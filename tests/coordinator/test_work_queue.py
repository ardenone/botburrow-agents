"""Tests for work queue and scalability components."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fakeredis import aioredis as fakeredis

from botburrow_agents.config import Settings
from botburrow_agents.coordinator.work_queue import (
    AGENT_BACKOFF,
    AGENT_FAILURES,
    QUEUE_HIGH,
    QUEUE_LOW,
    QUEUE_NORMAL,
    ConfigCache,
    LeaderElection,
    WorkItem,
    WorkQueue,
    jitter,
)
from botburrow_agents.models import TaskType

# Check if Lua scripting is available (needed for eval command in leader election)
try:
    import lupa  # noqa: F401

    HAS_LUA = True
except ImportError:
    HAS_LUA = False

requires_lua = pytest.mark.skipif(
    not HAS_LUA, reason="Requires lupa for Lua scripting support in fakeredis"
)


@pytest.fixture
def work_item() -> WorkItem:
    """Create a sample work item."""
    return WorkItem(
        agent_id="test-agent",
        agent_name="Test Agent",
        task_type=TaskType.INBOX,
        priority="normal",
        inbox_count=5,
    )


@pytest.fixture
async def work_queue(settings: Settings, fake_redis: fakeredis.FakeRedis) -> WorkQueue:
    """Create a work queue backed by fakeredis."""
    mock_redis_client = MagicMock()
    mock_redis_client._ensure_connected = AsyncMock(return_value=fake_redis)
    return WorkQueue(mock_redis_client, settings)


class TestWorkItemSerialization:
    """Tests for WorkItem JSON serialization."""

    def test_to_json(self, work_item: WorkItem) -> None:
        """Test serializing work item to JSON."""
        json_str = work_item.to_json()

        assert '"agent_id": "test-agent"' in json_str
        assert '"task_type": "inbox"' in json_str
        assert '"priority": "normal"' in json_str

    def test_from_json(self, work_item: WorkItem) -> None:
        """Test deserializing work item from JSON."""
        json_str = work_item.to_json()
        restored = WorkItem.from_json(json_str)

        assert restored.agent_id == work_item.agent_id
        assert restored.agent_name == work_item.agent_name
        assert restored.task_type == work_item.task_type
        assert restored.priority == work_item.priority

    def test_from_json_with_defaults(self) -> None:
        """Test deserializing with missing optional fields."""
        json_str = '{"agent_id": "a", "agent_name": "A", "task_type": "inbox"}'
        item = WorkItem.from_json(json_str)

        assert item.priority == "normal"  # Default
        assert item.inbox_count == 0  # Default


class TestWorkQueueEnqueue:
    """Tests for enqueuing work."""

    @pytest.mark.asyncio
    async def test_enqueue_normal_priority(
        self, work_queue: WorkQueue, work_item: WorkItem
    ) -> None:
        """Test enqueuing to normal priority queue."""
        result = await work_queue.enqueue(work_item)

        assert result is True

        # Check it's in the normal queue
        r = await work_queue.redis._ensure_connected()
        length = await r.llen(QUEUE_NORMAL)
        assert length == 1

    @pytest.mark.asyncio
    async def test_enqueue_high_priority(self, work_queue: WorkQueue, work_item: WorkItem) -> None:
        """Test enqueuing to high priority queue."""
        work_item.priority = "high"
        result = await work_queue.enqueue(work_item)

        assert result is True

        r = await work_queue.redis._ensure_connected()
        assert await r.llen(QUEUE_HIGH) == 1
        assert await r.llen(QUEUE_NORMAL) == 0

    @pytest.mark.asyncio
    async def test_enqueue_low_priority(self, work_queue: WorkQueue, work_item: WorkItem) -> None:
        """Test enqueuing to low priority queue."""
        work_item.priority = "low"
        await work_queue.enqueue(work_item)

        r = await work_queue.redis._ensure_connected()
        assert await r.llen(QUEUE_LOW) == 1

    @pytest.mark.asyncio
    async def test_enqueue_deduplication(self, work_queue: WorkQueue, work_item: WorkItem) -> None:
        """Test that duplicate work items are rejected."""
        # First enqueue succeeds
        result1 = await work_queue.enqueue(work_item)
        assert result1 is True

        # Simulate agent having active task
        r = await work_queue.redis._ensure_connected()
        await r.hset("work:active", work_item.agent_id, "runner-1")

        # Second enqueue should be rejected
        result2 = await work_queue.enqueue(work_item)
        assert result2 is False

        # Should still only have 1 item
        assert await r.llen(QUEUE_NORMAL) == 1

    @pytest.mark.asyncio
    async def test_enqueue_force_bypasses_deduplication(
        self, work_queue: WorkQueue, work_item: WorkItem
    ) -> None:
        """Test that force=True bypasses deduplication."""
        # Set up active task
        r = await work_queue.redis._ensure_connected()
        await r.hset("work:active", work_item.agent_id, "runner-1")

        # Force enqueue should succeed
        result = await work_queue.enqueue(work_item, force=True)
        assert result is True


class TestWorkQueueClaim:
    """Tests for claiming work."""

    @pytest.mark.asyncio
    async def test_claim_respects_priority_order(self, work_queue: WorkQueue) -> None:
        """Test that high priority items are claimed first."""
        # Enqueue items at different priorities
        low_item = WorkItem(
            agent_id="low-agent",
            agent_name="Low",
            task_type=TaskType.DISCOVERY,
            priority="low",
        )
        normal_item = WorkItem(
            agent_id="normal-agent",
            agent_name="Normal",
            task_type=TaskType.INBOX,
            priority="normal",
        )
        high_item = WorkItem(
            agent_id="high-agent",
            agent_name="High",
            task_type=TaskType.INBOX,
            priority="high",
        )

        # Enqueue in reverse order
        await work_queue.enqueue(low_item)
        await work_queue.enqueue(normal_item)
        await work_queue.enqueue(high_item)

        # Claim should get high priority first
        claimed = await work_queue.claim("runner-1", timeout=1)
        assert claimed is not None
        assert claimed.agent_id == "high-agent"

    @pytest.mark.asyncio
    async def test_claim_marks_as_active(self, work_queue: WorkQueue, work_item: WorkItem) -> None:
        """Test that claimed work is marked as active."""
        await work_queue.enqueue(work_item)
        claimed = await work_queue.claim("runner-1", timeout=1)

        assert claimed is not None

        # Should be marked active
        r = await work_queue.redis._ensure_connected()
        active_runner = await r.hget("work:active", claimed.agent_id)
        assert active_runner == "runner-1"

    @pytest.mark.asyncio
    async def test_claim_empty_queue_returns_none(self, work_queue: WorkQueue) -> None:
        """Test that claiming from empty queue returns None."""
        claimed = await work_queue.claim("runner-1", timeout=1)
        assert claimed is None


class TestWorkQueueCircuitBreaker:
    """Tests for circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_complete_success_clears_failures(
        self, work_queue: WorkQueue, work_item: WorkItem
    ) -> None:
        """Test that successful completion clears failure count."""
        r = await work_queue.redis._ensure_connected()

        # Set up some previous failures
        await r.hset(AGENT_FAILURES, work_item.agent_id, "3")
        await r.hset("work:active", work_item.agent_id, "runner-1")

        # Complete successfully
        await work_queue.complete(work_item, success=True)

        # Failures should be cleared
        failures = await r.hget(AGENT_FAILURES, work_item.agent_id)
        assert failures is None

        # Should no longer be active
        active = await r.hget("work:active", work_item.agent_id)
        assert active is None

    @pytest.mark.asyncio
    async def test_complete_failure_increments_count(
        self, work_queue: WorkQueue, work_item: WorkItem
    ) -> None:
        """Test that failures are counted."""
        r = await work_queue.redis._ensure_connected()
        await r.hset("work:active", work_item.agent_id, "runner-1")

        # Fail 3 times
        for _ in range(3):
            await work_queue.complete(work_item, success=False)
            # Re-add to active for next iteration
            await r.hset("work:active", work_item.agent_id, "runner-1")

        failures = await r.hget(AGENT_FAILURES, work_item.agent_id)
        assert int(failures) == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_triggers_backoff(
        self, work_queue: WorkQueue, work_item: WorkItem
    ) -> None:
        """Test that exceeding max failures triggers backoff."""
        r = await work_queue.redis._ensure_connected()

        # Set failures to max - 1
        await r.hset(AGENT_FAILURES, work_item.agent_id, str(work_queue.max_failures - 1))
        await r.hset("work:active", work_item.agent_id, "runner-1")

        # This failure should trigger circuit breaker
        await work_queue.complete(work_item, success=False)

        # Should be in backoff
        backoff = await r.hget(AGENT_BACKOFF, work_item.agent_id)
        assert backoff is not None
        assert float(backoff) > time.time()

    @pytest.mark.asyncio
    async def test_backoff_prevents_enqueue(
        self, work_queue: WorkQueue, work_item: WorkItem
    ) -> None:
        """Test that agents in backoff cannot be enqueued."""
        r = await work_queue.redis._ensure_connected()

        # Set future backoff time
        await r.hset(AGENT_BACKOFF, work_item.agent_id, str(time.time() + 3600))

        # Enqueue should fail
        result = await work_queue.enqueue(work_item)
        assert result is False

    @pytest.mark.asyncio
    async def test_expired_backoff_allows_enqueue(
        self, work_queue: WorkQueue, work_item: WorkItem
    ) -> None:
        """Test that expired backoff allows enqueuing."""
        r = await work_queue.redis._ensure_connected()

        # Set past backoff time
        await r.hset(AGENT_BACKOFF, work_item.agent_id, str(time.time() - 1))

        # Enqueue should succeed
        result = await work_queue.enqueue(work_item)
        assert result is True

        # Backoff should be cleared
        backoff = await r.hget(AGENT_BACKOFF, work_item.agent_id)
        assert backoff is None

    @pytest.mark.asyncio
    async def test_clear_backoff(self, work_queue: WorkQueue, work_item: WorkItem) -> None:
        """Test manually clearing backoff."""
        r = await work_queue.redis._ensure_connected()

        # Set backoff and failures
        await r.hset(AGENT_BACKOFF, work_item.agent_id, str(time.time() + 3600))
        await r.hset(AGENT_FAILURES, work_item.agent_id, "10")

        # Clear backoff
        await work_queue.clear_backoff(work_item.agent_id)

        # Both should be cleared
        assert await r.hget(AGENT_BACKOFF, work_item.agent_id) is None
        assert await r.hget(AGENT_FAILURES, work_item.agent_id) is None


class TestWorkQueueStats:
    """Tests for queue statistics."""

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, work_queue: WorkQueue) -> None:
        """Test getting queue statistics."""
        r = await work_queue.redis._ensure_connected()

        # Add items to queues
        await r.lpush(QUEUE_HIGH, '{"agent_id":"a1"}')
        await r.lpush(QUEUE_HIGH, '{"agent_id":"a2"}')
        await r.lpush(QUEUE_NORMAL, '{"agent_id":"a3"}')
        await r.lpush(QUEUE_LOW, '{"agent_id":"a4"}')

        # Add active tasks
        await r.hset("work:active", "a5", "runner-1")
        await r.hset("work:active", "a6", "runner-2")

        # Add backoff
        await r.hset(AGENT_BACKOFF, "a7", str(time.time() + 3600))

        stats = await work_queue.get_queue_stats()

        assert stats["queue_high"] == 2
        assert stats["queue_normal"] == 1
        assert stats["queue_low"] == 1
        assert stats["total_queued"] == 4
        assert stats["active_tasks"] == 2
        assert stats["agents_in_backoff"] == 1


class TestConfigCache:
    """Tests for configuration caching."""

    @pytest.fixture
    async def config_cache(self, fake_redis: fakeredis.FakeRedis) -> ConfigCache:
        """Create a config cache backed by fakeredis."""
        mock_redis_client = MagicMock()
        mock_redis_client._ensure_connected = AsyncMock(return_value=fake_redis)
        return ConfigCache(mock_redis_client, ttl=60)

    @pytest.mark.asyncio
    async def test_set_and_get(self, config_cache: ConfigCache) -> None:
        """Test setting and getting cached config."""
        config = {"name": "test", "type": "claude-code"}

        await config_cache.set("agent-1", config)
        result = await config_cache.get("agent-1")

        assert result == config

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, config_cache: ConfigCache) -> None:
        """Test that missing config returns None."""
        result = await config_cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate(self, config_cache: ConfigCache) -> None:
        """Test invalidating cached config."""
        await config_cache.set("agent-1", {"name": "test"})
        await config_cache.invalidate("agent-1")

        result = await config_cache.get("agent-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_all(self, config_cache: ConfigCache) -> None:
        """Test invalidating all cached configs."""
        r = await config_cache.redis._ensure_connected()

        # Set multiple cached configs
        await config_cache.set("agent-1", {"name": "agent1"})
        await config_cache.set("agent-2", {"name": "agent2"})
        await config_cache.set("agent-3", {"name": "agent3"})

        # Verify they're cached
        assert await config_cache.get("agent-1") is not None
        assert await config_cache.get("agent-2") is not None
        assert await config_cache.get("agent-3") is not None

        # Invalidate all
        await config_cache.invalidate_all()

        # All should be gone
        assert await config_cache.get("agent-1") is None
        assert await config_cache.get("agent-2") is None
        assert await config_cache.get("agent-3") is None

    @pytest.mark.asyncio
    async def test_prewarm(self, config_cache: ConfigCache) -> None:
        """Test prewarming cache with agent configs."""
        agent_ids = ["agent-1", "agent-2", "agent-3"]

        # Mock git client
        mock_git = MagicMock()
        mock_git.load_agent_config = AsyncMock()

        async def mock_load(agent_id):
            from botburrow_agents.models import AgentConfig
            return AgentConfig(name=agent_id, type="native", cache_ttl=60)

        mock_git.load_agent_config.side_effect = mock_load

        # Prewarm
        cached = await config_cache.prewarm(agent_ids, mock_git)

        assert cached == 3
        assert await config_cache.get("agent-1") is not None
        assert await config_cache.get("agent-2") is not None
        assert await config_cache.get("agent-3") is not None

    @pytest.mark.asyncio
    async def test_prewarm_skip_already_cached(self, config_cache: ConfigCache) -> None:
        """Test prewarm skips already cached agents."""
        # Cache one agent
        await config_cache.set("agent-1", {"name": "agent1", "cache_ttl": 60})

        agent_ids = ["agent-1", "agent-2"]

        mock_git = MagicMock()
        mock_git.load_agent_config = AsyncMock()

        async def mock_load(agent_id):
            from botburrow_agents.models import AgentConfig
            return AgentConfig(name=agent_id, type="native", cache_ttl=60)

        mock_git.load_agent_config.side_effect = mock_load

        # Prewarm
        cached = await config_cache.prewarm(agent_ids, mock_git)

        # Only agent-2 should be loaded (agent-1 was already cached)
        assert cached == 1
        mock_git.load_agent_config.assert_called_once_with("agent-2")

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, config_cache: ConfigCache) -> None:
        """Test setting cache with custom TTL."""
        config = {"name": "test", "cache_ttl": 120}

        await config_cache.set("agent-1", config, ttl=120)

        result = await config_cache.get("agent-1")
        assert result == config


class TestLeaderElection:
    """Tests for leader election."""

    @pytest.fixture
    async def leader_election(self, fake_redis: fakeredis.FakeRedis) -> LeaderElection:
        """Create a leader election instance."""
        mock_redis_client = MagicMock()
        mock_redis_client._ensure_connected = AsyncMock(return_value=fake_redis)
        return LeaderElection(mock_redis_client, "instance-1")

    @pytest.mark.asyncio
    async def test_become_leader(self, leader_election: LeaderElection) -> None:
        """Test acquiring leadership."""
        result = await leader_election.try_become_leader()

        assert result is True
        assert leader_election.is_leader is True

    @pytest.mark.asyncio
    async def test_only_one_leader(self, fake_redis: fakeredis.FakeRedis) -> None:
        """Test that only one instance can be leader."""
        mock_client1 = MagicMock()
        mock_client1._ensure_connected = AsyncMock(return_value=fake_redis)
        mock_client2 = MagicMock()
        mock_client2._ensure_connected = AsyncMock(return_value=fake_redis)

        leader1 = LeaderElection(mock_client1, "instance-1")
        leader2 = LeaderElection(mock_client2, "instance-2")

        result1 = await leader1.try_become_leader()
        result2 = await leader2.try_become_leader()

        assert result1 is True
        assert result2 is False
        assert leader1.is_leader is True
        assert leader2.is_leader is False

    @requires_lua
    @pytest.mark.asyncio
    async def test_release_leadership(
        self, leader_election: LeaderElection, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Test releasing leadership."""
        await leader_election.try_become_leader()
        assert leader_election.is_leader is True

        await leader_election.release_leadership()
        assert leader_election.is_leader is False

        # Another instance can now become leader
        mock_client2 = MagicMock()
        mock_client2._ensure_connected = AsyncMock(return_value=fake_redis)
        leader2 = LeaderElection(mock_client2, "instance-2")

        result = await leader2.try_become_leader()
        assert result is True

    @pytest.mark.asyncio
    async def test_refresh_leadership(self, leader_election: LeaderElection) -> None:
        """Test that leader can refresh their leadership."""
        # Become leader
        await leader_election.try_become_leader()

        # Try again (should refresh)
        result = await leader_election.try_become_leader()
        assert result is True
        assert leader_election.is_leader is True


class TestJitter:
    """Tests for jitter function."""

    def test_jitter_returns_value_in_range(self) -> None:
        """Test that jitter returns value within expected range."""
        base = 10.0
        factor = 0.1

        for _ in range(100):
            result = jitter(base, factor)
            assert base * 0.9 <= result <= base * 1.1

    def test_jitter_default_factor(self) -> None:
        """Test jitter with default factor."""
        base = 100.0

        for _ in range(50):
            result = jitter(base)
            assert base * 0.9 <= result <= base * 1.1
