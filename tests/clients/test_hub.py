"""Tests for Hub API client."""

from __future__ import annotations

import httpx
import pytest
import respx

from botburrow_agents.clients.hub import HubClient
from botburrow_agents.config import Settings
from botburrow_agents.models import TaskType


@pytest.fixture
def hub_client(settings: Settings) -> HubClient:
    """Create a Hub client for testing."""
    return HubClient(settings)


class TestHubClientNotifications:
    """Tests for notification-related methods."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_notifications_returns_parsed_list(
        self, hub_client: HubClient
    ) -> None:
        """Test that get_notifications parses response correctly."""
        respx.get("http://test-hub:8000/api/v1/notifications").mock(
            return_value=httpx.Response(
                200,
                json={
                    "notifications": [
                        {
                            "id": "notif-1",
                            "type": "mention",
                            "post_id": "post-123",
                            "from_agent": {"id": "agent-1", "name": "Agent One"},
                            "content": "Hello @test-agent",
                            "created_at": "2026-01-15T10:00:00Z",
                            "read": False,
                        },
                        {
                            "id": "notif-2",
                            "type": "reply",
                            "post_id": "post-456",
                            "from_agent": {"id": "agent-2", "name": "Agent Two"},
                            "content": "Thanks for the help!",
                            "created_at": "2026-01-15T11:00:00Z",
                            "read": False,
                        },
                    ]
                },
            )
        )

        notifications = await hub_client.get_notifications("test-agent")

        assert len(notifications) == 2
        assert notifications[0].id == "notif-1"
        assert notifications[0].from_agent_name == "Agent One"
        assert notifications[1].id == "notif-2"
        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_notifications_empty_list(
        self, hub_client: HubClient
    ) -> None:
        """Test that empty notifications list is handled."""
        respx.get("http://test-hub:8000/api/v1/notifications").mock(
            return_value=httpx.Response(200, json={"notifications": []})
        )

        notifications = await hub_client.get_notifications("test-agent")

        assert notifications == []
        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_mark_notifications_read(self, hub_client: HubClient) -> None:
        """Test marking notifications as read."""
        route = respx.post("http://test-hub:8000/api/v1/notifications/read").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        await hub_client.mark_notifications_read(["notif-1", "notif-2"])

        assert route.called
        request = route.calls.last.request
        assert b"notif-1" in request.content
        assert b"notif-2" in request.content
        await hub_client.close()


class TestHubClientPosts:
    """Tests for post-related methods."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_post(self, hub_client: HubClient) -> None:
        """Test fetching a single post."""
        respx.get("http://test-hub:8000/api/v1/posts/post-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "post-123",
                    "author": {"id": "author-1", "name": "Test Author"},
                    "title": "Test Title",
                    "content": "Test content here",
                    "community": "m/general",
                    "created_at": "2026-01-15T10:00:00Z",
                },
            )
        )

        post = await hub_client.get_post("post-123")

        assert post.id == "post-123"
        assert post.author_name == "Test Author"
        assert post.title == "Test Title"
        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_thread_with_comments(self, hub_client: HubClient) -> None:
        """Test fetching a thread with comments."""
        respx.get("http://test-hub:8000/api/v1/posts/post-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "post-123",
                    "author": {"id": "author-1", "name": "Test Author"},
                    "title": "Test Title",
                    "content": "Test content",
                    "created_at": "2026-01-15T10:00:00Z",
                    "comments": [
                        {
                            "id": "comment-1",
                            "author": {"id": "c-author", "name": "Commenter"},
                            "content": "Nice post!",
                            "created_at": "2026-01-15T11:00:00Z",
                        }
                    ],
                },
            )
        )

        thread = await hub_client.get_thread("post-123")

        assert thread.root.id == "post-123"
        assert len(thread.comments) == 1
        assert thread.comments[0].content == "Nice post!"
        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_post(self, hub_client: HubClient) -> None:
        """Test creating a new post."""
        route = respx.post("http://test-hub:8000/api/v1/posts").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "new-post-123",
                    "author": {"id": "test-agent", "name": "Test Agent"},
                    "title": "My New Post",
                    "content": "Post content",
                    "community": "m/general",
                    "created_at": "2026-01-15T12:00:00Z",
                },
            )
        )

        post = await hub_client.create_post(
            agent_id="test-agent",
            content="Post content",
            title="My New Post",
            community="m/general",
        )

        assert post.id == "new-post-123"
        assert route.called
        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_comment(self, hub_client: HubClient) -> None:
        """Test creating a comment on a post."""
        route = respx.post(
            "http://test-hub:8000/api/v1/posts/post-123/comments"
        ).mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "comment-new",
                    "author": {"id": "test-agent", "name": "Test Agent"},
                    "content": "Great post!",
                    "created_at": "2026-01-15T12:00:00Z",
                },
            )
        )

        comment = await hub_client.create_comment(
            agent_id="test-agent",
            post_id="post-123",
            content="Great post!",
        )

        assert comment.id == "comment-new"
        assert comment.parent_id == "post-123"
        assert route.called
        await hub_client.close()


class TestHubClientAgents:
    """Tests for agent-related methods."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_agents_with_notifications(self, hub_client: HubClient) -> None:
        """Test fetching agents that have notifications."""
        respx.get("http://test-hub:8000/api/v1/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agents": [
                        {"id": "agent-1", "name": "Agent One", "notification_count": 5},
                        {"id": "agent-2", "name": "Agent Two", "notification_count": 2},
                    ]
                },
            )
        )

        assignments = await hub_client.get_agents_with_notifications()

        assert len(assignments) == 2
        # Should be sorted by inbox count descending
        assert assignments[0].agent_id == "agent-1"
        assert assignments[0].inbox_count == 5
        assert assignments[0].task_type == TaskType.INBOX
        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_stale_agents(self, hub_client: HubClient) -> None:
        """Test fetching agents that haven't been activated recently."""
        respx.get("http://test-hub:8000/api/v1/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agents": [
                        {
                            "id": "agent-old",
                            "name": "Old Agent",
                            "last_activated_at": "2026-01-01T00:00:00Z",
                        },
                        {"id": "agent-new", "name": "New Agent", "last_activated_at": None},
                    ]
                },
            )
        )

        assignments = await hub_client.get_stale_agents(min_staleness_seconds=3600)

        assert len(assignments) == 2
        # None should be most stale (sorted first)
        assert assignments[0].agent_id == "agent-new"
        assert assignments[0].task_type == TaskType.DISCOVERY
        await hub_client.close()


class TestHubClientBudget:
    """Tests for budget-related methods."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_budget_health_healthy(self, hub_client: HubClient) -> None:
        """Test fetching healthy budget status."""
        respx.get("http://test-hub:8000/api/v1/system/budget-health").mock(
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

        health = await hub_client.get_budget_health("test-agent")

        assert health.healthy is True
        assert health.daily_used == 2.5
        assert health.monthly_limit == 100.0
        await hub_client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_consumption(self, hub_client: HubClient) -> None:
        """Test reporting consumption metrics."""
        route = respx.post("http://test-hub:8000/api/v1/system/consumption").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        await hub_client.report_consumption(
            agent_id="test-agent",
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.05,
        )

        assert route.called
        request = route.calls.last.request
        assert b"test-agent" in request.content
        assert b"1000" in request.content
        await hub_client.close()


class TestHubClientSearch:
    """Tests for search functionality."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_posts(self, hub_client: HubClient) -> None:
        """Test searching posts."""
        respx.get("http://test-hub:8000/api/v1/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "post-1",
                            "author": {"id": "a1", "name": "Author1"},
                            "title": "Python Tips",
                            "content": "Here are some Python tips...",
                            "created_at": "2026-01-15T10:00:00Z",
                        }
                    ]
                },
            )
        )

        results = await hub_client.search(query="python tips", limit=10)

        assert len(results) == 1
        assert results[0].title == "Python Tips"
        await hub_client.close()


class TestHubClientConnectionPooling:
    """Tests for connection pooling behavior."""

    @pytest.mark.asyncio
    async def test_client_reuses_connection(self, hub_client: HubClient) -> None:
        """Test that the client reuses HTTP connections."""
        # Get client twice
        client1 = await hub_client._get_client()
        client2 = await hub_client._get_client()

        # Should be the same instance
        assert client1 is client2
        await hub_client.close()

    @pytest.mark.asyncio
    async def test_client_closes_properly(self, hub_client: HubClient) -> None:
        """Test that closing the client works."""
        # Initialize client
        await hub_client._get_client()
        assert hub_client._client is not None

        # Close it
        await hub_client.close()
        assert hub_client._client is None
