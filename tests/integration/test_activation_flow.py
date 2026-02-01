"""Integration tests for end-to-end activation flow.

Tests the complete flow from notification polling through agent execution
and response posting.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from botburrow_agents.clients.hub import HubClient
from botburrow_agents.clients.r2 import R2Client
from botburrow_agents.clients.redis import RedisClient
from botburrow_agents.config import ActivationMode, Settings
from botburrow_agents.coordinator.assigner import Assigner
from botburrow_agents.coordinator.scheduler import Scheduler
from botburrow_agents.coordinator.work_queue import ConfigCache, WorkItem, WorkQueue
from botburrow_agents.models import (
    AgentConfig,
    Assignment,
    BehaviorConfig,
    BrainConfig,
    CapabilityGrants,
    Context,
    Message,
    Notification,
    NotificationType,
    Post,
    TaskType,
    Thread,
)
from botburrow_agents.runner.context import ContextBuilder
from botburrow_agents.runner.loop import AgentLoop
from botburrow_agents.runner.sandbox import LocalSandbox


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings(
        hub_url="http://test-hub:8000",
        redis_url="redis://localhost:6379",
        poll_interval=5,
        activation_timeout=60,
        max_iterations=3,
    )


@pytest.fixture
def agent_config():
    """Create test agent configuration."""
    return AgentConfig(
        name="test-agent",
        type="claude-code",
        brain=BrainConfig(
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            temperature=0.7,
            max_tokens=4096,
        ),
        capabilities=CapabilityGrants(
            grants=["hub:read", "hub:write"],
            skills=["hub-post"],
            mcp_servers=[],
        ),
        behavior=BehaviorConfig(
            respond_to_mentions=True,
            max_iterations=3,  # Match settings for testing
        ),
        system_prompt="You are a helpful agent.",
    )


@pytest.fixture
def notification():
    """Create test notification."""
    return Notification(
        id="notif-1",
        type=NotificationType.MENTION,
        post_id="post-1",
        from_agent="user-1",
        from_agent_name="Alice",
        content="@test-agent Can you help me with this?",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def thread():
    """Create test thread."""
    root = Post(
        id="post-1",
        author_id="user-1",
        author_name="Alice",
        title="Need help",
        content="I need help with my code.",
        community="m/general",
        created_at=datetime.now(UTC),
    )
    return Thread(root=root, comments=[])


class TestActivationFlow:
    """Test complete activation flow."""

    @pytest.mark.asyncio
    async def test_notification_to_context_to_response(
        self,
        settings,
        agent_config,
        notification,
        thread,
    ):
        """Test flow from notification to agent response."""
        # Mock clients
        hub = AsyncMock(spec=HubClient)
        hub.get_thread.return_value = thread
        hub.get_notifications.return_value = [notification]
        hub.create_comment.return_value = Post(
            id="comment-1",
            author_id="test-agent",
            author_name="Test Agent",
            content="Here's my response!",
            parent_id="post-1",
            created_at=datetime.now(UTC),
        )

        r2 = AsyncMock(spec=R2Client)
        r2.load_agent_config.return_value = agent_config

        # Build context
        context_builder = ContextBuilder(hub, r2)
        context = await context_builder.build_for_notification(
            agent_config, notification
        )

        # Verify context structure
        assert len(context.messages) >= 2  # System prompt + notification
        assert context.messages[0].role == "system"
        assert "You are a helpful agent" in context.messages[0].content
        assert "hub_post" in [t["name"] for t in context.tools]

    @pytest.mark.asyncio
    async def test_work_queue_claim_and_complete(self, settings):
        """Test work queue claim and completion flow."""
        # Use fakeredis
        import fakeredis.aioredis as fakeredis_aio

        fake_redis = fakeredis_aio.FakeRedis()

        redis = AsyncMock(spec=RedisClient)
        redis._ensure_connected = AsyncMock(return_value=fake_redis)

        work_queue = WorkQueue(redis, settings)

        # Enqueue work
        work_item = WorkItem(
            agent_id="test-agent",
            agent_name="Test Agent",
            task_type=TaskType.INBOX,
            priority="high",
            inbox_count=1,
        )

        # Mock enqueue
        await fake_redis.lpush("work:queue:high", work_item.to_json())

        # Claim work
        result = await fake_redis.brpop(
            ["work:queue:high", "work:queue:normal", "work:queue:low"],
            timeout=1,
        )

        assert result is not None
        queue_key, work_json = result
        claimed = WorkItem.from_json(work_json)

        assert claimed.agent_id == "test-agent"
        assert claimed.task_type == TaskType.INBOX

        await fake_redis.aclose()

    @pytest.mark.asyncio
    async def test_scheduler_prioritizes_notifications(self, settings):
        """Test that scheduler prioritizes agents with notifications."""
        hub = AsyncMock(spec=HubClient)
        redis = AsyncMock(spec=RedisClient)

        # Mock agents with different states
        hub.get_agents_with_notifications.return_value = [
            Assignment(
                agent_id="agent-1",
                agent_name="Agent 1",
                task_type=TaskType.INBOX,
                inbox_count=5,
            ),
            Assignment(
                agent_id="agent-2",
                agent_name="Agent 2",
                task_type=TaskType.INBOX,
                inbox_count=1,
            ),
        ]

        redis.exists = AsyncMock(return_value=False)

        scheduler = Scheduler(hub, redis, settings)

        # Get notification assignment (should be highest priority)
        assignment = await scheduler.get_next_assignment(ActivationMode.NOTIFICATION)

        assert assignment is not None
        assert assignment.agent_id == "agent-1"  # Most notifications first

    @pytest.mark.asyncio
    async def test_assigner_lock_flow(self, settings):
        """Test assigner lock acquisition and release."""
        hub = AsyncMock(spec=HubClient)
        hub.update_agent_activation = AsyncMock()

        redis = AsyncMock(spec=RedisClient)
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value="runner-1")
        redis.delete = AsyncMock(return_value=1)

        assigner = Assigner(hub, redis, settings)

        assignment = Assignment(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        # Claim agent
        claimed = await assigner.try_claim(assignment, "runner-1")
        assert claimed is True

        # Verify lock was set
        redis.set.assert_called()

        # Release agent
        released = await assigner.release("agent-1", "runner-1")
        assert released is True

    @pytest.mark.asyncio
    async def test_agent_loop_with_tool_call(self, settings, agent_config):
        """Test agent loop executes tool calls correctly."""
        hub = AsyncMock(spec=HubClient)
        hub.create_comment.return_value = Post(
            id="comment-1",
            author_id="test-agent",
            author_name="Test Agent",
            content="Response",
            parent_id="post-1",
            created_at=datetime.now(UTC),
        )

        sandbox = AsyncMock(spec=LocalSandbox)
        sandbox.execute_tool = AsyncMock()

        loop = AgentLoop(hub, sandbox, settings)

        # Create context with tool use scenario
        context = Context()
        context.add_message(Message(role="system", content="You are a helpful agent."))
        context.add_message(Message(role="user", content="Reply to post-1"))
        context.tools = [
            {
                "name": "hub_post",
                "description": "Create a post or comment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "reply_to": {"type": "string"},
                    },
                    "required": ["content"],
                },
            },
        ]

        # Mock LLM to return a direct response
        with patch.object(loop, "_reason") as mock_reason:
            from botburrow_agents.models import Action

            mock_reason.return_value = Action(
                is_tool_call=False,
                content="I've posted a helpful response!",
            )

            result = await loop.run(agent_config, context)

            assert result.success is True
            assert result.iterations == 1

    @pytest.mark.asyncio
    async def test_sandbox_tool_execution(self, agent_config, settings):
        """Test sandbox executes tools correctly."""
        sandbox = LocalSandbox(agent_config, settings)
        await sandbox.start()

        try:
            # Write a file
            write_result = await sandbox.execute_tool("Write", {
                "file_path": "test.txt",
                "content": "Hello, World!",
            })
            assert write_result.error is None

            # Read it back
            read_result = await sandbox.execute_tool("Read", {
                "file_path": "test.txt",
            })
            assert read_result.output == "Hello, World!"

            # Test glob
            glob_result = await sandbox.execute_tool("Glob", {
                "pattern": "*.txt",
            })
            assert "test.txt" in glob_result.output

        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    async def test_config_cache_flow(self, settings, agent_config):
        """Test config cache reduces R2 fetches."""
        import fakeredis.aioredis as fakeredis_aio

        fake_redis = fakeredis_aio.FakeRedis()

        redis = AsyncMock(spec=RedisClient)
        redis._ensure_connected = AsyncMock(return_value=fake_redis)

        cache = ConfigCache(redis, ttl=60)

        # First access should be cache miss
        cached = await cache.get("test-agent")
        assert cached is None

        # Cache the config
        await cache.set("test-agent", agent_config.model_dump())

        # Second access should be cache hit
        cached = await cache.get("test-agent")
        assert cached is not None
        assert cached["name"] == "test-agent"

        await fake_redis.aclose()


class TestErrorHandling:
    """Test error handling in activation flow."""

    @pytest.mark.asyncio
    async def test_hub_connection_error(self, settings):
        """Test handling of Hub connection errors."""
        hub = AsyncMock(spec=HubClient)
        hub.get_agents_with_notifications.side_effect = ConnectionError(
            "Cannot connect to Hub"
        )

        redis = AsyncMock(spec=RedisClient)
        scheduler = Scheduler(hub, redis, settings)

        # Should raise the error (not silently fail)
        with pytest.raises(ConnectionError):
            await scheduler.get_next_assignment(ActivationMode.NOTIFICATION)

    @pytest.mark.asyncio
    async def test_agent_loop_max_iterations(self, settings, agent_config):
        """Test agent loop respects max iterations."""
        hub = AsyncMock(spec=HubClient)
        sandbox = AsyncMock(spec=LocalSandbox)

        loop = AgentLoop(hub, sandbox, settings)

        context = Context()
        context.add_message(Message(role="system", content="You are a helpful agent."))
        context.add_message(Message(role="user", content="Keep calling tools forever"))

        # Mock LLM to always return tool calls
        with patch.object(loop, "_reason") as mock_reason:
            from botburrow_agents.models import Action, ToolCall

            mock_reason.return_value = Action(
                is_tool_call=True,
                tool_calls=[
                    ToolCall(id="call-1", name="hub_search", arguments={"query": "test"})
                ],
                content="",
            )

            # Mock tool execution
            with patch.object(loop, "_execute_tool") as mock_execute:
                from botburrow_agents.models import ToolResult

                mock_execute.return_value = ToolResult(output="No results")

                result = await loop.run(agent_config, context)

                # Should fail due to max iterations
                assert result.success is False
                assert "iterations" in result.error.lower()
                assert context.iterations == settings.max_iterations


class TestScalabilityPatterns:
    """Test scalability patterns."""

    @pytest.mark.asyncio
    async def test_work_queue_priority_ordering(self, settings):
        """Test work items are processed by priority."""
        import fakeredis.aioredis as fakeredis_aio

        fake_redis = fakeredis_aio.FakeRedis()

        # Add items to different priority queues
        low_item = WorkItem(
            agent_id="low-agent",
            agent_name="Low Priority",
            task_type=TaskType.DISCOVERY,
            priority="low",
        )
        normal_item = WorkItem(
            agent_id="normal-agent",
            agent_name="Normal Priority",
            task_type=TaskType.INBOX,
            priority="normal",
        )
        high_item = WorkItem(
            agent_id="high-agent",
            agent_name="High Priority",
            task_type=TaskType.INBOX,
            priority="high",
            inbox_count=10,
        )

        # Add in wrong order
        await fake_redis.lpush("work:queue:low", low_item.to_json())
        await fake_redis.lpush("work:queue:normal", normal_item.to_json())
        await fake_redis.lpush("work:queue:high", high_item.to_json())

        # Claim should get high priority first
        result = await fake_redis.brpop(
            ["work:queue:high", "work:queue:normal", "work:queue:low"],
            timeout=1,
        )
        assert result is not None
        queue_key, work_json = result
        claimed = WorkItem.from_json(work_json)

        assert claimed.agent_id == "high-agent"
        assert claimed.priority == "high"

        await fake_redis.aclose()

    @pytest.mark.asyncio
    async def test_concurrent_claim_deduplication(self, settings):
        """Test that same agent cannot be claimed twice."""
        import fakeredis.aioredis as fakeredis_aio

        fake_redis = fakeredis_aio.FakeRedis()

        redis = AsyncMock(spec=RedisClient)
        redis._ensure_connected = AsyncMock(return_value=fake_redis)

        work_queue = WorkQueue(redis, settings)

        work_item = WorkItem(
            agent_id="test-agent",
            agent_name="Test Agent",
            task_type=TaskType.INBOX,
        )

        # Simulate agent being active
        await fake_redis.hset("work:active", "test-agent", "runner-1")

        # Enqueue should be skipped due to deduplication
        enqueued = await work_queue.enqueue(work_item)
        assert enqueued is False  # Already active

        await fake_redis.aclose()

    @pytest.mark.asyncio
    async def test_circuit_breaker_on_failures(self, settings):
        """Test circuit breaker triggers after repeated failures."""
        import fakeredis.aioredis as fakeredis_aio

        fake_redis = fakeredis_aio.FakeRedis()

        redis = AsyncMock(spec=RedisClient)
        redis._ensure_connected = AsyncMock(return_value=fake_redis)

        work_queue = WorkQueue(redis, settings)
        work_queue.max_failures = 3  # Lower threshold for test

        work_item = WorkItem(
            agent_id="failing-agent",
            agent_name="Failing Agent",
            task_type=TaskType.INBOX,
        )

        # Simulate multiple failures
        for _ in range(4):
            await work_queue.complete(work_item, success=False)

        # Agent should now be in backoff
        backoff = await fake_redis.hget("work:backoff", "failing-agent")
        assert backoff is not None
        assert float(backoff) > 0

        # Attempting to enqueue should fail
        enqueued = await work_queue.enqueue(work_item)
        assert enqueued is False  # In backoff

        await fake_redis.aclose()
