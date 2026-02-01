"""Tests for WorkQueue, ConfigCache, and LeaderElection."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.coordinator.work_queue import (
    ACTIVE_TASKS,
    AGENT_BACKOFF,
    AGENT_FAILURES,
    ConfigCache,
    LeaderElection,
    WorkItem,
    WorkQueue,
    jitter,
)
from botburrow_agents.models import TaskType


@pytest.fixture
def work_queue_settings() -> Settings:
    """Test settings for WorkQueue."""
    return Settings(
        hub_url="http://test-hub:8000",
        redis_url="redis://localhost:6379",
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock RedisClient."""
    mock = AsyncMock()
    mock._ensure_connected = AsyncMock(return_value=mock)
    mock.lpush = AsyncMock()
    mock.brpop = AsyncMock()
    mock.hget = AsyncMock()
    mock.hset = AsyncMock()
    mock.hdel = AsyncMock()
    mock.hincrby = AsyncMock()
    mock.hlen = AsyncMock()
    mock.llen = AsyncMock()
    mock.set = AsyncMock()
    mock.get = AsyncMock()
    mock.delete = AsyncMock()
    mock.expire = AsyncMock()
    mock.eval = AsyncMock()
    return mock


class TestWorkItem:
    """Tests for WorkItem serialization."""

    def test_to_json(self) -> None:
        """Test serialization to JSON."""
        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
            priority="high",
            inbox_count=5,
        )

        json_str = item.to_json()
        data = json.loads(json_str)

        assert data["agent_id"] == "agent-1"
        assert data["agent_name"] == "Agent 1"
        assert data["task_type"] == "inbox"
        assert data["priority"] == "high"
        assert data["inbox_count"] == 5
        assert "created_at" in data

    def test_from_json(self) -> None:
        """Test deserialization from JSON."""
        data = {
            "agent_id": "agent-2",
            "agent_name": "Agent 2",
            "task_type": "discovery",
            "priority": "low",
            "inbox_count": 0,
            "created_at": 1234567890.0,
        }
        json_str = json.dumps(data)

        item = WorkItem.from_json(json_str)

        assert item.agent_id == "agent-2"
        assert item.agent_name == "Agent 2"
        assert item.task_type == TaskType.DISCOVERY
        assert item.priority == "low"
        assert item.inbox_count == 0
        assert item.created_at == 1234567890.0


class TestWorkQueueEnqueue:
    """Tests for WorkQueue enqueue functionality."""

    @pytest.fixture
    def queue(
        self, mock_redis: AsyncMock, work_queue_settings: Settings
    ) -> WorkQueue:
        """Create WorkQueue with mock."""
        return WorkQueue(mock_redis, work_queue_settings)

    @pytest.mark.asyncio
    async def test_enqueue_success(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test successful enqueue."""
        mock_redis.hget.return_value = None  # No active task

        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        result = await queue.enqueue(item)

        assert result is True
        mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_skip_duplicate(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test skipping duplicate work item."""
        mock_redis.hget.return_value = "runner-1"  # Already active

        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        result = await queue.enqueue(item)

        assert result is False
        mock_redis.lpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_skip_backoff(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test skipping agent in backoff."""
        mock_redis.hget.side_effect = [
            None,  # No active task
            str(time.time() + 3600),  # Backoff until future
        ]

        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        result = await queue.enqueue(item)

        assert result is False
        mock_redis.lpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_clear_expired_backoff(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test clearing expired backoff."""
        mock_redis.hget.side_effect = [
            None,  # No active task
            str(time.time() - 100),  # Backoff expired
        ]

        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        result = await queue.enqueue(item)

        assert result is True
        mock_redis.hdel.assert_called_once_with(AGENT_BACKOFF, "agent-1")
        mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_force_skip_dedup(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test force flag bypasses deduplication."""
        mock_redis.hget.return_value = "runner-1"  # Already active

        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        result = await queue.enqueue(item, force=True)

        assert result is True
        mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_priority_queues(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test items go to correct priority queue."""
        mock_redis.hget.return_value = None

        for priority, expected_queue in [
            ("high", "work:queue:high"),
            ("normal", "work:queue:normal"),
            ("low", "work:queue:low"),
        ]:
            mock_redis.lpush.reset_mock()
            item = WorkItem(
                agent_id=f"agent-{priority}",
                agent_name=f"Agent {priority}",
                task_type=TaskType.INBOX,
                priority=priority,
            )

            await queue.enqueue(item)

            call_args = mock_redis.lpush.call_args[0]
            assert call_args[0] == expected_queue


class TestWorkQueueClaim:
    """Tests for WorkQueue claim functionality."""

    @pytest.fixture
    def queue(
        self, mock_redis: AsyncMock, work_queue_settings: Settings
    ) -> WorkQueue:
        """Create WorkQueue with mock."""
        return WorkQueue(mock_redis, work_queue_settings)

    @pytest.mark.asyncio
    async def test_claim_success(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test successful claim."""
        work_data = {
            "agent_id": "agent-1",
            "agent_name": "Agent 1",
            "task_type": "inbox",
            "priority": "normal",
        }
        mock_redis.brpop.return_value = (
            "work:queue:normal",
            json.dumps(work_data),
        )

        result = await queue.claim("runner-1", timeout=30)

        assert result is not None
        assert result.agent_id == "agent-1"
        mock_redis.hset.assert_called_once_with(
            ACTIVE_TASKS, "agent-1", "runner-1"
        )

    @pytest.mark.asyncio
    async def test_claim_timeout(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test claim returns None on timeout."""
        mock_redis.brpop.return_value = None

        result = await queue.claim("runner-1", timeout=30)

        assert result is None


class TestWorkQueueComplete:
    """Tests for WorkQueue complete functionality."""

    @pytest.fixture
    def queue(
        self, mock_redis: AsyncMock, work_queue_settings: Settings
    ) -> WorkQueue:
        """Create WorkQueue with mock."""
        return WorkQueue(mock_redis, work_queue_settings)

    @pytest.mark.asyncio
    async def test_complete_success(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test completing work successfully."""
        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        await queue.complete(item, success=True)

        mock_redis.hdel.assert_any_call(ACTIVE_TASKS, "agent-1")
        mock_redis.hdel.assert_any_call(AGENT_FAILURES, "agent-1")
        mock_redis.hdel.assert_any_call(AGENT_BACKOFF, "agent-1")

    @pytest.mark.asyncio
    async def test_complete_failure_increments_count(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test completing with failure increments count."""
        mock_redis.hincrby.return_value = 2  # 2nd failure

        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        await queue.complete(item, success=False)

        mock_redis.hdel.assert_called_once_with(ACTIVE_TASKS, "agent-1")
        mock_redis.hincrby.assert_called_once_with(
            AGENT_FAILURES, "agent-1", 1
        )
        # Should not trigger circuit breaker yet
        mock_redis.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_failure_triggers_circuit_breaker(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test that repeated failures trigger circuit breaker."""
        mock_redis.hincrby.return_value = 5  # 5th failure = threshold

        item = WorkItem(
            agent_id="agent-1",
            agent_name="Agent 1",
            task_type=TaskType.INBOX,
        )

        await queue.complete(item, success=False)

        # Should set backoff
        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args[0]
        assert call_args[0] == AGENT_BACKOFF
        assert call_args[1] == "agent-1"


class TestWorkQueueStats:
    """Tests for WorkQueue statistics."""

    @pytest.fixture
    def queue(
        self, mock_redis: AsyncMock, work_queue_settings: Settings
    ) -> WorkQueue:
        """Create WorkQueue with mock."""
        return WorkQueue(mock_redis, work_queue_settings)

    @pytest.mark.asyncio
    async def test_get_queue_stats(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test getting queue statistics."""
        mock_redis.llen.side_effect = [10, 20, 5]  # high, normal, low
        mock_redis.hlen.side_effect = [3, 2]  # active, backoff

        stats = await queue.get_queue_stats()

        assert stats["queue_high"] == 10
        assert stats["queue_normal"] == 20
        assert stats["queue_low"] == 5
        assert stats["total_queued"] == 35
        assert stats["active_tasks"] == 3
        assert stats["agents_in_backoff"] == 2

    @pytest.mark.asyncio
    async def test_clear_backoff(
        self, queue: WorkQueue, mock_redis: AsyncMock
    ) -> None:
        """Test clearing agent backoff."""
        await queue.clear_backoff("agent-1")

        mock_redis.hdel.assert_any_call(AGENT_BACKOFF, "agent-1")
        mock_redis.hdel.assert_any_call(AGENT_FAILURES, "agent-1")


class TestConfigCache:
    """Tests for ConfigCache."""

    @pytest.fixture
    def cache(self, mock_redis: AsyncMock) -> ConfigCache:
        """Create ConfigCache with mock."""
        return ConfigCache(mock_redis, ttl=300)

    @pytest.mark.asyncio
    async def test_get_cached(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Test getting cached config."""
        config = {"name": "Agent 1", "type": "claude-code"}
        mock_redis.get.return_value = json.dumps(config)

        result = await cache.get("agent-1")

        assert result == config
        mock_redis.get.assert_called_once_with("cache:agent:agent-1")

    @pytest.mark.asyncio
    async def test_get_not_cached(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Test getting config when not cached."""
        mock_redis.get.return_value = None

        result = await cache.get("agent-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_set(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Test setting cached config."""
        config = {"name": "Agent 1", "type": "claude-code"}

        await cache.set("agent-1", config)

        mock_redis.set.assert_called_once_with(
            "cache:agent:agent-1",
            json.dumps(config),
            ex=300,
        )

    @pytest.mark.asyncio
    async def test_invalidate(
        self, cache: ConfigCache, mock_redis: AsyncMock
    ) -> None:
        """Test invalidating cached config."""
        await cache.invalidate("agent-1")

        mock_redis.delete.assert_called_once_with("cache:agent:agent-1")


class TestLeaderElection:
    """Tests for LeaderElection."""

    @pytest.fixture
    def leader(self, mock_redis: AsyncMock) -> LeaderElection:
        """Create LeaderElection with mock."""
        return LeaderElection(mock_redis, "coordinator-1")

    @pytest.mark.asyncio
    async def test_try_become_leader_success(
        self, leader: LeaderElection, mock_redis: AsyncMock
    ) -> None:
        """Test successfully becoming leader."""
        mock_redis.set.return_value = True

        result = await leader.try_become_leader()

        assert result is True
        assert leader.is_leader is True
        mock_redis.set.assert_called_once_with(
            "coordinator:leader",
            "coordinator-1",
            nx=True,
            ex=30,
        )

    @pytest.mark.asyncio
    async def test_try_become_leader_already_leader(
        self, leader: LeaderElection, mock_redis: AsyncMock
    ) -> None:
        """Test refreshing leadership when already leader."""
        mock_redis.set.return_value = False  # Can't acquire
        mock_redis.get.return_value = "coordinator-1"  # We're already leader

        result = await leader.try_become_leader()

        assert result is True
        assert leader.is_leader is True
        mock_redis.expire.assert_called_once_with("coordinator:leader", 30)

    @pytest.mark.asyncio
    async def test_try_become_leader_failure(
        self, leader: LeaderElection, mock_redis: AsyncMock
    ) -> None:
        """Test failing to become leader."""
        mock_redis.set.return_value = False  # Can't acquire
        mock_redis.get.return_value = "coordinator-2"  # Someone else is leader

        result = await leader.try_become_leader()

        assert result is False
        assert leader.is_leader is False

    @pytest.mark.asyncio
    async def test_release_leadership(
        self, leader: LeaderElection, mock_redis: AsyncMock
    ) -> None:
        """Test releasing leadership."""
        # First become leader
        mock_redis.set.return_value = True
        await leader.try_become_leader()

        await leader.release_leadership()

        assert leader.is_leader is False
        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_leadership_when_not_leader(
        self, leader: LeaderElection, mock_redis: AsyncMock
    ) -> None:
        """Test releasing leadership when not leader does nothing."""
        await leader.release_leadership()

        mock_redis.eval.assert_not_called()


class TestJitter:
    """Tests for jitter function."""

    def test_jitter_basic(self) -> None:
        """Test jitter adds randomness."""
        base = 100.0
        results = [jitter(base) for _ in range(100)]

        # All results should be within +/- 10% of base
        assert all(90.0 <= r <= 110.0 for r in results)

    def test_jitter_custom_factor(self) -> None:
        """Test jitter with custom factor."""
        base = 100.0
        results = [jitter(base, factor=0.5) for _ in range(100)]

        # All results should be within +/- 50% of base
        assert all(50.0 <= r <= 150.0 for r in results)

    def test_jitter_not_constant(self) -> None:
        """Test jitter produces varying results."""
        base = 100.0
        results = [jitter(base) for _ in range(100)]

        # Should not all be the same
        assert len(set(results)) > 1
