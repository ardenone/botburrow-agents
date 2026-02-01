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

    @pytest.mark.asyncio
    async def test_build_for_exploration_empty_feed(
        self, context_builder, agent_config, mock_hub_client
    ):
        """Test exploration with empty feed."""
        mock_hub_client.get_discovery_feed.return_value = []

        context = await context_builder.build_for_exploration(agent_config)

        # Should have message about no posts
        empty_msg = next((m for m in context.messages if "No new posts" in m.content), None)
        assert empty_msg is not None

    @pytest.mark.asyncio
    async def test_format_thread(self, context_builder):
        """Test thread formatting."""
        thread = Thread(
            root=Post(
                id="p1",
                author_id="u1",
                author_name="User One",
                title="Test Thread",
                content="Main post content",
                created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            ),
            comments=[
                Post(
                    id="c1",
                    author_id="u2",
                    author_name="User Two",
                    content="First comment",
                    parent_id="p1",
                    created_at=datetime(2025, 1, 1, 12, 30, 0, tzinfo=UTC),
                )
            ],
        )

        formatted = context_builder._format_thread(thread)

        assert "User One" in formatted
        assert "Test Thread" in formatted
        assert "Main post content" in formatted
        assert "User Two" in formatted
        assert "First comment" in formatted

    @pytest.mark.asyncio
    async def test_format_notification(self, context_builder, notification):
        """Test notification formatting."""
        formatted = context_builder._format_notification(notification)

        assert "You were mentioned" in formatted
        assert "Other Agent" in formatted
        assert notification.content in formatted

    @pytest.mark.asyncio
    async def test_format_feed(self, context_builder):
        """Test feed formatting."""
        posts = [
            Post(
                id="p1",
                author_id="u1",
                author_name="User One",
                title="Post 1",
                content="Content 1" * 100,  # Long content to test truncation
                community="m/general",
                created_at=datetime.now(UTC),
            ),
            Post(
                id="p2",
                author_id="u2",
                author_name="User Two",
                title="Post 2",
                content="Content 2",
                community="m/dev",
                created_at=datetime.now(UTC),
            ),
        ]

        formatted = context_builder._format_feed(posts)

        assert "Post 1" in formatted
        assert "Post 2" in formatted
        assert "..." in formatted  # Truncation indicator

    @pytest.mark.asyncio
    async def test_build_exploration_prompt(self, context_builder, agent_config):
        """Test exploration prompt building."""
        prompt = context_builder._build_exploration_prompt(agent_config)

        assert agent_config.name in prompt
        assert "exploring" in prompt.lower()
        assert str(agent_config.behavior.max_daily_posts) in prompt
        assert str(agent_config.behavior.max_daily_comments) in prompt

    @pytest.mark.asyncio
    async def test_aws_tools(self, context_builder):
        """Test AWS tool generation."""
        tools = context_builder._aws_tools(["aws", "s3", "read"])

        tool_names = [t["name"] for t in tools]
        assert "mcp_aws_s3_get" in tool_names

        # Test write access
        tools_write = context_builder._aws_tools(["aws", "s3", "write"])
        tool_names_write = [t["name"] for t in tools_write]
        assert "mcp_aws_s3_put" in tool_names_write

        # Test invalid/short parts
        tools_empty = context_builder._aws_tools(["aws"])
        assert tools_empty == []

    @pytest.mark.asyncio
    async def test_postgres_tools(self, context_builder):
        """Test PostgreSQL tool generation."""
        tools = context_builder._postgres_tools(["postgres", "mydb", "read"])

        assert len(tools) == 1
        assert "mydb" in tools[0]["name"]
        assert "query" in tools[0]["name"].lower()
        assert tools[0]["parameters"]["properties"]["query"]["type"] == "string"

        # Test invalid/short parts
        tools_empty = context_builder._postgres_tools(["postgres"])
        assert tools_empty == []

    @pytest.mark.asyncio
    async def test_non_coding_agent_no_core_tools(
        self, context_builder, agent_config, notification, mock_hub_client
    ):
        """Test that non-coding agents don't get core tools."""
        agent_config.type = "native"  # Native agents don't get core tools by default in _get_tools

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

        # Create a native-type agent (which doesn't get core tools)
        from botburrow_agents.models import AgentConfig, BrainConfig

        native_agent = AgentConfig(
            name="native-agent",
            type="builtin",  # Not a coding agent type
            brain=BrainConfig(),
            capabilities=agent_config.capabilities,
            behavior=agent_config.behavior,
        )

        context = await context_builder.build_for_notification(native_agent, notification)

        tool_names = [t["name"] for t in context.tools]

        # Should have hub tools but not core tools
        assert "hub_post" in tool_names
        # Native agents don't get core tools
        assert "Read" not in tool_names
