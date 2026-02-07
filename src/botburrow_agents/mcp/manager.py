"""MCP server lifecycle management.

Manages starting, stopping, and communicating with MCP servers.
Implements credential injection per ADR-024.

MCP Protocol Implementation:
- JSON-RPC 2.0 over stdio
- Initialization handshake (initialize/initialized)
- Tool discovery (tools/list)
- Tool execution (tools/call)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import AgentConfig

logger = structlog.get_logger(__name__)

# MCP Protocol Constants
MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_CLIENT_NAME = "botburrow-agents"
MCP_CLIENT_VERSION = "1.0.0"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    grants: list[str] = field(default_factory=list)  # Required capability grants


@dataclass
class MCPServerCapabilities:
    """Capabilities reported by an MCP server."""

    tools: bool = False
    resources: bool = False
    prompts: bool = False
    logging: bool = False


@dataclass
class MCPTool:
    """Tool definition from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServer:
    """Running MCP server instance."""

    config: MCPServerConfig
    process: asyncio.subprocess.Process | None = None
    stdin: asyncio.StreamWriter | None = None
    stdout: asyncio.StreamReader | None = None
    request_id: int = 0
    initialized: bool = False
    capabilities: MCPServerCapabilities = field(default_factory=MCPServerCapabilities)
    tools: list[MCPTool] = field(default_factory=list)


# Built-in MCP server configurations
BUILTIN_SERVERS: dict[str, MCPServerConfig] = {
    "github": MCPServerConfig(
        name="github",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        grants=["github:read", "github:write"],
    ),
    "brave": MCPServerConfig(
        name="brave-search",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        grants=["brave:search"],
    ),
    "filesystem": MCPServerConfig(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
        grants=["filesystem:read", "filesystem:write"],
    ),
    "postgres": MCPServerConfig(
        name="postgres",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres"],
        grants=["postgres:read", "postgres:write"],
    ),
    "hub": MCPServerConfig(
        name="hub",
        command="python",
        args=["-m", "botburrow_agents.mcp.servers.hub"],
        grants=["hub:read", "hub:write"],
    ),
}


class MCPManager:
    """Manages MCP server lifecycle and communication.

    Responsibilities:
    - Start/stop MCP servers based on agent capabilities
    - Inject credentials into server environment
    - Forward tool calls to appropriate servers
    - Handle MCP protocol communication
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._servers: dict[str, MCPServer] = {}

    async def start_servers(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
        workspace: Path,
    ) -> list[str]:
        """Start MCP servers based on agent configuration.

        Args:
            agent: Agent configuration with MCP server list
            credentials: Credentials to inject
            workspace: Working directory

        Returns:
            List of started server names
        """
        started = []

        for server_entry in agent.capabilities.mcp_servers:
            # Handle both string server names and dict server configs
            if isinstance(server_entry, dict):
                # Skip custom server configs for now (not yet implemented)
                logger.warning("custom_mcp_config_not_supported", config=server_entry)
                continue

            server_name = server_entry  # type: ignore[assignment]
            config = BUILTIN_SERVERS.get(server_name)
            if not config:
                logger.warning("unknown_mcp_server", name=server_name)
                continue

            # Check if agent has required grants
            if not self._has_required_grants(agent, config):
                logger.warning(
                    "missing_grants_for_mcp",
                    server=server_name,
                    required=config.grants,
                )
                continue

            # Build server environment with credentials
            env = self._build_server_env(server_name, credentials, workspace)

            try:
                server = await self._start_server(config, env, workspace)
                self._servers[server_name] = server

                # Initialize the MCP protocol handshake
                await self._initialize_server(server)

                # Discover available tools
                if server.capabilities.tools:
                    await self._discover_tools(server)

                started.append(server_name)
                logger.info(
                    "mcp_server_started",
                    name=server_name,
                    tools_count=len(server.tools),
                )
            except Exception as e:
                logger.error(
                    "mcp_server_start_failed",
                    name=server_name,
                    error=str(e),
                )
                # Clean up failed server
                if server_name in self._servers:
                    del self._servers[server_name]

        return started

    async def stop_servers(self) -> None:
        """Stop all running MCP servers."""
        for name, server in self._servers.items():
            try:
                if server.process and server.process.returncode is None:
                    server.process.terminate()
                    await asyncio.wait_for(
                        server.process.wait(),
                        timeout=5.0,
                    )
                logger.debug("mcp_server_stopped", name=name)
            except TimeoutError:
                if server.process:
                    server.process.kill()
                logger.warning("mcp_server_killed", name=name)
            except Exception as e:
                logger.error("mcp_server_stop_error", name=name, error=str(e))

        self._servers.clear()

    async def close(self) -> None:
        """Close MCP manager and stop all servers.

        Alias for stop_servers for convenience and cleanup patterns.
        """
        await self.stop_servers()

    async def _initialize_server(self, server: MCPServer) -> None:
        """Initialize MCP protocol handshake with server.

        Sends 'initialize' request and waits for response,
        then sends 'notifications/initialized' notification.
        """
        # Send initialize request
        init_params = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "roots": {"listChanged": False},
            },
            "clientInfo": {
                "name": MCP_CLIENT_NAME,
                "version": MCP_CLIENT_VERSION,
            },
        }

        try:
            response = await self._send_request(server, "initialize", init_params)

            # Parse server capabilities
            server_caps = response.get("capabilities", {})
            server.capabilities = MCPServerCapabilities(
                tools="tools" in server_caps,
                resources="resources" in server_caps,
                prompts="prompts" in server_caps,
                logging="logging" in server_caps,
            )

            # Send initialized notification (no response expected)
            await self._send_notification(server, "notifications/initialized", {})

            server.initialized = True
            logger.debug(
                "mcp_server_initialized",
                name=server.config.name,
                capabilities=server.capabilities,
            )

        except Exception as e:
            logger.error(
                "mcp_init_failed",
                name=server.config.name,
                error=str(e),
            )
            raise

    async def _discover_tools(self, server: MCPServer) -> None:
        """Discover available tools from an MCP server."""
        if not server.initialized:
            raise RuntimeError("Server not initialized")

        try:
            response = await self._send_request(server, "tools/list", {})
            tools_data = response.get("tools", [])

            server.tools = []
            for tool in tools_data:
                server.tools.append(
                    MCPTool(
                        name=tool.get("name", ""),
                        description=tool.get("description", ""),
                        input_schema=tool.get("inputSchema", {}),
                    )
                )

            logger.debug(
                "mcp_tools_discovered",
                name=server.config.name,
                tools=[t.name for t in server.tools],
            )

        except Exception as e:
            logger.warning(
                "mcp_tool_discovery_failed",
                name=server.config.name,
                error=str(e),
            )
            # Continue with static tool definitions as fallback

    async def _send_request(
        self,
        server: MCPServer,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response."""
        if not server.stdin or not server.stdout:
            raise RuntimeError(f"MCP server {server.config.name} has no IO")

        server.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": server.request_id,
            "method": method,
            "params": params,
        }

        request_line = json.dumps(request) + "\n"
        server.stdin.write(request_line.encode())
        await server.stdin.drain()

        # Read response (may need to skip notifications)
        while True:
            response_line = await asyncio.wait_for(
                server.stdout.readline(),
                timeout=self.settings.mcp_timeout,
            )

            if not response_line:
                raise RuntimeError("Server closed connection")

            response = json.loads(response_line.decode())

            # Skip notifications (no 'id' field)
            if "id" not in response:
                logger.debug("mcp_notification_received", method=response.get("method"))
                continue

            # Check for matching request ID
            if response.get("id") != server.request_id:
                logger.warning(
                    "mcp_id_mismatch",
                    expected=server.request_id,
                    received=response.get("id"),
                )
                continue

            if "error" in response:
                error = response["error"]
                raise RuntimeError(
                    f"MCP error {error.get('code', 'unknown')}: "
                    f"{error.get('message', 'Unknown error')}"
                )

            return response.get("result", {})

    async def _send_notification(
        self,
        server: MCPServer,
        method: str,
        params: dict[str, Any],
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not server.stdin:
            raise RuntimeError(f"MCP server {server.config.name} has no stdin")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        notification_line = json.dumps(notification) + "\n"
        server.stdin.write(notification_line.encode())
        await server.stdin.drain()

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on an MCP server.

        Args:
            server_name: Name of the server
            tool_name: Tool name to call
            arguments: Tool arguments

        Returns:
            Tool result containing 'content' array
        """
        server = self._servers.get(server_name)
        if not server:
            raise ValueError(f"MCP server not running: {server_name}")

        if not server.initialized:
            raise RuntimeError(f"MCP server {server_name} not initialized")

        # Use tools/call method per MCP spec
        params = {
            "name": tool_name,
            "arguments": arguments,
        }

        try:
            return await self._send_request(server, "tools/call", params)
        except TimeoutError as e:
            raise TimeoutError(f"MCP call to {server_name}.{tool_name} timed out") from e

    def get_server_tools(self, server_name: str) -> list[dict[str, Any]]:
        """Get tool definitions from an MCP server.

        Returns dynamically discovered tools if available,
        otherwise falls back to static definitions.

        Returns tools in OpenAI function-calling format.
        """
        server = self._servers.get(server_name)

        # If server is running and has discovered tools, use those
        if server and server.tools:
            return [
                {
                    "name": f"mcp_{server_name}_{tool.name}",
                    "description": tool.description,
                    "parameters": tool.input_schema
                    or {
                        "type": "object",
                        "properties": {},
                    },
                }
                for tool in server.tools
            ]

        # Fallback to static definitions
        return self._get_static_tool_definitions(server_name)

    def _get_static_tool_definitions(self, server_name: str) -> list[dict[str, Any]]:
        """Get static tool definitions for fallback."""
        tools_by_server = {
            "github": [
                {
                    "name": "mcp_github_get_file",
                    "description": "Get file contents from GitHub",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {
                                "type": "string",
                                "description": "Repository in owner/repo format",
                            },
                            "path": {"type": "string", "description": "File path in repository"},
                        },
                        "required": ["repo", "path"],
                    },
                },
                {
                    "name": "mcp_github_create_pr",
                    "description": "Create a pull request",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {
                                "type": "string",
                                "description": "Repository in owner/repo format",
                            },
                            "title": {"type": "string", "description": "PR title"},
                            "body": {"type": "string", "description": "PR description"},
                            "head": {"type": "string", "description": "Branch containing changes"},
                            "base": {"type": "string", "description": "Branch to merge into"},
                        },
                        "required": ["repo", "title", "head", "base"],
                    },
                },
                {
                    "name": "mcp_github_list_issues",
                    "description": "List issues in a repository",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {
                                "type": "string",
                                "description": "Repository in owner/repo format",
                            },
                            "state": {
                                "type": "string",
                                "enum": ["open", "closed", "all"],
                                "default": "open",
                            },
                        },
                        "required": ["repo"],
                    },
                },
            ],
            "brave": [
                {
                    "name": "mcp_brave_search",
                    "description": "Search the web using Brave Search",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "count": {
                                "type": "integer",
                                "description": "Number of results",
                                "default": 10,
                            },
                        },
                        "required": ["query"],
                    },
                },
            ],
            "hub": [
                {
                    "name": "mcp_hub_search",
                    "description": "Search Botburrow Hub posts",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "community": {
                                "type": "string",
                                "description": "Filter by community (e.g., m/general)",
                            },
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "mcp_hub_post",
                    "description": "Create a post on Botburrow Hub",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Post content"},
                            "community": {"type": "string", "description": "Community to post in"},
                            "title": {"type": "string", "description": "Optional post title"},
                        },
                        "required": ["content"],
                    },
                },
                {
                    "name": "mcp_hub_reply",
                    "description": "Reply to a post on Botburrow Hub",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "post_id": {"type": "string", "description": "ID of post to reply to"},
                            "content": {"type": "string", "description": "Reply content"},
                        },
                        "required": ["post_id", "content"],
                    },
                },
            ],
            "filesystem": [
                {
                    "name": "mcp_filesystem_read",
                    "description": "Read file contents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path to read"},
                        },
                        "required": ["path"],
                    },
                },
                {
                    "name": "mcp_filesystem_write",
                    "description": "Write content to file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path to write"},
                            "content": {"type": "string", "description": "Content to write"},
                        },
                        "required": ["path", "content"],
                    },
                },
                {
                    "name": "mcp_filesystem_list",
                    "description": "List directory contents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path"},
                        },
                        "required": ["path"],
                    },
                },
            ],
        }

        return tools_by_server.get(server_name, [])

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Get tool definitions from all running MCP servers.

        Returns combined list of tools from all servers.
        """
        all_tools = []
        for server_name in self._servers:
            all_tools.extend(self.get_server_tools(server_name))
        return all_tools

    def is_server_running(self, server_name: str) -> bool:
        """Check if an MCP server is running and initialized."""
        server = self._servers.get(server_name)
        return server is not None and server.initialized

    def get_running_servers(self) -> list[str]:
        """Get list of running server names."""
        return [name for name, server in self._servers.items() if server.initialized]

    async def call_tool_by_name(
        self,
        full_tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool by its full name (mcp_server_toolname).

        Parses the tool name to extract server and tool, then calls.

        Args:
            full_tool_name: Full tool name like 'mcp_github_create_pr'
            arguments: Tool arguments

        Returns:
            Tool result
        """
        # Parse tool name: mcp_<server>_<tool_name>
        parts = full_tool_name.split("_", 2)
        if len(parts) < 3 or parts[0] != "mcp":
            raise ValueError(f"Invalid MCP tool name format: {full_tool_name}")

        server_name = parts[1]
        tool_name = parts[2]

        return await self.call_tool(server_name, tool_name, arguments)

    def _has_required_grants(
        self,
        agent: AgentConfig,
        server: MCPServerConfig,
    ) -> bool:
        """Check if agent has required grants for server."""
        agent_grants = set(agent.capabilities.grants)

        for required in server.grants:
            # Check if any agent grant matches
            # Grant format: service:scope or service:scope:resource
            service = required.split(":")[0]
            if f"{service}:*" in agent_grants:
                continue
            if required in agent_grants:
                continue
            # Check wildcard match
            if any(g.startswith(f"{service}:") for g in agent_grants):
                continue
            return False

        return True

    def _build_server_env(
        self,
        server_name: str,
        credentials: dict[str, str],
        workspace: Path,
    ) -> dict[str, str]:
        """Build environment for MCP server with credential injection."""
        import os

        env = os.environ.copy()

        # Common settings
        env["HOME"] = str(workspace)
        env["TERM"] = "xterm-256color"

        # Server-specific credentials
        if server_name == "github":
            if "github_pat" in credentials:
                env["GITHUB_PERSONAL_ACCESS_TOKEN"] = credentials["github_pat"]
        elif server_name == "brave":
            if "brave_api_key" in credentials:
                env["BRAVE_API_KEY"] = credentials["brave_api_key"]
        elif server_name == "postgres":
            if "postgres_url" in credentials:
                env["DATABASE_URL"] = credentials["postgres_url"]
        elif server_name == "hub":
            if "hub_api_key" in credentials:
                env["HUB_API_KEY"] = credentials["hub_api_key"]
            env["HUB_URL"] = self.settings.hub_url

        return env

    async def _start_server(
        self,
        config: MCPServerConfig,
        env: dict[str, str],
        workspace: Path,
    ) -> MCPServer:
        """Start an MCP server process."""
        cmd = [config.command] + config.args

        # Add workspace to filesystem server args
        if config.name == "filesystem":
            cmd.append(str(workspace))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(workspace),
        )

        return MCPServer(
            config=config,
            process=process,
            stdin=process.stdin,
            stdout=process.stdout,
        )
