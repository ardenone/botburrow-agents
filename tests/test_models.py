"""Tests for data models."""

from datetime import UTC, datetime

from botburrow_agents.models import (
    AgentConfig,
    Assignment,
    BrainConfig,
    Context,
    LoopResult,
    Message,
    Notification,
    NotificationType,
    Post,
    TaskType,
    Thread,
    ToolResult,
)


class TestAgentConfig:
    """Tests for AgentConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = AgentConfig(name="test-agent")

        assert config.name == "test-agent"
        assert config.type == "claude-code"
        assert config.brain.model == "claude-sonnet-4-20250514"
        assert config.brain.temperature == 0.7
        assert config.behavior.max_iterations == 10

    def test_full_config(self) -> None:
        """Test complete configuration."""
        config = AgentConfig(
            name="full-agent",
            type="goose",
            brain=BrainConfig(
                model="gpt-4o",
                provider="openai",
                temperature=0.5,
                max_tokens=2048,
            ),
        )

        assert config.name == "full-agent"
        assert config.type == "goose"
        assert config.brain.provider == "openai"


class TestAssignment:
    """Tests for Assignment model."""

    def test_inbox_assignment(self) -> None:
        """Test inbox task assignment."""
        assignment = Assignment(
            agent_id="agent-1",
            agent_name="Test Agent",
            task_type=TaskType.INBOX,
            inbox_count=5,
        )

        assert assignment.task_type == TaskType.INBOX
        assert assignment.inbox_count == 5

    def test_discovery_assignment(self) -> None:
        """Test discovery task assignment."""
        assignment = Assignment(
            agent_id="agent-1",
            agent_name="Test Agent",
            task_type=TaskType.DISCOVERY,
            last_activated=datetime.now(UTC),
        )

        assert assignment.task_type == TaskType.DISCOVERY
        assert assignment.last_activated is not None


class TestContext:
    """Tests for Context model."""

    def test_add_message(self) -> None:
        """Test adding messages to context."""
        ctx = Context()
        ctx.add_message(Message(role="system", content="You are helpful."))
        ctx.add_message({"role": "user", "content": "Hello!"})

        assert len(ctx.messages) == 2
        assert ctx.messages[0].role == "system"
        assert ctx.messages[1].content == "Hello!"

    def test_add_tool_result(self) -> None:
        """Test adding tool results."""
        ctx = Context()
        result = ToolResult(output="File written successfully.")
        ctx.add_tool_result("call-123", result)

        assert len(ctx.messages) == 1
        assert ctx.messages[0].role == "tool"
        assert ctx.messages[0].tool_call_id == "call-123"
        assert len(ctx.tool_history) == 1


class TestNotification:
    """Tests for Notification model."""

    def test_mention_notification(self) -> None:
        """Test mention notification."""
        notif = Notification(
            id="notif-1",
            type=NotificationType.MENTION,
            post_id="post-123",
            from_agent="other-agent",
            from_agent_name="Other Agent",
            content="@test-agent check this out",
            created_at=datetime.now(UTC),
        )

        assert notif.type == NotificationType.MENTION
        assert notif.post_id == "post-123"
        assert not notif.read


class TestThread:
    """Tests for Thread model."""

    def test_thread_with_comments(self, post: Post) -> None:
        """Test thread with comments."""
        comment = Post(
            id="comment-1",
            author_id="commenter",
            author_name="Commenter",
            content="Great post!",
            parent_id=post.id,
            created_at=datetime.now(UTC),
        )
        thread = Thread(root=post, comments=[comment])

        assert thread.root.id == post.id
        assert len(thread.comments) == 1
        assert thread.comments[0].parent_id == post.id


class TestLoopResult:
    """Tests for LoopResult model."""

    def test_successful_result(self) -> None:
        """Test successful loop result."""
        result = LoopResult(
            success=True,
            response="I processed your request.",
            iterations=3,
            tokens_used=1500,
            tool_calls_made=2,
        )

        assert result.success
        assert result.error is None

    def test_failed_result(self) -> None:
        """Test failed loop result."""
        result = LoopResult(
            success=False,
            error="Exceeded maximum iterations",
            iterations=10,
        )

        assert not result.success
        assert result.error is not None
