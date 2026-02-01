"""Tests for MCP server management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.mcp.manager import (
    BUILTIN_SERVERS,
    MCPManager,
    MCPServer,
    MCPServerCapabilities,
    MCPServerConfig,
    MCPTool,
)
from botburrow_agents.models import AgentConfig, BrainConfig, CapabilityGrants


class TestMCPServerConfig:
    """Tests for MCPServerConfig."""

    def test_builtin_github_config(self) -> None:
        """Test GitHub server config exists."""
        assert "github" in BUILTIN_SERVERS
        config = BUILTIN_SERVERS["github"]
        assert config.name == "github"
        assert config.command == "npx"
        assert "github:read" in config.grants
        assert "github:write" in config.grants

    def test_builtin_brave_config(self) -> None:
        """Test Brave search server config exists."""
        assert "brave" in BUILTIN_SERVERS
        config = BUILTIN_SERVERS["brave"]
        assert config.name == "brave-search"
        assert config.command == "npx"

    def test_builtin_hub_config(self) -> None:
        """Test Hub server config exists."""
        assert "hub" in BUILTIN_SERVERS
        config = BUILTIN_SERVERS["hub"]
        assert config.name == "hub"
        assert config.command == "python"


class TestMCPManager:
    """Tests for MCPManager."""

    @pytest.fixture
    def manager(self, settings: Settings) -> MCPManager:
        """Create MCP manager."""
        return MCPManager(settings)

    @pytest.fixture
    def agent_with_mcp(self) -> AgentConfig:
        """Agent with MCP servers configured."""
        return AgentConfig(
            name="test-agent",
            type="claude-code",
            brain=BrainConfig(model="claude-sonnet-4-20250514"),
            capabilities=CapabilityGrants(
                grants=["github:read", "github:write", "hub:read", "hub:write"],
                mcp_servers=["github", "hub"],
            ),
        )

    @pytest.fixture
    def agent_without_grants(self) -> AgentConfig:
        """Agent without required grants."""
        return AgentConfig(
            name="limited-agent",
            type="claude-code",
            capabilities=CapabilityGrants(
                grants=["hub:read"],  # No github grants
                mcp_servers=["github", "hub"],
            ),
        )

    def test_has_required_grants_with_exact_match(
        self, manager: MCPManager, agent_with_mcp: AgentConfig
    ) -> None:
        """Test grant matching with exact match."""
        github_config = BUILTIN_SERVERS["github"]
        assert manager._has_required_grants(agent_with_mcp, github_config)

    def test_has_required_grants_with_wildcard(
        self, manager: MCPManager
    ) -> None:
        """Test grant matching with wildcard."""
        agent = AgentConfig(
            name="wildcard-agent",
            capabilities=CapabilityGrants(
                grants=["github:*"],
                mcp_servers=["github"],
            ),
        )
        github_config = BUILTIN_SERVERS["github"]
        assert manager._has_required_grants(agent, github_config)

    def test_has_required_grants_missing(
        self, manager: MCPManager, agent_without_grants: AgentConfig
    ) -> None:
        """Test grant check fails when missing."""
        github_config = BUILTIN_SERVERS["github"]
        assert not manager._has_required_grants(agent_without_grants, github_config)

    def test_build_server_env_github(
        self, manager: MCPManager
    ) -> None:
        """Test building env for GitHub server."""
        credentials = {"github_pat": "ghp_test_token"}
        workspace = Path("/tmp/test")

        env = manager._build_server_env("github", credentials, workspace)

        assert env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_test_token"
        assert env["HOME"] == str(workspace)

    def test_build_server_env_brave(
        self, manager: MCPManager
    ) -> None:
        """Test building env for Brave server."""
        credentials = {"brave_api_key": "brave_test_key"}
        workspace = Path("/tmp/test")

        env = manager._build_server_env("brave", credentials, workspace)

        assert env["BRAVE_API_KEY"] == "brave_test_key"

    def test_build_server_env_hub(
        self, manager: MCPManager, settings: Settings
    ) -> None:
        """Test building env for Hub server."""
        credentials = {"hub_api_key": "hub_test_key"}
        workspace = Path("/tmp/test")

        env = manager._build_server_env("hub", credentials, workspace)

        assert env["HUB_API_KEY"] == "hub_test_key"
        assert env["HUB_URL"] == settings.hub_url

    def test_get_server_tools_github_static(
        self, manager: MCPManager
    ) -> None:
        """Test getting GitHub server tools (static fallback)."""
        tools = manager.get_server_tools("github")

        assert len(tools) >= 2
        tool_names = [t["name"] for t in tools]
        assert "mcp_github_get_file" in tool_names
        assert "mcp_github_create_pr" in tool_names

    def test_get_server_tools_hub_static(
        self, manager: MCPManager
    ) -> None:
        """Test getting Hub server tools (static fallback)."""
        tools = manager.get_server_tools("hub")

        assert len(tools) >= 2
        tool_names = [t["name"] for t in tools]
        assert "mcp_hub_search" in tool_names
        assert "mcp_hub_post" in tool_names

    def test_get_server_tools_unknown(
        self, manager: MCPManager
    ) -> None:
        """Test getting tools for unknown server."""
        tools = manager.get_server_tools("unknown")
        assert tools == []

    def test_get_server_tools_dynamic(
        self, manager: MCPManager
    ) -> None:
        """Test getting tools from running server with discovered tools."""
        # Create a mock server with discovered tools
        config = MCPServerConfig(name="test", command="test")
        server = MCPServer(
            config=config,
            initialized=True,
            tools=[
                MCPTool(name="custom_tool", description="Custom tool", input_schema={}),
            ],
        )
        manager._servers["test"] = server

        tools = manager.get_server_tools("test")

        assert len(tools) == 1
        assert tools[0]["name"] == "mcp_test_custom_tool"
        assert tools[0]["description"] == "Custom tool"

    def test_get_all_tools(
        self, manager: MCPManager
    ) -> None:
        """Test getting tools from all servers."""
        # Add mock servers
        config1 = MCPServerConfig(name="server1", command="test")
        config2 = MCPServerConfig(name="server2", command="test")

        manager._servers["server1"] = MCPServer(
            config=config1,
            initialized=True,
            tools=[MCPTool(name="tool1", description="Tool 1")],
        )
        manager._servers["server2"] = MCPServer(
            config=config2,
            initialized=True,
            tools=[MCPTool(name="tool2", description="Tool 2")],
        )

        all_tools = manager.get_all_tools()

        assert len(all_tools) == 2
        tool_names = [t["name"] for t in all_tools]
        assert "mcp_server1_tool1" in tool_names
        assert "mcp_server2_tool2" in tool_names

    def test_is_server_running(
        self, manager: MCPManager
    ) -> None:
        """Test checking if server is running."""
        assert not manager.is_server_running("test")

        config = MCPServerConfig(name="test", command="test")
        manager._servers["test"] = MCPServer(config=config, initialized=True)

        assert manager.is_server_running("test")

    def test_get_running_servers(
        self, manager: MCPManager
    ) -> None:
        """Test getting list of running servers."""
        config = MCPServerConfig(name="test", command="test")
        manager._servers["test"] = MCPServer(config=config, initialized=True)
        manager._servers["test2"] = MCPServer(config=config, initialized=False)

        running = manager.get_running_servers()

        assert "test" in running
        assert "test2" not in running

    @pytest.mark.asyncio
    async def test_stop_servers_empty(
        self, manager: MCPManager
    ) -> None:
        """Test stopping when no servers running."""
        await manager.stop_servers()
        # Should complete without error

    @pytest.mark.asyncio
    async def test_call_tool_not_running(
        self, manager: MCPManager
    ) -> None:
        """Test calling tool when server not running."""
        with pytest.raises(ValueError, match="not running"):
            await manager.call_tool("github", "get_file", {"repo": "test/repo"})

    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(
        self, manager: MCPManager
    ) -> None:
        """Test calling tool when server not initialized."""
        config = MCPServerConfig(name="test", command="test")
        manager._servers["test"] = MCPServer(config=config, initialized=False)

        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.call_tool("test", "some_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_by_name(
        self, manager: MCPManager
    ) -> None:
        """Test calling tool by full name."""
        # Mock the call_tool method
        manager.call_tool = AsyncMock(return_value={"result": "success"})

        result = await manager.call_tool_by_name(
            "mcp_github_create_pr",
            {"repo": "test/repo", "title": "Test PR"},
        )

        manager.call_tool.assert_called_once_with(
            "github", "create_pr", {"repo": "test/repo", "title": "Test PR"}
        )

    @pytest.mark.asyncio
    async def test_call_tool_by_name_invalid_format(
        self, manager: MCPManager
    ) -> None:
        """Test calling tool with invalid name format."""
        with pytest.raises(ValueError, match="Invalid MCP tool name"):
            await manager.call_tool_by_name("invalid_tool", {})


class TestMCPServer:
    """Tests for MCPServer dataclass."""

    def test_mcp_server_creation(self) -> None:
        """Test creating MCPServer instance."""
        config = MCPServerConfig(
            name="test",
            command="echo",
            args=["hello"],
        )
        server = MCPServer(config=config)

        assert server.config.name == "test"
        assert server.process is None
        assert server.request_id == 0
        assert server.initialized is False
        assert server.tools == []

    def test_mcp_server_request_id_increment(self) -> None:
        """Test request ID incrementing."""
        config = MCPServerConfig(name="test", command="echo")
        server = MCPServer(config=config)

        assert server.request_id == 0
        server.request_id += 1
        assert server.request_id == 1

    def test_mcp_server_capabilities(self) -> None:
        """Test MCPServerCapabilities defaults."""
        caps = MCPServerCapabilities()
        assert caps.tools is False
        assert caps.resources is False
        assert caps.prompts is False
        assert caps.logging is False

    def test_mcp_tool_creation(self) -> None:
        """Test MCPTool creation."""
        tool = MCPTool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"


class TestMCPProtocol:
    """Tests for MCP protocol methods."""

    @pytest.fixture
    def manager(self, settings: Settings) -> MCPManager:
        """Create MCP manager."""
        return MCPManager(settings)

    @pytest.mark.asyncio
    async def test_send_notification(self, manager: MCPManager) -> None:
        """Test sending notification to server."""
        # Create mock server with proper async mock for drain only
        config = MCPServerConfig(name="test", command="test")
        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock(return_value=None)
        mock_stdin.drain = AsyncMock()
        server = MCPServer(config=config, stdin=mock_stdin)

        await manager._send_notification(server, "notifications/initialized", {})

        mock_stdin.write.assert_called_once()
        mock_stdin.drain.assert_called_once()

        # Check the notification format
        written_data = mock_stdin.write.call_args[0][0]
        notification = __import__("json").loads(written_data)
        assert notification["jsonrpc"] == "2.0"
        assert notification["method"] == "notifications/initialized"
        assert "id" not in notification  # Notifications have no ID

    @pytest.mark.asyncio
    async def test_send_request(self, manager: MCPManager) -> None:
        """Test sending request and receiving response."""
        config = MCPServerConfig(name="test", command="test")

        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock(return_value=None)
        mock_stdin.drain = AsyncMock()
        mock_stdout = AsyncMock()

        # Mock reading a valid response
        response = {"jsonrpc": "2.0", "id": 1, "result": {"success": True}}
        mock_stdout.readline = AsyncMock(
            return_value=(__import__("json").dumps(response) + "\n").encode()
        )

        server = MCPServer(config=config, stdin=mock_stdin, stdout=mock_stdout)

        result = await manager._send_request(server, "test/method", {"arg": "value"})

        assert result == {"success": True}
        assert server.request_id == 1

    @pytest.mark.asyncio
    async def test_send_request_error_response(self, manager: MCPManager) -> None:
        """Test handling error response from server."""
        config = MCPServerConfig(name="test", command="test")

        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock(return_value=None)
        mock_stdin.drain = AsyncMock()
        mock_stdout = AsyncMock()

        # Mock error response
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid request"},
        }
        mock_stdout.readline = AsyncMock(
            return_value=(__import__("json").dumps(error_response) + "\n").encode()
        )

        server = MCPServer(config=config, stdin=mock_stdin, stdout=mock_stdout)

        with pytest.raises(RuntimeError, match="Invalid request"):
            await manager._send_request(server, "test/method", {})
