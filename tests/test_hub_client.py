"""Tests for Hub API client."""

from __future__ import annotations

import httpx
import pytest
import respx

from botburrow_agents.clients.hub import HubClient
from botburrow_agents.config import Settings
from botburrow_agents.models import NotificationType, TaskType


class TestHubClientInit:
    """Tests for HubClient initialization."""

    def test_init_with_settings(self, settings: Settings) -> None:
        """Test initialization with settings."""
        client = HubClient(settings)

        assert client.base_url == settings.hub_url
        assert client.settings == settings

    def test_init_without_settings(self) -> None:
        """Test initialization without explicit settings."""
        client = HubClient()

        assert client.base_url is not None


class TestHubClientNotifications:
    """Tests for notification methods."""

    @pytest.fixture
    def hub_client(self, settings: Settings) -> HubClient:
        """Create Hub client."""
        return HubClient(settings)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_notifications(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test getting notifications."""
        respx.get(f"{settings.hub_url}/api/v1/notifications").mock(
            return_value=httpx.Response(
                200,
                json={
                    "notifications": [
                        {
                            "id": "notif-1",
                            "type": "mention",
                            "post_id": "post-123",
                            "from_agent": {"id": "agent-1", "name": "Agent One"},
                            "content": "@test mentioned you",
                            "created_at": "2026-01-01T00:00:00Z",
                            "read": False,
                        }
                    ]
                },
            )
        )

        notifications = await hub_client.get_notifications("test-agent")

        assert len(notifications) == 1
        assert notifications[0].id == "notif-1"
        assert notifications[0].type == NotificationType.MENTION
        assert notifications[0].from_agent == "agent-1"

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_mark_notifications_read(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test marking notifications as read."""
        respx.post(f"{settings.hub_url}/api/v1/notifications/read").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        await hub_client.mark_notifications_read(["notif-1", "notif-2"])
        # Should complete without error

        await hub_client.close()


class TestHubClientPosts:
    """Tests for post-related methods."""

    @pytest.fixture
    def hub_client(self, settings: Settings) -> HubClient:
        """Create Hub client."""
        return HubClient(settings)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_post(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test getting a single post."""
        respx.get(f"{settings.hub_url}/api/v1/posts/post-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "post-123",
                    "author": {"id": "author-1", "name": "Author"},
                    "title": "Test Post",
                    "content": "This is a test post",
                    "community": "m/general",
                    "created_at": "2026-01-01T00:00:00Z",
                },
            )
        )

        post = await hub_client.get_post("post-123")

        assert post.id == "post-123"
        assert post.title == "Test Post"
        assert post.author_name == "Author"

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_thread(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test getting a thread with comments."""
        respx.get(f"{settings.hub_url}/api/v1/posts/post-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "post-123",
                    "author": {"id": "author-1", "name": "Author"},
                    "title": "Test Post",
                    "content": "This is a test post",
                    "created_at": "2026-01-01T00:00:00Z",
                    "comments": [
                        {
                            "id": "comment-1",
                            "author": {"id": "commenter", "name": "Commenter"},
                            "content": "Great post!",
                            "created_at": "2026-01-01T01:00:00Z",
                        }
                    ],
                },
            )
        )

        thread = await hub_client.get_thread("post-123")

        assert thread.root.id == "post-123"
        assert len(thread.comments) == 1
        assert thread.comments[0].content == "Great post!"

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_post(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test creating a new post."""
        respx.post(f"{settings.hub_url}/api/v1/posts").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "new-post-1",
                    "author": {"id": "agent-1", "name": "Agent"},
                    "created_at": "2026-01-01T00:00:00Z",
                },
            )
        )

        post = await hub_client.create_post(
            agent_id="agent-1",
            content="New post content",
            title="New Post",
            community="m/general",
        )

        assert post.id == "new-post-1"

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_comment(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test creating a comment."""
        respx.post(f"{settings.hub_url}/api/v1/posts/post-123/comments").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "comment-1",
                    "author": {"id": "agent-1", "name": "Agent"},
                    "created_at": "2026-01-01T00:00:00Z",
                },
            )
        )

        comment = await hub_client.create_comment(
            agent_id="agent-1",
            post_id="post-123",
            content="This is a comment",
        )

        assert comment.id == "comment-1"
        assert comment.parent_id == "post-123"

        await hub_client.close()


class TestHubClientSearch:
    """Tests for search methods."""

    @pytest.fixture
    def hub_client(self, settings: Settings) -> HubClient:
        """Create Hub client."""
        return HubClient(settings)

    @respx.mock
    @pytest.mark.asyncio
    async def test_search(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test searching posts."""
        respx.get(f"{settings.hub_url}/api/v1/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "post-1",
                            "author": {"id": "author-1", "name": "Author"},
                            "title": "Test",
                            "content": "Content with search term",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
            )
        )

        results = await hub_client.search("search term")

        assert len(results) == 1
        assert results[0].id == "post-1"

        await hub_client.close()


class TestHubClientBudget:
    """Tests for budget-related methods."""

    @pytest.fixture
    def hub_client(self, settings: Settings) -> HubClient:
        """Create Hub client."""
        return HubClient(settings)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_budget_health(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test getting budget health."""
        respx.get(f"{settings.hub_url}/api/v1/system/budget-health").mock(
            return_value=httpx.Response(
                200,
                json={
                    "daily_limit": 10.0,
                    "daily_used": 2.5,
                    "monthly_limit": 100.0,
                    "monthly_used": 25.0,
                    "healthy": True,
                },
            )
        )

        health = await hub_client.get_budget_health("agent-1")

        assert health.healthy
        assert health.daily_used == 2.5
        assert health.monthly_limit == 100.0

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_consumption(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test reporting consumption."""
        respx.post(f"{settings.hub_url}/api/v1/system/consumption").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        await hub_client.report_consumption(
            agent_id="agent-1",
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.05,
        )
        # Should complete without error

        await hub_client.close()


class TestHubClientAgents:
    """Tests for agent-related methods."""

    @pytest.fixture
    def hub_client(self, settings: Settings) -> HubClient:
        """Create Hub client."""
        return HubClient(settings)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_agents_with_notifications(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test getting agents with pending notifications."""
        respx.get(f"{settings.hub_url}/api/v1/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agents": [
                        {
                            "id": "agent-1",
                            "name": "Agent One",
                            "notification_count": 5,
                        },
                        {
                            "id": "agent-2",
                            "name": "Agent Two",
                            "notification_count": 2,
                        },
                    ]
                },
            )
        )

        assignments = await hub_client.get_agents_with_notifications()

        assert len(assignments) == 2
        # Should be sorted by notification count
        assert assignments[0].inbox_count == 5
        assert assignments[0].task_type == TaskType.INBOX

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_stale_agents(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test getting stale agents for exploration."""
        respx.get(f"{settings.hub_url}/api/v1/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agents": [
                        {
                            "id": "agent-1",
                            "name": "Agent One",
                            "last_activated_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
            )
        )

        assignments = await hub_client.get_stale_agents()

        assert len(assignments) == 1
        assert assignments[0].task_type == TaskType.DISCOVERY

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_agent_activation(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test updating agent activation timestamp."""
        respx.post(f"{settings.hub_url}/api/v1/agents/agent-1/activated").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        await hub_client.update_agent_activation("agent-1")
        # Should complete without error

        await hub_client.close()


class TestHubClientLongPoll:
    """Tests for long-poll notification methods."""

    @pytest.fixture
    def hub_client(self, settings: Settings) -> HubClient:
        """Create Hub client."""
        return HubClient(settings)

    @respx.mock
    @pytest.mark.asyncio
    async def test_poll_notifications_success(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test successful long-poll for notifications."""
        respx.get(f"{settings.hub_url}/api/v1/notifications/poll").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agents": [
                        {
                            "id": "agent-1",
                            "name": "Agent One",
                            "notification_count": 5,
                        },
                        {
                            "id": "agent-2",
                            "name": "Agent Two",
                            "notification_count": 2,
                        },
                    ]
                },
            )
        )

        assignments = await hub_client.poll_notifications(timeout=30)

        assert len(assignments) == 2
        # Should be sorted by notification count descending
        assert assignments[0].inbox_count == 5
        assert assignments[1].inbox_count == 2
        assert assignments[0].task_type == TaskType.INBOX

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_poll_notifications_timeout(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test long-poll timeout returns empty list."""
        respx.get(f"{settings.hub_url}/api/v1/notifications/poll").mock(
            side_effect=httpx.TimeoutException("timeout")
        )

        assignments = await hub_client.poll_notifications(timeout=1)

        assert assignments == []

        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_poll_notifications_fallback_to_regular(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test fallback to regular polling when endpoint not available."""
        # Long-poll endpoint returns 404
        respx.get(f"{settings.hub_url}/api/v1/notifications/poll").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        # Regular endpoint should be called as fallback
        respx.get(f"{settings.hub_url}/api/v1/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agents": [
                        {
                            "id": "agent-1",
                            "name": "Agent One",
                            "notification_count": 3,
                        }
                    ]
                },
            )
        )

        assignments = await hub_client.poll_notifications(timeout=30)

        assert len(assignments) == 1
        assert assignments[0].inbox_count == 3

        await hub_client.close()


class TestHubClientDiscovery:
    """Tests for discovery feed methods."""

    @pytest.fixture
    def hub_client(self, settings: Settings) -> HubClient:
        """Create Hub client."""
        return HubClient(settings)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_discovery_feed(
        self, hub_client: HubClient, settings: Settings
    ) -> None:
        """Test getting discovery feed."""
        respx.get(f"{settings.hub_url}/api/v1/feed/discover").mock(
            return_value=httpx.Response(
                200,
                json={
                    "posts": [
                        {
                            "id": "post-1",
                            "author": {"id": "author-1", "name": "Author"},
                            "title": "Interesting Post",
                            "content": "Interesting content",
                            "community": "m/general",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
            )
        )

        posts = await hub_client.get_discovery_feed(
            communities=["m/general"],
            exclude_responded=True,
            limit=10,
        )

        assert len(posts) == 1
        assert posts[0].title == "Interesting Post"

        await hub_client.close()
