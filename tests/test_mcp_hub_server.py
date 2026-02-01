"""Tests for the Hub MCP server."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botburrow_agents.mcp.servers.hub import HubMCPServer


class TestHubMCPServerInit:
    """Tests for HubMCPServer initialization."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        server = HubMCPServer()
        assert server.hub_url == "http://localhost:8000"
        assert server.api_key == ""

    def test_init_with_custom_url(self) -> None:
        """Test initialization with custom URL."""
        server = HubMCPServer(hub_url="http://custom:9000")
        assert server.hub_url == "http://custom:9000"

    def test_init_with_api_key(self) -> None:
        """Test initialization with API key."""
        server = HubMCPServer(api_key="test-key")
        assert server.api_key == "test-key"

    def test_url_trailing_slash_stripped(self) -> None:
        """Test that trailing slash is stripped from URL."""
        server = HubMCPServer(hub_url="http://example.com/")
        assert server.hub_url == "http://example.com"


class TestHubMCPServerTools:
    """Tests for tool definitions."""

    def test_get_tools_returns_list(self) -> None:
        """Test that get_tools returns a list."""
        server = HubMCPServer()
        tools = server.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 4

    def test_hub_search_tool_definition(self) -> None:
        """Test hub_search tool definition."""
        server = HubMCPServer()
        tools = server.get_tools()
        search_tool = next(t for t in tools if t["name"] == "hub_search")

        assert search_tool["description"] == "Search posts in Botburrow Hub"
        assert "query" in search_tool["inputSchema"]["properties"]
        assert "query" in search_tool["inputSchema"]["required"]

    def test_hub_post_tool_definition(self) -> None:
        """Test hub_post tool definition."""
        server = HubMCPServer()
        tools = server.get_tools()
        post_tool = next(t for t in tools if t["name"] == "hub_post")

        assert "content" in post_tool["inputSchema"]["properties"]
        assert "reply_to" in post_tool["inputSchema"]["properties"]
        assert "content" in post_tool["inputSchema"]["required"]

    def test_hub_get_thread_tool_definition(self) -> None:
        """Test hub_get_thread tool definition."""
        server = HubMCPServer()
        tools = server.get_tools()
        thread_tool = next(t for t in tools if t["name"] == "hub_get_thread")

        assert "post_id" in thread_tool["inputSchema"]["properties"]
        assert "post_id" in thread_tool["inputSchema"]["required"]

    def test_hub_get_notifications_tool_definition(self) -> None:
        """Test hub_get_notifications tool definition."""
        server = HubMCPServer()
        tools = server.get_tools()
        notif_tool = next(t for t in tools if t["name"] == "hub_get_notifications")

        assert "limit" in notif_tool["inputSchema"]["properties"]


class TestHubMCPServerSearch:
    """Tests for hub_search tool."""

    @pytest.fixture
    def server(self) -> HubMCPServer:
        """Create test server."""
        return HubMCPServer(hub_url="http://test:8000", api_key="test-key")

    async def test_search_success(self, server: HubMCPServer) -> None:
        """Test successful search."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "post-1",
                    "title": "Test Post",
                    "author": {"name": "Author"},
                    "content": "This is test content",
                    "community": "m/general",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(server, "_get_client", return_value=mock_client):
            result = await server._search({"query": "test", "limit": 10})

            assert result["count"] == 1
            assert result["results"][0]["id"] == "post-1"
            assert result["results"][0]["title"] == "Test Post"

    async def test_search_with_community_filter(self, server: HubMCPServer) -> None:
        """Test search with community filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(server, "_get_client", return_value=mock_client):
            await server._search({"query": "test", "community": "m/devops"})

            mock_client.get.assert_called_once()
            call_params = mock_client.get.call_args[1]["params"]
            assert call_params["community"] == "m/devops"

    async def test_search_truncates_long_content(self, server: HubMCPServer) -> None:
        """Test that search truncates long content."""
        long_content = "x" * 500

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "post-1",
                    "title": "Test",
                    "author": {"name": "Author"},
                    "content": long_content,
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(server, "_get_client", return_value=mock_client):
            result = await server._search({"query": "test"})

            assert len(result["results"][0]["content"]) == 303  # 300 + "..."


class TestHubMCPServerPost:
    """Tests for hub_post tool."""

    @pytest.fixture
    def server(self) -> HubMCPServer:
        """Create test server."""
        return HubMCPServer(hub_url="http://test:8000", api_key="test-key")

    async def test_post_new_post(self, server: HubMCPServer) -> None:
        """Test creating a new post."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new-post-id"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(server, "_get_client", return_value=mock_client):
            result = await server._post({
                "content": "New post content",
                "title": "New Title",
                "community": "m/general",
            })

            assert result["success"] is True
            assert result["post_id"] == "new-post-id"
            assert result["message"] == "Post created"
            mock_client.post.assert_called_once_with(
                "/api/v1/posts",
                json={
                    "content": "New post content",
                    "title": "New Title",
                    "community": "m/general",
                },
            )

    async def test_post_reply(self, server: HubMCPServer) -> None:
        """Test creating a reply/comment."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "comment-id"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(server, "_get_client", return_value=mock_client):
            result = await server._post({
                "content": "Reply content",
                "reply_to": "parent-post-id",
            })

            assert result["success"] is True
            assert result["message"] == "Comment posted"
            mock_client.post.assert_called_once_with(
                "/api/v1/posts/parent-post-id/comments",
                json={"content": "Reply content"},
            )


class TestHubMCPServerThread:
    """Tests for hub_get_thread tool."""

    @pytest.fixture
    def server(self) -> HubMCPServer:
        """Create test server."""
        return HubMCPServer(hub_url="http://test:8000", api_key="test-key")

    async def test_get_thread(self, server: HubMCPServer) -> None:
        """Test getting a thread."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "post-123",
            "author": {"name": "Author"},
            "title": "Thread Title",
            "content": "Root post content",
            "created_at": "2026-01-15T12:00:00Z",
            "comments": [
                {
                    "id": "comment-1",
                    "author": {"name": "Commenter"},
                    "content": "First comment",
                    "created_at": "2026-01-15T12:05:00Z",
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(server, "_get_client", return_value=mock_client):
            result = await server._get_thread({"post_id": "post-123"})

            assert result["root"]["id"] == "post-123"
            assert result["root"]["author"] == "Author"
            assert len(result["comments"]) == 1
            assert result["comments"][0]["content"] == "First comment"


class TestHubMCPServerNotifications:
    """Tests for hub_get_notifications tool."""

    @pytest.fixture
    def server(self) -> HubMCPServer:
        """Create test server."""
        return HubMCPServer(hub_url="http://test:8000", api_key="test-key")

    async def test_get_notifications(self, server: HubMCPServer) -> None:
        """Test getting notifications."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "notifications": [
                {
                    "id": "notif-1",
                    "type": "mention",
                    "from_agent": {"name": "SomeAgent"},
                    "content": "Hey @test-agent!",
                    "post_id": "post-123",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(server, "_get_client", return_value=mock_client):
            result = await server._get_notifications({"limit": 20})

            assert result["count"] == 1
            assert result["notifications"][0]["id"] == "notif-1"
            assert result["notifications"][0]["from"] == "SomeAgent"


class TestHubMCPServerToolCall:
    """Tests for the call_tool method."""

    @pytest.fixture
    def server(self) -> HubMCPServer:
        """Create test server."""
        return HubMCPServer(hub_url="http://test:8000", api_key="test-key")

    async def test_call_tool_search(self, server: HubMCPServer) -> None:
        """Test calling hub_search tool."""
        with patch.object(server, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"results": [], "count": 0}

            result = await server.call_tool("hub_search", {"query": "test"})

            assert result["count"] == 0
            mock_search.assert_called_once_with({"query": "test"})

    async def test_call_tool_post(self, server: HubMCPServer) -> None:
        """Test calling hub_post tool."""
        with patch.object(server, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"success": True, "post_id": "123"}

            result = await server.call_tool("hub_post", {"content": "Hello"})

            assert result["success"] is True
            mock_post.assert_called_once()

    async def test_call_tool_unknown(self, server: HubMCPServer) -> None:
        """Test calling unknown tool."""
        result = await server.call_tool("unknown_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    async def test_call_tool_error_handling(self, server: HubMCPServer) -> None:
        """Test error handling in call_tool."""
        with patch.object(server, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("API Error")

            result = await server.call_tool("hub_search", {"query": "test"})

            assert "error" in result
            assert "API Error" in result["error"]


class TestHubMCPServerJSONRPC:
    """Tests for JSON-RPC request handling."""

    @pytest.fixture
    def server(self) -> HubMCPServer:
        """Create test server."""
        return HubMCPServer(hub_url="http://test:8000", api_key="test-key")

    async def test_handle_initialize(self, server: HubMCPServer) -> None:
        """Test initialize request."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }

        response = await server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "protocolVersion" in response["result"]
        assert response["result"]["serverInfo"]["name"] == "hub-mcp-server"

    async def test_handle_tools_list(self, server: HubMCPServer) -> None:
        """Test tools/list request."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        response = await server.handle_request(request)

        assert response["id"] == 2
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 4

    async def test_handle_tools_call(self, server: HubMCPServer) -> None:
        """Test tools/call request."""
        with patch.object(server, "call_tool", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"results": [], "count": 0}

            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "hub_search",
                    "arguments": {"query": "test"},
                },
            }

            response = await server.handle_request(request)

            assert response["id"] == 3
            assert "content" in response["result"]
            assert response["result"]["content"][0]["type"] == "text"

    async def test_handle_unknown_method(self, server: HubMCPServer) -> None:
        """Test unknown method returns error."""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "unknown/method",
            "params": {},
        }

        response = await server.handle_request(request)

        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]

    async def test_handle_error_propagation(self, server: HubMCPServer) -> None:
        """Test that errors are properly propagated."""
        with patch.object(server, "get_tools", side_effect=Exception("Unexpected")):
            request = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/list",
                "params": {},
            }

            response = await server.handle_request(request)

            assert "error" in response
            assert response["error"]["code"] == -32000


class TestHubMCPServerClient:
    """Tests for HTTP client management."""

    async def test_get_client_creates_client(self) -> None:
        """Test that _get_client creates a client."""
        server = HubMCPServer(hub_url="http://test:8000", api_key="test-key")

        client = await server._get_client()

        assert client is not None
        assert client.base_url.host == "test"
        await server.close()

    async def test_get_client_reuses_client(self) -> None:
        """Test that _get_client reuses existing client."""
        server = HubMCPServer(hub_url="http://test:8000")

        client1 = await server._get_client()
        client2 = await server._get_client()

        assert client1 is client2
        await server.close()

    async def test_close_closes_client(self) -> None:
        """Test that close properly closes client."""
        server = HubMCPServer(hub_url="http://test:8000")

        await server._get_client()
        assert server._client is not None

        await server.close()
        assert server._client is None
