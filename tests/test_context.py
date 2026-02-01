"""Tests for context builder."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from botburrow_agents.models import (
    AgentConfig,
    Notification,
    Thread,
)
from botburrow_agents.runner.context import (
    CORE_TOOLS,
    HUB_TOOLS,
    ContextBuilder,
)


class TestContextBuilder:
    """Tests for ContextBuilder."""

    @pytest.fixture
    def mock_hub(self, thread: Thread) -> AsyncMock:
        """Mock Hub client."""
        mock = AsyncMock()
        mock.get_thread.return_value = thread
        mock.get_discovery_feed.return_value = []
        return mock

    @pytest.fixture
    def mock_r2(self) -> AsyncMock:
        """Mock R2 client."""
        return AsyncMock()

    @pytest.fixture
    def builder(self, mock_hub: AsyncMock, mock_r2: AsyncMock) -> ContextBuilder:
        """Create context builder."""
        return ContextBuilder(mock_hub, mock_r2)

    @pytest.mark.asyncio
    async def test_build_for_notification(
        self,
        builder: ContextBuilder,
        agent_config: AgentConfig,
        notification: Notification,
    ) -> None:
        """Test building context for notification."""
        context = await builder.build_for_notification(agent_config, notification)

        # Should have system prompt
        assert len(context.messages) >= 2
        assert context.messages[0].role == "system"

        # Should have thread context
        assert any("Thread Context" in m.content for m in context.messages)

        # Should have notification info
        assert any("Notification" in m.content for m in context.messages)

        # Should have tools
        assert len(context.tools) > 0

    @pytest.mark.asyncio
    async def test_build_for_exploration(
        self,
        builder: ContextBuilder,
        agent_config: AgentConfig,
    ) -> None:
        """Test building context for exploration."""
        context = await builder.build_for_exploration(agent_config)

        # Should have system prompt
        assert len(context.messages) >= 2
        assert context.messages[0].role == "system"

        # Should have exploration instructions
        assert any("exploring" in m.content.lower() for m in context.messages)

        # Should have tools
        assert len(context.tools) > 0

    def test_get_tools_includes_hub(
        self, builder: ContextBuilder, agent_config: AgentConfig
    ) -> None:
        """Test Hub tools are included."""
        tools = builder._get_tools(agent_config)
        tool_names = [t["name"] for t in tools]

        assert "hub_post" in tool_names
        assert "hub_search" in tool_names
        assert "hub_get_thread" in tool_names

    def test_get_tools_includes_core(
        self, builder: ContextBuilder, agent_config: AgentConfig
    ) -> None:
        """Test core tools included for coding agents."""
        tools = builder._get_tools(agent_config)
        tool_names = [t["name"] for t in tools]

        for core_tool in ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]:
            assert core_tool in tool_names

    def test_format_thread(self, builder: ContextBuilder, thread: Thread) -> None:
        """Test thread formatting."""
        formatted = builder._format_thread(thread)

        assert thread.root.author_name in formatted
        assert thread.root.content in formatted
        for comment in thread.comments:
            assert comment.content in formatted

    def test_format_notification(self, builder: ContextBuilder, notification: Notification) -> None:
        """Test notification formatting."""
        formatted = builder._format_notification(notification)

        assert notification.from_agent_name in formatted
        assert notification.content in formatted
        assert "mentioned" in formatted.lower()

    def test_grant_to_tools_github(self, builder: ContextBuilder) -> None:
        """Test GitHub grant produces tools."""
        tools = builder._grant_to_tools("github:read")
        tool_names = [t["name"] for t in tools]

        assert "mcp_github_get_file" in tool_names
        assert "mcp_github_list_prs" in tool_names

    def test_grant_to_tools_github_write(self, builder: ContextBuilder) -> None:
        """Test GitHub write grant produces create tools."""
        tools = builder._grant_to_tools("github:write")
        tool_names = [t["name"] for t in tools]

        assert "mcp_github_create_pr" in tool_names
        assert "mcp_github_create_issue" in tool_names


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_core_tools_valid(self) -> None:
        """Test core tools have required fields."""
        for tool in CORE_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "type" in tool["parameters"]
            assert tool["parameters"]["type"] == "object"

    def test_hub_tools_valid(self) -> None:
        """Test Hub tools have required fields."""
        for tool in HUB_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "required" in tool["parameters"]
