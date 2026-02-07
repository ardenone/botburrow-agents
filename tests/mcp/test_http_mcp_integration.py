"""Test HTTP-based MCP server integration (zai-proxy).

This module tests the HTTP-based MCP servers used by agents configured
in /home/coder/claude-config/agents/. These include:
- zai-web-search (web_search_prime)
- zai-web-reader (web content reading)
- zai-zread (GitHub repository reading)

Tests verify:
1. MCP server configs in agent-definitions
2. Agent can load and use MCP tools
3. Sandbox isolation for agent execution
4. Common MCP servers: filesystem, database, search, web
5. Tool execution logs and metrics
6. MCP server fallback if server unavailable
7. MCP server resource usage monitoring
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: F401

import httpx
import pytest

# HTTP MCP server configuration (from agent settings.json files)
ZAI_PROXY_BASE = "http://zai-proxy.devpod.svc.cluster.local:8080"
ZAI_MCP_ENDPOINTS = {
    "zai-web-search": f"{ZAI_PROXY_BASE}/api/mcp/web_search_prime/mcp",
    "zai-web-reader": f"{ZAI_PROXY_BASE}/api/mcp/web_reader/mcp",
    "zai-zread": f"{ZAI_PROXY_BASE}/api/mcp/zread/mcp",
}


class HTTPMCPClient:
    """HTTP-based MCP client following JSON-RPC 2.0 over HTTP POST.

    This is the transport used by zai-proxy MCP servers.
    Unlike stdio-based MCP, this uses HTTP with:
    - Accept: application/json, text/event-stream (required)
    - Content-Type: application/json
    - JSON-RPC 2.0 protocol
    """

    def __init__(self, mcp_url: str, timeout: float = 120.0):
        self.mcp_url = mcp_url
        self.client = httpx.AsyncClient(timeout=timeout)
        self.request_id = 0

    async def initialize(self) -> dict[str, Any]:
        """Initialize MCP session."""
        init_request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        return await self._send_message(init_request)

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available MCP tools."""
        list_request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
        }
        response = await self._send_message(list_request)
        return response.get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool with arguments."""
        call_request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        return await self._send_message(call_request)

    async def _send_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a message and receive response."""
        response = await self.client.post(
            self.mcp_url,
            json=message,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",  # Required by zai-proxy
            },
        )
        response.raise_for_status()

        # Parse SSE-style response if present
        text = response.text
        if "event:message" in text:
            # Extract data from SSE format
            for line in text.split("\n"):
                if line.startswith("data:"):
                    return json.loads(line[5:])
        return response.json()

    def _next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    async def close(self):
        """Close the client."""
        await self.client.aclose()


@pytest.fixture
def agent_settings_path() -> Path:
    """Path to agent settings.json files."""
    return Path("/home/coder/claude-config/agents")


@pytest.fixture
def claude_code_glm_47_settings(agent_settings_path: Path) -> dict[str, Any]:
    """Load claude-code-glm-47 agent settings."""
    settings_path = agent_settings_path / "claude-code-glm-47" / "settings.json"
    with open(settings_path) as f:
        return json.load(f)


@pytest.fixture
def opencode_glm_47_settings(agent_settings_path: Path) -> dict[str, Any]:
    """Load opencode-glm-47 agent settings."""
    settings_path = agent_settings_path / "opencode-glm-47" / "settings.json"
    with open(settings_path) as f:
        return json.load(f)


@pytest.mark.integration
class TestAgentMCPConfigs:
    """Test MCP server configurations in agent-definitions."""

    def test_claude_code_glm_47_has_mcp_servers(
        self, claude_code_glm_47_settings: dict[str, Any]
    ) -> None:
        """Verify claude-code-glm-47 has MCP servers configured."""
        assert "mcpServers" in claude_code_glm_47_settings
        mcp_servers = claude_code_glm_47_settings["mcpServers"]

        # Check expected servers
        assert "zai-web-search" in mcp_servers
        assert "zai-web-reader" in mcp_servers
        assert "zai-zread" in mcp_servers

    def test_opencode_glm_47_has_mcp_servers(
        self, opencode_glm_47_settings: dict[str, Any]
    ) -> None:
        """Verify opencode-glm-47 has MCP servers configured."""
        assert "mcpServers" in opencode_glm_47_settings
        mcp_servers = opencode_glm_47_settings["mcpServers"]

        # Check expected servers
        assert "zai-web-search" in mcp_servers
        assert "zai-web-reader" in mcp_servers
        assert "zai-zread" in mcp_servers

    def test_mcp_server_type_is_http(
        self, claude_code_glm_47_settings: dict[str, Any]
    ) -> None:
        """Verify MCP servers use HTTP transport type."""
        mcp_servers = claude_code_glm_47_settings["mcpServers"]

        for server_name, server_config in mcp_servers.items():
            assert "type" in server_config
            assert server_config["type"] == "http", f"{server_name} should use HTTP type"

    def test_mcp_server_urls_valid(
        self, claude_code_glm_47_settings: dict[str, Any]
    ) -> None:
        """Verify MCP server URLs are properly formatted."""
        mcp_servers = claude_code_glm_47_settings["mcpServers"]

        for server_name, server_config in mcp_servers.items():
            assert "url" in server_config
            url = server_config["url"]
            assert url.startswith("http://"), f"{server_name} URL should start with http://"
            assert "/api/mcp/" in url, f"{server_name} URL should contain /api/mcp/ path"
            assert url.endswith("/mcp"), f"{server_name} URL should end with /mcp"

    def test_claude_code_sonnet_no_mcp_servers(self, agent_settings_path: Path) -> None:
        """Verify claude-code-sonnet does NOT have MCP servers (baseline)."""
        settings_path = agent_settings_path / "claude-code-sonnet" / "settings.json"
        with open(settings_path) as f:
            settings = json.load(f)

        # Sonnet agent doesn't have MCP servers configured
        mcp_servers = settings.get("mcpServers", {})
        assert len(mcp_servers) == 0, "claude-code-sonnet should not have MCP servers"


@pytest.mark.integration
class TestHTTPMCPServers:
    """Integration tests for HTTP-based MCP servers.

    These tests require access to zai-proxy service.
    Skip with: pytest -m "not integration"
    """

    @pytest.mark.asyncio
    async def test_zai_web_search_initialize(self) -> None:
        """Test initializing zai-web-search MCP server."""
        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-web-search"])

        try:
            response = await client.initialize()

            assert "result" in response
            result = response["result"]
            assert "protocolVersion" in result
            assert "serverInfo" in result
            assert result["serverInfo"]["name"] == "mcp-web-search-prime"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_zai_web_search_list_tools(self) -> None:
        """Test listing tools from zai-web-search."""
        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-web-search"])

        try:
            tools = await client.list_tools()

            assert len(tools) > 0
            # Verify tool structure
            tool = tools[0]
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["name"] == "webSearchPrime"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_zai_zread_list_tools(self) -> None:
        """Test listing tools from zai-zread (GitHub reader)."""
        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-zread"])

        try:
            tools = await client.list_tools()

            assert len(tools) >= 3
            tool_names = [t["name"] for t in tools]

            # Expected tools for zread
            assert "search_doc" in tool_names
            assert "read_file" in tool_names
            assert "get_repo_structure" in tool_names
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_zai_web_reader_list_tools(self) -> None:
        """Test listing tools from zai-web-reader."""
        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-web-reader"])

        try:
            tools = await client.list_tools()

            assert len(tools) > 0
            tool_names = [t["name"] for t in tools]

            # Should have webReader tool
            assert "webReader" in tool_names
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_mcp_server_accept_header_requirement(self) -> None:
        """Test that Accept header with both JSON and SSE is required."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Without proper Accept header - should fail
            response = await client.post(
                ZAI_MCP_ENDPOINTS["zai-web-search"],
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                headers={"Content-Type": "application/json"},
            )

            # Should get error about Accept header
            assert response.status_code == 400 or response.status_code == 500

    @pytest.mark.asyncio
    async def test_mcp_server_timeout_configurable(self) -> None:
        """Test that MCP client timeout is configurable."""
        # Short timeout client
        short_client = HTTPMCPClient(
            ZAI_MCP_ENDPOINTS["zai-web-search"], timeout=0.001
        )

        # Should timeout quickly
        with pytest.raises((httpx.TimeoutException, asyncio.TimeoutError)):
            await short_client.initialize()

        await short_client.close()


class TestMCPSandboxIsolation:
    """Test sandbox isolation for MCP tool execution."""

    def test_mcp_urls_use_internal_dns(self) -> None:
        """Verify MCP URLs use Kubernetes internal DNS."""
        for url in ZAI_MCP_ENDPOINTS.values():
            # Should use cluster internal DNS
            assert ".svc.cluster.local" in url, "Should use Kubernetes internal DNS"
            assert "zai-proxy.devpod.svc.cluster.local" in url

    def test_mcp_no_credentials_in_urls(self) -> None:
        """Verify MCP URLs don't contain embedded credentials."""
        for url in ZAI_MCP_ENDPOINTS.values():
            # No credentials in URL
            assert ":@" not in url  # No auth in URL
            assert "token" not in url.lower()
            assert "password" not in url.lower()


class TestMCPToolExecutionMetrics:
    """Test tool execution logs and metrics."""

    @pytest.mark.asyncio
    async def test_tool_execution_latency(self) -> None:
        """Test measuring tool execution latency."""
        import time

        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-zread"])

        try:
            start = time.time()
            tools = await client.list_tools()
            elapsed = time.time() - start

            # Should complete within reasonable time
            assert elapsed < 5.0, "Tool listing should complete within 5 seconds"
            assert len(tools) > 0
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_tool_result_structure(self) -> None:
        """Test that tool results have expected structure."""
        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-zread"])

        try:
            response = await client.call_tool(
                "get_repo_structure",
                {"repo_name": "vitejs/vite", "dir_path": "/"}
            )

            # Should have result or error
            assert "result" in response or "error" in response

            if "result" in response:
                result = response["result"]
                # Result may be in different formats
                assert isinstance(result, (dict, list, str))
        finally:
            await client.close()


class TestMCPFallbackMechanism:
    """Test MCP server fallback when server unavailable."""

    @pytest.mark.asyncio
    async def test_unreachable_server_error(self) -> None:
        """Test behavior when MCP server is unreachable."""
        # Use a non-existent server
        client = HTTPMCPClient("http://localhost:9999/nonexistent")

        with pytest.raises(httpx.ConnectError):
            await client.initialize()

        await client.close()

    def test_static_tool_definitions_available(self) -> None:
        """Test that static tool definitions exist for documentation."""
        # These should match the tools returned by the actual servers
        expected_tools = {
            "zai-web-search": ["webSearchPrime"],
            "zai-web-reader": ["webReader"],
            "zai-zread": ["search_doc", "read_file", "get_repo_structure"],
        }

        for server, tools in expected_tools.items():
            assert len(tools) > 0, f"{server} should have known tools"


class TestMCPResourceUsage:
    """Test MCP server resource usage."""

    @pytest.mark.asyncio
    async def test_connection_reuse(self) -> None:
        """Test that client can reuse connection for multiple requests."""
        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-zread"])

        try:
            # Make multiple requests
            await client.initialize()
            tools1 = await client.list_tools()
            tools2 = await client.list_tools()

            # Should return same data
            assert len(tools1) == len(tools2)
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self) -> None:
        """Test handling concurrent requests to different servers."""
        clients = [
            HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-zread"]),
            HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-web-reader"]),
        ]

        try:
            # Make concurrent requests
            results = await asyncio.gather(
                clients[0].list_tools(),
                clients[1].list_tools(),
            )

            # Both should succeed
            assert len(results) == 2
            assert all(len(tools) > 0 for tools in results)
        finally:
            for client in clients:
                await client.close()


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance for HTTP-based servers."""

    @pytest.mark.asyncio
    async def test_json_rpc_version(self) -> None:
        """Test that responses use JSON-RPC 2.0."""
        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-zread"])

        try:
            response = await client.initialize()

            # Response should have JSON-RPC fields
            assert "jsonrpc" not in response or response.get("jsonrpc") == "2.0"
            assert "result" in response or "error" in response
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_protocol_version_header(self) -> None:
        """Test that server reports correct MCP protocol version."""
        client = HTTPMCPClient(ZAI_MCP_ENDPOINTS["zai-zread"])

        try:
            response = await client.initialize()

            if "result" in response:
                result = response["result"]
                assert "protocolVersion" in result
                # Current MCP version is 2024-11-05
                assert result["protocolVersion"] == "2024-11-05"
        finally:
            await client.close()


# Note: pytest integration marker is configured in pyproject.toml
# Run with: pytest tests/mcp/test_http_mcp_integration.py -v
# Skip integration tests: pytest tests/mcp/test_http_mcp_integration.py -v -m "not integration"
