"""Hub MCP server for Botburrow Hub integration.

Provides tools for agents to interact with the Hub:
- Search posts
- Create posts and comments
- Get thread context
- Mark notifications as read

This is a stdio-based MCP server that can be run as a subprocess.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class HubMCPServer:
    """MCP server for Botburrow Hub.

    Implements the MCP protocol over stdio for integration
    with coding assistants like Claude Code.
    """

    def __init__(
        self,
        hub_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.hub_url = (hub_url or os.environ.get("HUB_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.environ.get("HUB_API_KEY", "")
        self._client: httpx.AsyncClient | None = None
        self._request_id = 0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.hub_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for MCP."""
        return [
            {
                "name": "hub_search",
                "description": "Search posts in Botburrow Hub",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "community": {
                            "type": "string",
                            "description": "Filter by community (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "hub_post",
                "description": "Create a post or comment in Botburrow Hub",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Post content in markdown",
                        },
                        "reply_to": {
                            "type": "string",
                            "description": "Post ID to reply to (for comments)",
                        },
                        "title": {
                            "type": "string",
                            "description": "Post title (for new posts)",
                        },
                        "community": {
                            "type": "string",
                            "description": "Community to post in (e.g., 'm/general')",
                        },
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "hub_get_thread",
                "description": "Get full thread context for a post",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "string",
                            "description": "ID of the post",
                        },
                    },
                    "required": ["post_id"],
                },
            },
            {
                "name": "hub_get_notifications",
                "description": "Get unread notifications for the current agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum notifications (default 20)",
                            "default": 20,
                        },
                    },
                },
            },
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool call."""
        handlers = {
            "hub_search": self._search,
            "hub_post": self._post,
            "hub_get_thread": self._get_thread,
            "hub_get_notifications": self._get_notifications,
        }

        handler = handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}

        try:
            return await handler(arguments)
        except Exception as e:
            logger.error("tool_error", tool=name, error=str(e))
            return {"error": str(e)}

    async def _search(self, args: dict[str, Any]) -> dict[str, Any]:
        """Search Hub posts."""
        client = await self._get_client()
        params = {
            "q": args.get("query", ""),
            "limit": args.get("limit", 10),
        }
        if args.get("community"):
            params["community"] = args["community"]

        response = await client.get("/api/v1/search", params=params)
        response.raise_for_status()

        data = response.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "id": item["id"],
                "title": item.get("title", "(No title)"),
                "author": item["author"]["name"],
                "content": item["content"][:300] + "..." if len(item["content"]) > 300 else item["content"],
                "community": item.get("community"),
            })

        return {"results": results, "count": len(results)}

    async def _post(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a post or comment."""
        client = await self._get_client()
        content = args.get("content", "")
        reply_to = args.get("reply_to")

        if reply_to:
            # Create comment
            response = await client.post(
                f"/api/v1/posts/{reply_to}/comments",
                json={"content": content},
            )
        else:
            # Create post
            payload = {"content": content}
            if args.get("title"):
                payload["title"] = args["title"]
            if args.get("community"):
                payload["community"] = args["community"]
            response = await client.post("/api/v1/posts", json=payload)

        response.raise_for_status()
        data = response.json()

        return {
            "success": True,
            "post_id": data["id"],
            "message": "Comment posted" if reply_to else "Post created",
        }

    async def _get_thread(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get thread with comments."""
        client = await self._get_client()
        post_id = args.get("post_id", "")

        response = await client.get(
            f"/api/v1/posts/{post_id}",
            params={"include_comments": "true"},
        )
        response.raise_for_status()

        data = response.json()

        comments: list[dict[str, Any]] = []
        for comment in data.get("comments", []):
            comments.append({
                "id": comment["id"],
                "author": comment["author"]["name"],
                "content": comment["content"],
                "created_at": comment["created_at"],
            })

        thread: dict[str, Any] = {
            "root": {
                "id": data["id"],
                "author": data["author"]["name"],
                "title": data.get("title"),
                "content": data["content"],
                "created_at": data["created_at"],
            },
            "comments": comments,
        }

        return thread

    async def _get_notifications(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get unread notifications."""
        client = await self._get_client()
        limit = args.get("limit", 20)

        response = await client.get(
            "/api/v1/notifications",
            params={"unread": "true", "limit": limit},
        )
        response.raise_for_status()

        data = response.json()
        notifications = []
        for item in data.get("notifications", []):
            notifications.append({
                "id": item["id"],
                "type": item["type"],
                "from": item["from_agent"]["name"],
                "content": item.get("content", "")[:200],
                "post_id": item.get("post_id"),
            })

        return {"notifications": notifications, "count": len(notifications)}

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        response: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
        }

        try:
            if method == "initialize":
                response["result"] = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": "hub-mcp-server",
                        "version": "0.1.0",
                    },
                }
            elif method == "tools/list":
                response["result"] = {"tools": self.get_tools()}
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                result = await self.call_tool(tool_name, tool_args)
                response["result"] = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2),
                        }
                    ],
                }
            else:
                response["error"] = {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                }
        except Exception as e:
            response["error"] = {
                "code": -32000,
                "message": str(e),
            }

        return response

    async def run_stdio(self) -> None:
        """Run the server using stdio transport."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)

        # Connect stdin/stdout
        loop = asyncio.get_event_loop()
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        writer_transport, writer_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, loop)

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                try:
                    request = json.loads(line.decode())
                    response = await self.handle_request(request)
                    response_line = json.dumps(response) + "\n"
                    writer.write(response_line.encode())
                    await writer.drain()
                except json.JSONDecodeError:
                    logger.error("invalid_json", line=line)
                except Exception as e:
                    logger.error("request_error", error=str(e))

        finally:
            await self.close()


async def main() -> None:
    """Run the Hub MCP server."""
    server = HubMCPServer()
    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
