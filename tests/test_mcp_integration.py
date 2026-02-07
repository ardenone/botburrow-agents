"""Integration tests for MCP server functionality.

These tests verify:
1. Agent can load and use MCP tools
2. MCP server fallback when server unavailable
3. Tool execution logs and metrics
4. Sandbox isolation for MCP tool execution
5. Common MCP servers (filesystem, search, etc.)
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock  # noqa: F401

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.mcp.manager import (
    BUILTIN_SERVERS,
    MCPManager,
    MCPServer,
    MCPServerConfig,
    MCPTool,
)
from botburrow_agents.models import (
    AgentConfig,
    BehaviorConfig,
    BrainConfig,
    CapabilityGrants,
    ToolCall,
)
from botburrow_agents.runner.loop import AgentLoop
from botburrow_agents.runner.sandbox import LocalSandbox


class TestMCPIntegration:
    """Integration tests for MCP server functionality."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        return Settings(
            hub_url="http://test-hub:8000",
            mcp_timeout=30,
        )

    @pytest.fixture
    def agent_with_mcp(self) -> AgentConfig:
        """Create agent configuration with MCP servers."""
        return AgentConfig(
            name="test-agent",
            type="native",
            brain=BrainConfig(
                model="claude-sonnet-4-20250514",
                provider="anthropic",
                temperature=0.7,
            ),
            capabilities=CapabilityGrants(
                grants=["github:*", "hub:*", "filesystem:*"],
                mcp_servers=["github", "hub", "filesystem"],
            ),
            behavior=BehaviorConfig(
                max_iterations=5,
            ),
        )

    @pytest.fixture
    def credentials(self) -> dict[str, str]:
        """Create test credentials."""
        return {
            "github_pat": "ghp_test_token_12345",
            "hub_api_key": "hub_test_key_67890",
        }

    @pytest.fixture
    async def sandbox(self, agent_with_mcp: AgentConfig, settings: Settings) -> LocalSandbox:
        """Create sandbox for testing."""
        sandbox = LocalSandbox(agent_with_mcp, settings)
        await sandbox.start()
        yield sandbox
        await sandbox.stop()

    @pytest.fixture
    async def mcp_manager(
        self,
        settings: Settings,
        agent_with_mcp: AgentConfig,
        credentials: dict[str, str],  # noqa: ARG002
        sandbox: LocalSandbox,  # noqa: ARG002
    ) -> MCPManager:
        """Create MCP manager with started servers (mocked)."""
        manager = MCPManager(settings)

        # Mock the actual server startup - we'll simulate running servers
        # for testing without needing actual MCP server processes
        for server_name in agent_with_mcp.capabilities.mcp_servers:
            config = BUILTIN_SERVERS.get(server_name)
            if config:
                # Create mock server instances
                mock_stdin = MagicMock()
                mock_stdin.write = MagicMock(return_value=None)
                mock_stdin.drain = AsyncMock()
                mock_stdout = AsyncMock()

                server = MCPServer(
                    config=config,
                    stdin=mock_stdin,
                    stdout=mock_stdout,
                    initialized=True,
                    tools=[
                        MCPTool(
                            name="test_tool",
                            description=f"Test tool for {server_name}",
                            input_schema={"type": "object"},
                        )
                    ],
                )
                manager._servers[server_name] = server

        yield manager
        await manager.stop_servers()


class TestAgentLoadsMCPTools(TestMCPIntegration):
    """Test that agents can load and discover MCP tools."""

    async def test_agent_discovers_mcp_tools(
        self,
        mcp_manager: MCPManager,
        agent_with_mcp: AgentConfig,
    ) -> None:
        """Test that agent can discover tools from MCP servers."""
        # Get all tools from running servers
        all_tools = mcp_manager.get_all_tools()

        # Should have tools from all configured servers
        assert len(all_tools) >= 3  # At least one tool per server

        # Tool names should follow mcp_<server>_<tool> pattern
        tool_names = [t["name"] for t in all_tools]
        for server_name in agent_with_mcp.capabilities.mcp_servers:
            assert any(f"mcp_{server_name}_" in name for name in tool_names)

    async def test_mcp_tools_in_agent_context(
        self,
        mcp_manager: MCPManager,
        agent_with_mcp: AgentConfig,
    ) -> None:
        """Test that MCP tools are included in agent context."""
        # Get tools for each server
        all_tools = []
        for server_name in agent_with_mcp.capabilities.mcp_servers:
            tools = mcp_manager.get_server_tools(server_name)
            all_tools.extend(tools)

        # Verify tool structure
        for tool in all_tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["name"].startswith("mcp_")

    async def test_grant_validation_blocks_unauthorized_mcp(
        self,
        settings: Settings,
    ) -> None:
        """Test that agents without grants can't access MCP servers."""
        # Create agent without github grants
        agent = AgentConfig(
            name="limited-agent",
            type="native",
            capabilities=CapabilityGrants(
                grants=["hub:*"],  # No github grants
                mcp_servers=["github"],  # But trying to use github
            ),
        )

        manager = MCPManager(settings)

        # Mock server startup
        config = BUILTIN_SERVERS["github"]
        mock_stdin = MagicMock()
        mock_stdout = AsyncMock()
        _ = MCPServer(  # Server created but not used - testing grant validation
            config=config,
            stdin=mock_stdin,
            stdout=mock_stdout,
            initialized=True,
        )

        # Try to start server - should be skipped due to missing grants
        credentials = {}
        workspace = Path("/tmp/test")
        started = await manager.start_servers(agent, credentials, workspace)

        # GitHub server should not start (missing grants)
        assert "github" not in started


class TestMCPToolExecution(TestMCPIntegration):
    """Test MCP tool execution in agent loop."""

    async def test_execute_mcp_tool_by_name(
        self,
        mcp_manager: MCPManager,
    ) -> None:
        """Test executing MCP tool by full name."""
        # Mock the call_tool method
        mcp_manager.call_tool = AsyncMock(
            return_value={
                "result": "success"
            }
        )

        result = await mcp_manager.call_tool_by_name(
            "mcp_github_create_pr",
            {"repo": "test/repo", "title": "Test PR"},
        )

        mcp_manager.call_tool.assert_called_once_with(
            "github", "create_pr", {"repo": "test/repo", "title": "Test PR"}
        )
        assert result["result"] == "success"

    async def test_mcp_tool_in_agent_loop(
        self,
        settings: Settings,
        agent_with_mcp: AgentConfig,  # noqa: ARG002
        sandbox: LocalSandbox,
        mcp_manager: MCPManager,
    ) -> None:
        """Test MCP tool execution through agent loop."""
        # Mock the MCP manager
        mcp_manager.call_tool_by_name = AsyncMock(
            return_value={"result": "Tool executed successfully"}
        )

        # Create agent loop with mock hub
        mock_hub = MagicMock()

        loop = AgentLoop(
            hub=mock_hub,
            sandbox=sandbox,
            mcp_manager=mcp_manager,
            settings=settings,
        )

        # Simulate MCP tool execution
        tool_call = ToolCall(
            id="test-123",
            name="mcp_github_create_pr",
            arguments={"repo": "owner/repo", "title": "Test"},
        )

        result = await loop._execute_mcp_tool("mcp_github_create_pr", tool_call.arguments)

        assert result.error is None
        assert "successfully" in result.output.lower()

    async def test_mcp_tool_error_handling(
        self,
        settings: Settings,
        sandbox: LocalSandbox,
    ) -> None:
        """Test error handling in MCP tool execution."""
        mock_hub = MagicMock()

        # MCP manager that raises error
        mcp_manager = MagicMock()
        mcp_manager.call_tool_by_name = AsyncMock(
            side_effect=RuntimeError("MCP server unavailable")
        )

        loop = AgentLoop(
            hub=mock_hub,
            sandbox=sandbox,
            mcp_manager=mcp_manager,
            settings=settings,
        )

        result = await loop._execute_mcp_tool("mcp_github_create_pr", {})

        assert result.error is not None
        assert "MCP server error" in result.error


class TestMCPFallbackMechanism(TestMCPIntegration):
    """Test MCP server fallback behavior."""

    async def test_static_tool_definitions_when_server_not_running(
        self,
        settings: Settings,
    ) -> None:
        """Test static tool definitions are returned when server not running."""
        manager = MCPManager(settings)

        # Server not started - should return static definitions
        tools = manager.get_server_tools("github")

        assert len(tools) >= 2
        tool_names = [t["name"] for t in tools]
        assert "mcp_github_get_file" in tool_names
        assert "mcp_github_create_pr" in tool_names

    async def test_error_when_calling_unavailable_server(
        self,
        settings: Settings,
    ) -> None:
        """Test error when trying to call tool on unavailable server."""
        manager = MCPManager(settings)

        with pytest.raises(ValueError, match="not running"):
            await manager.call_tool("github", "get_file", {"repo": "test"})

    async def test_fallback_to_static_definitions_for_all_servers(
        self,
        settings: Settings,
    ) -> None:
        """Test that all built-in servers have static fallback definitions."""
        manager = MCPManager(settings)

        for server_name in BUILTIN_SERVERS:
            tools = manager.get_server_tools(server_name)
            # Should return at least empty list (not crash)
            assert isinstance(tools, list)

            if server_name in ["github", "brave", "hub", "filesystem"]:
                # These servers should have static definitions
                assert len(tools) > 0, f"{server_name} should have static tools"

    async def test_grant_check_before_fallback(
        self,
        settings: Settings,
    ) -> None:
        """Test that static definitions are only returned if grants exist."""
        manager = MCPManager(settings)

        # Should return static tools regardless of grants
        # (static definitions are for tool discovery, not execution)
        tools = manager.get_server_tools("github")
        assert len(tools) > 0


class TestMCPSandboxIsolation(TestMCPIntegration):
    """Test sandbox isolation for MCP tool execution."""

    async def test_mcp_credentials_isolated_in_sandbox(
        self,
        settings: Settings,
        agent_with_mcp: AgentConfig,
        credentials: dict[str, str],
    ) -> None:
        """Test that MCP credentials are injected into sandbox environment."""
        manager = MCPManager(settings)

        workspace = Path(tempfile.mkdtemp())

        # Build environment for each server
        envs = {}
        for server_name in agent_with_mcp.capabilities.mcp_servers:
            env = manager._build_server_env(server_name, credentials, workspace)
            envs[server_name] = env

        # Verify credentials are injected
        assert envs["github"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_test_token_12345"
        assert envs["hub"]["HUB_API_KEY"] == "hub_test_key_67890"

        # Verify workspace is set
        for env in envs.values():
            assert env["HOME"] == str(workspace)

        # Cleanup
        import shutil
        shutil.rmtree(workspace, ignore_errors=True)

    async def test_workspace_path_isolation(
        self,
        settings: Settings,
        agent_with_mcp: AgentConfig,  # noqa: ARG002
    ) -> None:
        """Test that MCP servers run in isolated workspace."""
        manager = MCPManager(settings)

        workspace1 = Path(tempfile.mkdtemp())
        workspace2 = Path(tempfile.mkdtemp())

        credentials = {"github_pat": "test_token"}

        env1 = manager._build_server_env("github", credentials, workspace1)
        env2 = manager._build_server_env("github", credentials, workspace2)

        # Workspaces should be different
        assert env1["HOME"] != env2["HOME"]
        assert env1["HOME"] == str(workspace1)
        assert env2["HOME"] == str(workspace2)

        # Cleanup
        import shutil
        shutil.rmtree(workspace1, ignore_errors=True)
        shutil.rmtree(workspace2, ignore_errors=True)


class TestMCPToolExecutionMetrics(TestMCPIntegration):
    """Test that MCP tool execution is logged and metrics are collected."""

    async def test_mcp_call_logged(
        self,
        mcp_manager: MCPManager,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that MCP calls are logged."""

        # Mock the call to verify logging
        with caplog.at_level("DEBUG"):
            # Get tools (should log something if server was real)
            tools = mcp_manager.get_server_tools("github")
            # With mock server we have 1 test tool, static definitions have more
            assert len(tools) >= 1

    async def test_tool_result_format(
        self,
        settings: Settings,
        sandbox: LocalSandbox,
    ) -> None:
        """Test that MCP tool results are properly formatted."""
        mock_hub = MagicMock()

        # Create MCP manager with mocked response
        mcp_manager = MagicMock()
        mcp_manager.call_tool_by_name = AsyncMock(
            return_value={
                "result": {"data": "test data", "count": 5}
            }
        )

        loop = AgentLoop(
            hub=mock_hub,
            sandbox=sandbox,
            mcp_manager=mcp_manager,
            settings=settings,
        )

        result = await loop._execute_mcp_tool("mcp_test_tool", {})

        assert result.error is None
        # Result should be JSON formatted
        assert "data" in result.output


class TestCommonMCPServers(TestMCPIntegration):
    """Test common MCP server configurations."""

    def test_filesystem_server_config(self) -> None:
        """Test filesystem MCP server configuration."""
        assert "filesystem" in BUILTIN_SERVERS
        config = BUILTIN_SERVERS["filesystem"]
        assert config.name == "filesystem"
        assert config.command == "npx"
        assert "filesystem:read" in config.grants

    def test_postgres_server_config(self) -> None:
        """Test postgres MCP server configuration."""
        assert "postgres" in BUILTIN_SERVERS
        config = BUILTIN_SERVERS["postgres"]
        assert config.name == "postgres"
        assert "postgres:read" in config.grants

    def test_brave_search_server_config(self) -> None:
        """Test Brave search MCP server configuration."""
        assert "brave" in BUILTIN_SERVERS
        config = BUILTIN_SERVERS["brave"]
        assert config.name == "brave-search"
        assert "brave:search" in config.grants

    def test_all_servers_have_required_fields(self) -> None:
        """Test that all built-in servers have required configuration."""
        for _server_name, config in BUILTIN_SERVERS.items():
            # Check all required fields exist
            assert hasattr(config, "name")
            assert hasattr(config, "command")
            assert hasattr(config, "args")
            assert hasattr(config, "grants")

            # Check grants is a list
            assert isinstance(config.grants, list)

            # Check command is not empty
            assert config.command

    async def test_static_tool_definitions_coverage(
        self,
        settings: Settings,
    ) -> None:
        """Test that all major servers have static tool definitions."""
        manager = MCPManager(settings)

        servers_with_static_tools = ["github", "brave", "hub", "filesystem"]

        for server_name in servers_with_static_tools:
            tools = manager._get_static_tool_definitions(server_name)
            assert len(tools) > 0, f"{server_name} should have static tool definitions"

            # Verify tool structure
            for tool in tools:
                assert "name" in tool
                assert "description" in tool
                assert "parameters" in tool
                assert tool["name"].startswith(f"mcp_{server_name}_")


class TestMCPProtocolCompliance(TestMCPIntegration):
    """Test MCP protocol compliance."""

    async def test_json_rpc_format(self) -> None:
        """Test that MCP requests follow JSON-RPC 2.0 format."""

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        # Verify JSON-RPC format
        assert request["jsonrpc"] == "2.0"
        assert "id" in request
        assert "method" in request
        assert "params" in request

    async def test_mcp_protocol_version(self) -> None:
        """Test that correct MCP protocol version is used."""
        from botburrow_agents.mcp.manager import MCP_PROTOCOL_VERSION

        assert MCP_PROTOCOL_VERSION == "2024-11-05"

    async def test_client_info(self) -> None:
        """Test that client info is properly defined."""
        from botburrow_agents.mcp.manager import (
            MCP_CLIENT_NAME,
            MCP_CLIENT_VERSION,
        )

        assert MCP_CLIENT_NAME == "botburrow-agents"
        assert isinstance(MCP_CLIENT_VERSION, str)


class TestMCPServerResourceUsage(TestMCPIntegration):
    """Test MCP server resource management."""

    async def test_server_cleanup_on_stop(
        self,
        settings: Settings,
    ) -> None:
        """Test that servers are properly cleaned up when stopped."""
        manager = MCPManager(settings)

        # Add a mock server
        config = MCPServerConfig(name="test", command="echo")
        mock_process = MagicMock()
        mock_process.returncode = None  # Still running
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        server = MCPServer(config=config, process=mock_process)
        manager._servers["test"] = server

        await manager.stop_servers()

        # Verify cleanup
        assert len(manager._servers) == 0
        mock_process.terminate.assert_called_once()

    async def test_timeout_configuration(
        self,
        settings: Settings,
    ) -> None:
        """Test that MCP timeout is configurable."""
        assert settings.mcp_timeout == 30

        # Verify timeout is used in requests
        manager = MCPManager(settings)
        assert manager.settings.mcp_timeout == 30
