"""Tests for context builder."""

from datetime import UTC, datetime

import pytest

from botburrow_agents.models import (
    Post,
    Thread,
)
from botburrow_agents.runner.context import ContextBuilder


class TestContextBuilder:
    """Tests for ContextBuilder class."""

    @pytest.fixture
    def context_builder(self, mock_hub_client, mock_git_client):
        """Create context builder with mocks."""
        return ContextBuilder(hub=mock_hub_client, git=mock_git_client)

    @pytest.mark.asyncio
    async def test_build_for_notification(
        self, context_builder, agent_config, notification, mock_hub_client
    ):
        """Test building context for notification."""
        # Set up mock thread
        mock_hub_client.get_thread.return_value = Thread(
            root=Post(
                id="post-1",
                author_id="user-1",
                author_name="User One",
                title="Help needed",
                content="Can someone help with this bug?",
                created_at=datetime.now(UTC),
            ),
            comments=[],
        )

        context = await context_builder.build_for_notification(agent_config, notification)

        # Should have system prompt
        assert len(context.messages) >= 2
        assert context.messages[0].role == "system"
        assert "test-agent" in context.messages[0].content.lower()

        # Should have thread context
        thread_msg = next((m for m in context.messages if "Thread Context" in m.content), None)
        assert thread_msg is not None
        assert "Help needed" in thread_msg.content

        # Should have notification
        notif_msg = next((m for m in context.messages if "New Notification" in m.content), None)
        assert notif_msg is not None
        assert notification.content in notif_msg.content

        # Should have tools
        assert len(context.tools) > 0

    @pytest.mark.asyncio
    async def test_build_for_exploration(self, context_builder, agent_config, mock_hub_client):
        """Test building context for exploration."""
        mock_hub_client.get_discovery_feed.return_value = [
            Post(
                id="post-1",
                author_id="user-1",
                author_name="User One",
                title="Interesting topic",
                content="Discussing something interesting...",
                created_at=datetime.now(UTC),
            ),
        ]

        context = await context_builder.build_for_exploration(agent_config)

        # Should have system prompt
        assert context.messages[0].role == "system"

        # Should have exploration instructions
        exploration_msg = next(
            (m for m in context.messages if "exploring" in m.content.lower()), None
        )
        assert exploration_msg is not None

        # Should have recent posts
        posts_msg = next((m for m in context.messages if "Recent Posts" in m.content), None)
        assert posts_msg is not None
        assert "Interesting topic" in posts_msg.content

    @pytest.mark.asyncio
    async def test_tools_include_hub_tools(
        self, context_builder, agent_config, notification, mock_hub_client
    ):
        """Test that context includes hub tools."""
        mock_hub_client.get_thread.return_value = Thread(
            root=Post(
                id="p1",
                author_id="u1",
                author_name="U1",
                content="Test",
                created_at=datetime.now(UTC),
            ),
            comments=[],
        )

        context = await context_builder.build_for_notification(agent_config, notification)

        tool_names = [t["name"] for t in context.tools]
        assert "hub_post" in tool_names
        assert "hub_search" in tool_names

    @pytest.mark.asyncio
    async def test_tools_include_core_tools_for_coding_agent(
        self, context_builder, agent_config, notification, mock_hub_client
    ):
        """Test that coding agent gets core tools."""
        mock_hub_client.get_thread.return_value = Thread(
            root=Post(
                id="p1",
                author_id="u1",
                author_name="U1",
                content="Test",
                created_at=datetime.now(UTC),
            ),
            comments=[],
        )

        context = await context_builder.build_for_notification(agent_config, notification)

        tool_names = [t["name"] for t in context.tools]
        assert "Read" in tool_names
        assert "Write" in tool_names
        assert "Edit" in tool_names
        assert "Bash" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_tools_based_on_grants(
        self, context_builder, agent_config, notification, mock_hub_client
    ):
        """Test that MCP tools are added based on grants."""
        mock_hub_client.get_thread.return_value = Thread(
            root=Post(
                id="p1",
                author_id="u1",
                author_name="U1",
                content="Test",
                created_at=datetime.now(UTC),
            ),
            comments=[],
        )

        context = await context_builder.build_for_notification(agent_config, notification)

        tool_names = [t["name"] for t in context.tools]

        # Agent has github:read and github:write grants
        assert any("github" in name for name in tool_names)
