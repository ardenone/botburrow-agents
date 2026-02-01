"""Tests for the agentic loop implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.models import (
    Action,
    AgentConfig,
    BehaviorConfig,
    BrainConfig,
    CapabilityGrants,
    Context,
    Message,
    Post,
    Thread,
    ToolCall,
    ToolResult,
)
from botburrow_agents.runner.loop import AgentLoop


@pytest.fixture
def settings() -> Settings:
    """Test settings."""
    return Settings(
        hub_url="http://test-hub:8000",
        hub_api_key="test-key",
        redis_url="redis://localhost:6379",
        r2_endpoint="https://test.r2.cloudflarestorage.com",
        r2_access_key="test-access",
        r2_secret_key="test-secret",
        r2_bucket="test-bucket",
        max_iterations=5,
    )


@pytest.fixture
def agent_config() -> AgentConfig:
    """Test agent configuration."""
    return AgentConfig(
        name="test-agent",
        type="direct",
        brain=BrainConfig(
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            temperature=0.7,
            max_tokens=4096,
        ),
        capabilities=CapabilityGrants(
            grants=["hub:read", "hub:write"],
            skills=["hub-post", "hub-search"],
            mcp_servers=["hub"],
        ),
        behavior=BehaviorConfig(
            respond_to_mentions=True,
            max_iterations=10,
        ),
        system_prompt="You are a test agent.",
    )


@pytest.fixture
def context() -> Context:
    """Test context."""
    return Context(
        messages=[
            Message(role="system", content="You are a test agent."),
            Message(role="user", content="What is 2+2?"),
        ],
        tools=[
            {
                "name": "hub_post",
                "description": "Post to Hub",
                "parameters": {
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                    "required": ["content"],
                },
            },
        ],
    )


@pytest.fixture
def mock_hub() -> AsyncMock:
    """Mock HubClient."""
    mock = AsyncMock()
    mock.create_comment.return_value = Post(
        id="comment-new",
        author_id="test-agent",
        author_name="Test Agent",
        content="Test response",
        created_at=datetime.now(UTC),
    )
    mock.create_post.return_value = Post(
        id="post-new",
        author_id="test-agent",
        author_name="Test Agent",
        title="New Post",
        content="Test content",
        created_at=datetime.now(UTC),
    )
    mock.search.return_value = []
    mock.get_thread.return_value = Thread(
        root=Post(
            id="post-123",
            author_id="other",
            author_name="Other",
            content="Original post",
            created_at=datetime.now(UTC),
        ),
        comments=[],
    )
    return mock


@pytest.fixture
def mock_sandbox() -> AsyncMock:
    """Mock Sandbox."""
    mock = AsyncMock()
    mock.execute_tool.return_value = ToolResult(output="File contents here")
    mock.execute_mcp_tool.return_value = ToolResult(output="MCP result")
    return mock


class TestAgentLoop:
    """Tests for AgentLoop class."""

    async def test_loop_direct_response(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test loop returns direct response when no tools called."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        # Mock LLM returning a text response
        with patch.object(loop, "_reason", new_callable=AsyncMock) as mock_reason:
            mock_reason.return_value = Action(
                is_tool_call=False,
                content="The answer is 4.",
            )

            result = await loop.run(agent_config, context)

            assert result.success is True
            assert result.response == "The answer is 4."
            assert result.iterations == 1
            assert result.tool_calls_made == 0
            mock_reason.assert_called_once()

    async def test_loop_with_tool_call(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test loop handles tool call then final response."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        # First call returns tool use, second returns text
        call_count = 0

        async def mock_reason(*_args: object, **_kwargs: object) -> Action:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Action(
                    is_tool_call=True,
                    tool_calls=[
                        ToolCall(
                            id="call-1",
                            name="hub_post",
                            arguments={"content": "Hello!"},
                        )
                    ],
                    content="I'll post to Hub.",
                )
            return Action(
                is_tool_call=False,
                content="I've posted to Hub.",
            )

        with patch.object(loop, "_reason", side_effect=mock_reason):
            result = await loop.run(agent_config, context)

            assert result.success is True
            assert result.response == "I've posted to Hub."
            assert result.iterations == 2
            assert result.tool_calls_made == 1

    async def test_loop_max_iterations_exceeded(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test loop stops at max iterations."""
        settings.max_iterations = 3
        agent_config.behavior.max_iterations = 3
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        # Always return tool calls (never complete)
        with patch.object(loop, "_reason", new_callable=AsyncMock) as mock_reason:
            mock_reason.return_value = Action(
                is_tool_call=True,
                tool_calls=[
                    ToolCall(id="call-1", name="Read", arguments={"file_path": "/test"})
                ],
            )
            with patch.object(loop, "_execute_tool", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = ToolResult(output="file content")

                result = await loop.run(agent_config, context)

                assert result.success is False
                assert "Exceeded maximum iterations" in (result.error or "")
                assert result.iterations == 3

    async def test_loop_fatal_tool_error(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test loop stops on fatal tool error."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        with patch.object(loop, "_reason", new_callable=AsyncMock) as mock_reason:
            mock_reason.return_value = Action(
                is_tool_call=True,
                tool_calls=[
                    ToolCall(id="call-1", name="Bash", arguments={"command": "rm -rf /"})
                ],
            )
            with patch.object(loop, "_execute_tool", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = ToolResult(
                    error="Dangerous command blocked",
                    fatal=True,
                )

                result = await loop.run(agent_config, context)

                assert result.success is False
                assert "Fatal tool error" in (result.error or "")

    async def test_loop_llm_error(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test loop handles LLM errors gracefully."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        with patch.object(loop, "_reason", new_callable=AsyncMock) as mock_reason:
            mock_reason.side_effect = Exception("API rate limit")

            result = await loop.run(agent_config, context)

            assert result.success is False
            assert "LLM error" in (result.error or "")
            assert "API rate limit" in (result.error or "")


class TestToolExecution:
    """Tests for tool execution in AgentLoop."""

    async def test_hub_post_reply(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test hub_post with reply_to."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        result = await loop._hub_post(
            agent_config,
            {"content": "Great point!", "reply_to": "post-123"},
        )

        assert result.error is None
        assert "Comment posted" in result.output
        mock_hub.create_comment.assert_called_once_with(
            agent_id="test-agent",
            post_id="post-123",
            content="Great point!",
        )

    async def test_hub_post_new(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test hub_post creating new post."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        result = await loop._hub_post(
            agent_config,
            {
                "content": "New discussion topic",
                "title": "Discussion",
                "community": "m/general",
            },
        )

        assert result.error is None
        assert "Post created" in result.output
        mock_hub.create_post.assert_called_once()

    async def test_hub_search(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test hub_search tool."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)
        mock_hub.search.return_value = [
            Post(
                id="post-1",
                author_id="user-1",
                author_name="User 1",
                title="Test Result",
                content="This is a search result",
                created_at=datetime.now(UTC),
            )
        ]

        result = await loop._hub_search({"query": "test", "limit": 5})

        assert result.error is None
        assert "Test Result" in result.output
        mock_hub.search.assert_called_once_with(
            query="test",
            community=None,
            limit=5,
        )

    async def test_hub_search_no_results(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test hub_search with no results."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)
        mock_hub.search.return_value = []

        result = await loop._hub_search({"query": "nonexistent"})

        assert result.error is None
        assert "No results" in result.output

    async def test_hub_get_thread(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test hub_get_thread tool."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)
        mock_hub.get_thread.return_value = Thread(
            root=Post(
                id="post-123",
                author_id="author-1",
                author_name="Author",
                content="Original post content",
                created_at=datetime.now(UTC),
            ),
            comments=[
                Post(
                    id="comment-1",
                    author_id="commenter-1",
                    author_name="Commenter",
                    content="First reply",
                    created_at=datetime.now(UTC),
                )
            ],
        )

        result = await loop._hub_get_thread({"post_id": "post-123"})

        assert result.error is None
        assert "Author" in result.output
        assert "Original post content" in result.output
        assert "Commenter" in result.output

    async def test_execute_core_tool(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test executing core tools (Read, Write, etc.)."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)
        mock_sandbox.execute_tool.return_value = ToolResult(
            output="file contents here"
        )

        result = await loop._execute_tool(
            agent_config,
            ToolCall(id="call-1", name="Read", arguments={"file_path": "/test.py"}),
        )

        assert result.error is None
        assert result.output == "file contents here"
        mock_sandbox.execute_tool.assert_called_once_with(
            "Read", {"file_path": "/test.py"}
        )

    async def test_execute_mcp_tool(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test executing MCP tools."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)
        mock_sandbox.execute_mcp_tool.return_value = ToolResult(output="GitHub data")

        result = await loop._execute_tool(
            agent_config,
            ToolCall(
                id="call-1",
                name="mcp_github_list_prs",
                arguments={"repo": "owner/repo"},
            ),
        )

        assert result.error is None
        assert result.output == "GitHub data"
        mock_sandbox.execute_mcp_tool.assert_called_once()

    async def test_unknown_tool(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test handling unknown tool."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        result = await loop._execute_tool(
            agent_config,
            ToolCall(id="call-1", name="unknown_tool", arguments={}),
        )

        assert "Unknown tool" in (result.error or "")


class TestLLMIntegration:
    """Tests for LLM integration (mocked)."""

    async def test_reason_anthropic(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test Anthropic Claude reasoning."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        # Mock Anthropic client
        mock_response = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.content = [MagicMock(type="text", text="Test response")]

        with patch("botburrow_agents.runner.loop.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            action = await loop._reason_anthropic(agent_config, context)

            assert action.is_tool_call is False
            assert action.content == "Test response"
            assert context.token_count == 150

    async def test_reason_anthropic_tool_use(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test Anthropic Claude with tool use."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.id = "toolu_123"
        mock_tool_use.name = "hub_post"
        mock_tool_use.input = {"content": "Hello"}

        mock_response = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.content = [mock_tool_use]

        with patch("botburrow_agents.runner.loop.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            action = await loop._reason_anthropic(agent_config, context)

            assert action.is_tool_call is True
            assert len(action.tool_calls) == 1
            assert action.tool_calls[0].name == "hub_post"
            assert action.tool_calls[0].id == "toolu_123"

    async def test_reason_openai(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test OpenAI reasoning."""
        # Switch to OpenAI provider
        agent_config.brain.provider = "openai"
        agent_config.brain.model = "gpt-4o"
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        mock_usage = MagicMock()
        mock_usage.total_tokens = 150

        mock_message = MagicMock()
        mock_message.content = "OpenAI response"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.usage = mock_usage
        mock_response.choices = [mock_choice]

        with patch("botburrow_agents.runner.loop.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            action = await loop._reason_openai(agent_config, context)

            assert action.is_tool_call is False
            assert action.content == "OpenAI response"

    async def test_reason_unsupported_provider(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test unsupported LLM provider."""
        agent_config.brain.provider = "unsupported"
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            await loop._reason(agent_config, context)


class TestContextManagement:
    """Tests for context management during loop execution."""

    async def test_context_tracks_iterations(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test context iteration tracking."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        with patch.object(loop, "_reason", new_callable=AsyncMock) as mock_reason:
            # Two tool calls, then final response
            responses = [
                Action(
                    is_tool_call=True,
                    tool_calls=[
                        ToolCall(id="1", name="Read", arguments={"file_path": "/a"})
                    ],
                ),
                Action(
                    is_tool_call=True,
                    tool_calls=[
                        ToolCall(id="2", name="Read", arguments={"file_path": "/b"})
                    ],
                ),
                Action(is_tool_call=False, content="Done!"),
            ]
            mock_reason.side_effect = responses

            with patch.object(loop, "_execute_tool", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = ToolResult(output="content")

                result = await loop.run(agent_config, context)

                assert result.iterations == 3
                assert result.tool_calls_made == 2

    async def test_context_tracks_tokens(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test token counting in context."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        # Token count should accumulate
        async def mock_reason_with_tokens(
            _agent: AgentConfig, ctx: Context
        ) -> Action:
            ctx.token_count += 100  # Add 100 tokens per call
            return Action(is_tool_call=False, content="Response")

        with patch.object(loop, "_reason", side_effect=mock_reason_with_tokens):
            result = await loop.run(agent_config, context)

            assert result.tokens_used == 100  # One iteration

    async def test_tool_results_added_to_context(
        self,
        settings: Settings,
        agent_config: AgentConfig,
        context: Context,
        mock_hub: AsyncMock,
        mock_sandbox: AsyncMock,
    ) -> None:
        """Test that tool results are added to context."""
        loop = AgentLoop(mock_hub, mock_sandbox, settings)

        call_count = 0
        saved_context: Context | None = None

        async def track_context(_agent: AgentConfig, ctx: Context) -> Action:
            nonlocal call_count, saved_context
            call_count += 1
            saved_context = ctx
            if call_count == 1:
                return Action(
                    is_tool_call=True,
                    tool_calls=[
                        ToolCall(id="call-1", name="hub_search", arguments={"query": "test"})
                    ],
                )
            return Action(is_tool_call=False, content="Done")

        with patch.object(loop, "_reason", side_effect=track_context):
            mock_hub.search.return_value = []
            await loop.run(agent_config, context)

            # After tool execution, context should have tool result message
            assert saved_context is not None
            tool_messages = [m for m in saved_context.messages if m.role == "tool"]
            assert len(tool_messages) == 1
            assert tool_messages[0].tool_call_id == "call-1"
