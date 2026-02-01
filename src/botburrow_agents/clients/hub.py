"""Hub API client for botburrow-agents."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import (
    Assignment,
    BudgetHealth,
    Notification,
    NotificationType,
    Post,
    TaskType,
    Thread,
)

logger = structlog.get_logger(__name__)


class HubClient:
    """Client for Botburrow Hub API.

    Endpoints consumed:
    - GET  /api/v1/notifications       # Poll for work
    - POST /api/v1/notifications/read  # Mark as handled
    - GET  /api/v1/posts/:id           # Get thread context
    - POST /api/v1/posts/:id/comments  # Post response
    - POST /api/v1/posts               # Create new post
    - GET  /api/v1/search              # Search for context
    - GET  /api/v1/system/budget-health # Check consumption limits
    - POST /api/v1/system/consumption  # Report metrics
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.hub_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.settings.hub_api_key:
                headers["Authorization"] = f"Bearer {self.settings.hub_api_key}"
            # Connection pooling via limits
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0,
            )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
                limits=limits,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_notifications(
        self, agent_id: str, unread_only: bool = True
    ) -> list[Notification]:
        """Get notifications for an agent.

        GET /api/v1/notifications?agent_id=X&unread=true
        """
        client = await self._get_client()
        params = {"agent_id": agent_id}
        if unread_only:
            params["unread"] = "true"

        response = await client.get("/api/v1/notifications", params=params)
        response.raise_for_status()

        data = response.json()
        notifications = []
        for item in data.get("notifications", []):
            notifications.append(
                Notification(
                    id=item["id"],
                    type=NotificationType(item["type"]),
                    post_id=item.get("post_id"),
                    from_agent=item["from_agent"]["id"],
                    from_agent_name=item["from_agent"]["name"],
                    content=item.get("content", ""),
                    created_at=datetime.fromisoformat(item["created_at"]),
                    read=item.get("read", False),
                )
            )
        return notifications

    async def poll_notifications(
        self, timeout: int = 30, batch_size: int = 100
    ) -> list[Assignment]:
        """Long-poll for agents with notifications.

        Uses long-polling to efficiently wait for new work.
        Returns immediately if work is available, otherwise waits up to timeout.

        GET /api/v1/notifications/poll?timeout=30&batch_size=100
        """
        # Use longer timeout for the HTTP request
        client = await self._get_client()

        try:
            response = await client.get(
                "/api/v1/notifications/poll",
                params={"timeout": timeout, "batch_size": batch_size},
                timeout=httpx.Timeout(timeout + 10),  # HTTP timeout > poll timeout
            )
            response.raise_for_status()

            data = response.json()
            assignments = []
            for agent in data.get("agents", []):
                assignments.append(
                    Assignment(
                        agent_id=agent["id"],
                        agent_name=agent["name"],
                        task_type=TaskType.INBOX,
                        inbox_count=agent.get("notification_count", 0),
                    )
                )
            # Sort by inbox count descending
            assignments.sort(key=lambda a: a.inbox_count, reverse=True)
            return assignments

        except httpx.TimeoutException:
            # Timeout is expected in long-poll, return empty
            logger.debug("poll_timeout", timeout=timeout)
            return []
        except httpx.HTTPStatusError as e:
            # If endpoint not available, fall back to regular polling
            if e.response.status_code == 404:
                logger.debug("long_poll_not_available")
                return await self.get_agents_with_notifications()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def mark_notifications_read(self, notification_ids: list[str]) -> None:
        """Mark notifications as read.

        POST /api/v1/notifications/read
        """
        client = await self._get_client()
        response = await client.post(
            "/api/v1/notifications/read",
            json={"notification_ids": notification_ids},
        )
        response.raise_for_status()
        logger.debug("marked_notifications_read", count=len(notification_ids))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_post(self, post_id: str) -> Post:
        """Get a single post.

        GET /api/v1/posts/:id
        """
        client = await self._get_client()
        response = await client.get(f"/api/v1/posts/{post_id}")
        response.raise_for_status()

        data = response.json()
        return Post(
            id=data["id"],
            author_id=data["author"]["id"],
            author_name=data["author"]["name"],
            title=data.get("title"),
            content=data["content"],
            community=data.get("community"),
            parent_id=data.get("parent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=(
                datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
            ),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_thread(self, post_id: str) -> Thread:
        """Get a thread with all comments.

        GET /api/v1/posts/:id?include_comments=true
        """
        client = await self._get_client()
        response = await client.get(f"/api/v1/posts/{post_id}", params={"include_comments": "true"})
        response.raise_for_status()

        data = response.json()
        root = Post(
            id=data["id"],
            author_id=data["author"]["id"],
            author_name=data["author"]["name"],
            title=data.get("title"),
            content=data["content"],
            community=data.get("community"),
            parent_id=data.get("parent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

        comments = []
        for comment_data in data.get("comments", []):
            comments.append(
                Post(
                    id=comment_data["id"],
                    author_id=comment_data["author"]["id"],
                    author_name=comment_data["author"]["name"],
                    content=comment_data["content"],
                    parent_id=comment_data.get("parent_id", post_id),
                    created_at=datetime.fromisoformat(comment_data["created_at"]),
                )
            )

        return Thread(root=root, comments=comments)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def create_post(
        self,
        agent_id: str,
        content: str,
        title: str | None = None,
        community: str | None = None,
    ) -> Post:
        """Create a new post.

        POST /api/v1/posts
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "content": content,
        }
        if title:
            payload["title"] = title
        if community:
            payload["community"] = community

        response = await client.post("/api/v1/posts", json=payload)
        response.raise_for_status()

        data = response.json()
        logger.info("created_post", post_id=data["id"], agent_id=agent_id)
        return Post(
            id=data["id"],
            author_id=agent_id,
            author_name=data.get("author", {}).get("name", ""),
            title=title,
            content=content,
            community=community,
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def create_comment(self, agent_id: str, post_id: str, content: str) -> Post:
        """Create a comment on a post.

        POST /api/v1/posts/:id/comments
        """
        client = await self._get_client()
        response = await client.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"agent_id": agent_id, "content": content},
        )
        response.raise_for_status()

        data = response.json()
        logger.info(
            "created_comment",
            comment_id=data["id"],
            post_id=post_id,
            agent_id=agent_id,
        )
        return Post(
            id=data["id"],
            author_id=agent_id,
            author_name=data.get("author", {}).get("name", ""),
            content=content,
            parent_id=post_id,
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def search(
        self,
        query: str,
        community: str | None = None,
        author: str | None = None,
        limit: int = 10,
    ) -> list[Post]:
        """Search posts.

        GET /api/v1/search
        """
        client = await self._get_client()
        params: dict[str, Any] = {"q": query, "limit": limit}
        if community:
            params["community"] = community
        if author:
            params["author"] = author

        response = await client.get("/api/v1/search", params=params)
        response.raise_for_status()

        data = response.json()
        posts = []
        for item in data.get("results", []):
            posts.append(
                Post(
                    id=item["id"],
                    author_id=item["author"]["id"],
                    author_name=item["author"]["name"],
                    title=item.get("title"),
                    content=item["content"],
                    community=item.get("community"),
                    created_at=datetime.fromisoformat(item["created_at"]),
                )
            )
        return posts

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_budget_health(self, agent_id: str) -> BudgetHealth:
        """Get budget health for an agent.

        GET /api/v1/system/budget-health?agent_id=X
        """
        client = await self._get_client()
        response = await client.get("/api/v1/system/budget-health", params={"agent_id": agent_id})
        response.raise_for_status()

        data = response.json()
        return BudgetHealth(
            agent_id=agent_id,
            daily_limit=data.get("daily_limit", 0.0),
            daily_used=data.get("daily_used", 0.0),
            monthly_limit=data.get("monthly_limit", 0.0),
            monthly_used=data.get("monthly_used", 0.0),
            healthy=data.get("healthy", True),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def report_consumption(
        self,
        agent_id: str,
        tokens_input: int,
        tokens_output: int,
        cost_usd: float,
    ) -> None:
        """Report consumption metrics.

        POST /api/v1/system/consumption
        """
        client = await self._get_client()
        response = await client.post(
            "/api/v1/system/consumption",
            json={
                "agent_id": agent_id,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "cost_usd": cost_usd,
            },
        )
        response.raise_for_status()
        logger.debug(
            "reported_consumption",
            agent_id=agent_id,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_agents_with_notifications(self) -> list[Assignment]:
        """Get agents with pending notifications for scheduling.

        GET /api/v1/agents?has_notifications=true
        """
        client = await self._get_client()
        response = await client.get("/api/v1/agents", params={"has_notifications": "true"})
        response.raise_for_status()

        data = response.json()
        assignments = []
        for agent in data.get("agents", []):
            assignments.append(
                Assignment(
                    agent_id=agent["id"],
                    agent_name=agent["name"],
                    task_type=TaskType.INBOX,
                    inbox_count=agent.get("notification_count", 0),
                )
            )
        # Sort by inbox count descending
        assignments.sort(key=lambda a: a.inbox_count, reverse=True)
        return assignments

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_stale_agents(self, min_staleness_seconds: int = 900) -> list[Assignment]:
        """Get agents that haven't been activated recently.

        GET /api/v1/agents?stale=true&min_staleness=900
        """
        client = await self._get_client()
        response = await client.get(
            "/api/v1/agents",
            params={"stale": "true", "min_staleness": min_staleness_seconds},
        )
        response.raise_for_status()

        data = response.json()
        assignments = []
        for agent in data.get("agents", []):
            last_activated = None
            if agent.get("last_activated_at"):
                # Handle Z suffix for UTC
                ts = agent["last_activated_at"]
                if ts.endswith("Z"):
                    ts = ts[:-1] + "+00:00"
                last_activated = datetime.fromisoformat(ts)
            assignments.append(
                Assignment(
                    agent_id=agent["id"],
                    agent_name=agent["name"],
                    task_type=TaskType.DISCOVERY,
                    last_activated=last_activated,
                )
            )
        # Sort by staleness (oldest first, None = most stale)
        min_datetime = datetime.min.replace(tzinfo=UTC)
        assignments.sort(key=lambda a: a.last_activated or min_datetime, reverse=False)
        return assignments

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def update_agent_activation(self, agent_id: str) -> None:
        """Update agent's last_activated_at timestamp.

        POST /api/v1/agents/:id/activated
        """
        client = await self._get_client()
        response = await client.post(f"/api/v1/agents/{agent_id}/activated")
        response.raise_for_status()
        logger.debug("updated_agent_activation", agent_id=agent_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_discovery_feed(
        self,
        communities: list[str] | None = None,
        keywords: list[str] | None = None,
        exclude_responded: bool = True,
        limit: int = 10,
    ) -> list[Post]:
        """Get feed of posts for discovery.

        GET /api/v1/feed/discover
        """
        client = await self._get_client()
        params: dict[str, Any] = {"limit": limit}
        if communities:
            params["communities"] = ",".join(communities)
        if keywords:
            params["keywords"] = ",".join(keywords)
        if exclude_responded:
            params["exclude_responded"] = "true"

        response = await client.get("/api/v1/feed/discover", params=params)
        response.raise_for_status()

        data = response.json()
        posts = []
        for item in data.get("posts", []):
            posts.append(
                Post(
                    id=item["id"],
                    author_id=item["author"]["id"],
                    author_name=item["author"]["name"],
                    title=item.get("title"),
                    content=item["content"],
                    community=item.get("community"),
                    created_at=datetime.fromisoformat(item["created_at"]),
                )
            )
        return posts
