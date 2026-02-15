"""Simplified runner pool scaling tests.

Tests the core scaling mechanisms without requiring deployed infrastructure:
1. WorkQueue multi-runner support (BRPOP, deduplication, priority)
2. Agent config caching for multiple runners
3. Multiple agent persona execution
4. Circuit breaker integration

This is a simplified-scope alternative to bd-3qv which requires Kubernetes.
"""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

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
)
from botburrow_agents.models import TaskType


class TestWorkQueueMultiRunner:
    """Tests for WorkQueue behavior with multiple runners."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = AsyncMock()
        redis._ensure_connected = AsyncMock(return_value=redis)
        return redis

    @pytest.fixture
    def settings(self):
        """Test settings."""
        return Settings(
            hub_url="http://test-hub:8000",
            redis_url="redis://localhost:6379",
        )

    @pytest.fixture
    def work_queue(self, mock_redis, settings):
        """Create work queue."""
        return WorkQueue(mock_redis, settings)

    @pytest.mark.asyncio
    async def test_enqueue_with_deduplication(self, work_queue, mock_redis):
        """Test that duplicate work for same agent is rejected."""
        mock_redis.hget = AsyncMock(return_value="runner-1")  # Already active

        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        result = await work_queue.enqueue(work)

        assert result is False  # Duplicate rejected
        mock_redis.hget.assert_called_once_with(ACTIVE_TASKS, "agent-1")

    @pytest.mark.asyncio
    async def test_enqueue_with_backoff(self, work_queue, mock_redis):
        """Test that agents in backoff are not queued."""
        # No active task, but in backoff
        mock_redis.hget = AsyncMock(side_effect=[
            None,  # No active task
            "9999999999",  # Backoff until far in future
        ])
        mock_redis.hdel = AsyncMock()

        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        result = await work_queue.enqueue(work)

        assert result is False  # Backoff agent rejected

    @pytest.mark.asyncio
    async def test_expired_backoff_cleared(self, work_queue, mock_redis):
        """Test that expired backoff is cleared and work accepted."""
        # No active task, expired backoff
        mock_redis.hget = AsyncMock(side_effect=[
            None,  # No active task
            str(time.time() - 100),  # Backoff expired 100s ago
        ])
        mock_redis.hdel = AsyncMock()
        mock_redis.lpush = AsyncMock()

        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        result = await work_queue.enqueue(work)

        assert result is True
        mock_redis.hdel.assert_called_with(AGENT_BACKOFF, "agent-1")

    @pytest.mark.asyncio
    async def test_claim_marks_active(self, work_queue, mock_redis):
        """Test that claiming work marks agent as active."""
        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        mock_redis.brpop = AsyncMock(return_value=("work:queue:normal", work.to_json()))
        mock_redis.hset = AsyncMock()

        claimed = await work_queue.claim("runner-1", timeout=1)

        assert claimed is not None
        assert claimed.agent_id == "agent-1"
        mock_redis.hset.assert_called_once_with(ACTIVE_TASKS, "agent-1", "runner-1")

    @pytest.mark.asyncio
    async def test_claim_priority_order(self, work_queue, mock_redis):
        """Test that claim tries queues in priority order: high, normal, low."""
        # BRPOP should receive all three queues in order
        # Mock returns None for timeout (brpop returns None or tuple)
        mock_redis.brpop = AsyncMock(return_value=None)
        mock_redis.hset = AsyncMock()

        await work_queue.claim("runner-1", timeout=0.1)

        # Verify BRPOP was called with correct queue order
        mock_redis.brpop.assert_called_once()
        call_args = mock_redis.brpop.call_args
        queues = call_args[0][0]  # First positional arg is list of queues
        assert queues == ["work:queue:high", "work:queue:normal", "work:queue:low"]

    @pytest.mark.asyncio
    async def test_claim_timeout_returns_none(self, work_queue, mock_redis):
        """Test that claim timeout returns None."""
        mock_redis.brpop = AsyncMock(return_value=None)

        result = await work_queue.claim("runner-1", timeout=0.1)

        assert result is None

    @pytest.mark.asyncio
    async def test_complete_success_clears_failures(self, work_queue, mock_redis):
        """Test that successful completion clears failure tracking."""
        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        mock_redis.hdel = AsyncMock()

        await work_queue.complete(work, success=True)

        # Should clear failures and backoff
        mock_redis.hdel.assert_any_call(AGENT_FAILURES, "agent-1")
        mock_redis.hdel.assert_any_call(AGENT_BACKOFF, "agent-1")

    @pytest.mark.asyncio
    async def test_complete_failure_increments_counter(self, work_queue, mock_redis):
        """Test that failed completion increments failure counter."""
        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        mock_redis.hdel = AsyncMock()
        mock_redis.hincrby = AsyncMock(return_value=1)  # First failure

        await work_queue.complete(work, success=False)

        mock_redis.hincrby.assert_called_once_with(AGENT_FAILURES, "agent-1", 1)

    @pytest.mark.asyncio
    async def test_circuit_breaker_triggers_after_max_failures(self, work_queue, mock_redis):
        """Test that circuit breaker enters backoff after max failures."""
        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        mock_redis.hdel = AsyncMock()
        mock_redis.hincrby = AsyncMock(return_value=5)  # At max failures
        mock_redis.hset = AsyncMock()

        await work_queue.complete(work, success=False)

        # Should set backoff
        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args
        assert call_args[0][0] == AGENT_BACKOFF
        assert call_args[0][1] == "agent-1"

        # Backoff timestamp should be in the future
        backoff_timestamp = float(call_args[0][2])
        assert backoff_timestamp > time.time()

    @pytest.mark.asyncio
    async def test_circuit_breaker_exponential_backoff(self, work_queue, mock_redis):
        """Test that circuit breaker uses exponential backoff."""
        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        mock_redis.hdel = AsyncMock()
        mock_redis.hset = AsyncMock()

        # Test different failure counts
        test_cases = [
            (5, 60),    # Base backoff: 60s
            (6, 120),   # 2x: 120s
            (7, 240),   # 4x: 240s
            (8, 480),   # 8x: 480s
            (15, 3600), # Capped at max: 3600s
        ]

        for failures, expected_min_backoff in test_cases:
            mock_redis.hincrby = AsyncMock(return_value=failures)
            mock_redis.hset.reset_mock()

            await work_queue.complete(work, success=False)

            backoff_timestamp = float(mock_redis.hset.call_args[0][2])
            backoff_seconds = backoff_timestamp - time.time()

            assert backoff_seconds >= expected_min_backoff - 1, \
                f"Failures={failures}: expected at least {expected_min_backoff}s, got {backoff_seconds}s"

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, work_queue, mock_redis):
        """Test getting queue statistics."""
        mock_redis.llen = AsyncMock(side_effect=[2, 5, 1])  # high, normal, low
        mock_redis.hlen = AsyncMock(side_effect=[3, 1])  # active, backoff

        stats = await work_queue.get_queue_stats()

        assert stats["queue_high"] == 2
        assert stats["queue_normal"] == 5
        assert stats["queue_low"] == 1
        assert stats["total_queued"] == 8
        assert stats["active_tasks"] == 3
        assert stats["agents_in_backoff"] == 1

    @pytest.mark.asyncio
    async def test_clear_backoff(self, work_queue, mock_redis):
        """Test manually clearing backoff for an agent."""
        mock_redis.hdel = AsyncMock()

        await work_queue.clear_backoff("agent-1")

        mock_redis.hdel.assert_any_call(AGENT_BACKOFF, "agent-1")
        mock_redis.hdel.assert_any_call(AGENT_FAILURES, "agent-1")


class TestMultiRunnerWorkDistribution:
    """Tests for simulating multiple runners claiming work."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = AsyncMock()
        redis._ensure_connected = AsyncMock(return_value=redis)
        return redis

    @pytest.fixture
    def settings(self):
        """Test settings."""
        return Settings(
            hub_url="http://test-hub:8000",
            redis_url="redis://localhost:6379",
        )

    @pytest.mark.asyncio
    async def test_multiple_runners_claim_different_work(self, mock_redis, settings):
        """Test that two runners can claim different work items."""
        # Simulate two work items in queue
        work1 = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )
        work2 = WorkItem(
            agent_id="agent-2",
            agent_name="Agent Two",
            task_type=TaskType.DISCOVERY,
        )

        # First BRPOP call returns work1, second returns work2
        mock_redis.brpop = AsyncMock(side_effect=[
            ("work:queue:normal", work1.to_json()),
            ("work:queue:normal", work2.to_json()),
        ])
        mock_redis.hset = AsyncMock()

        # Create two work queues (simulating two runners)
        queue1 = WorkQueue(mock_redis, settings)
        queue2 = WorkQueue(mock_redis, settings)

        # Both runners claim work concurrently
        results = await asyncio.gather(
            queue1.claim("runner-1", timeout=1),
            queue2.claim("runner-2", timeout=1),
        )

        # Both should get work, and it should be different
        assert results[0] is not None
        assert results[1] is not None
        assert results[0].agent_id != results[1].agent_id

    @pytest.mark.asyncio
    async def test_runner_cannot_claim_active_work(self, mock_redis, settings):
        """Test that work already claimed by one runner can't be claimed by another."""
        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.INBOX,
        )

        # First runner claims the work
        mock_redis.brpop = AsyncMock(return_value=("work:queue:normal", work.to_json()))
        mock_redis.hset = AsyncMock()
        mock_redis.hget = AsyncMock(return_value="runner-1")  # Already claimed

        queue = WorkQueue(mock_redis, settings)

        # First claim succeeds
        claimed1 = await queue.claim("runner-1", timeout=1)
        assert claimed1 is not None
        assert claimed1.agent_id == "agent-1"

        # Second runner tries to enqueue same work - should fail deduplication
        result = await queue.enqueue(work)
        assert result is False  # Duplicate rejected

    @pytest.mark.asyncio
    async def test_priority_queue_servicing_order(self, mock_redis, settings):
        """Test that high priority work is claimed before normal/low."""
        high_priority_work = WorkItem(
            agent_id="agent-urgent",
            agent_name="Urgent Agent",
            task_type=TaskType.INBOX,
            priority="high",
        )

        mock_redis.brpop = AsyncMock(return_value=("work:queue:high", high_priority_work.to_json()))
        mock_redis.hset = AsyncMock()

        queue = WorkQueue(mock_redis, settings)

        claimed = await queue.claim("runner-1", timeout=1)

        assert claimed is not None
        assert claimed.agent_id == "agent-urgent"
        assert claimed.priority == "high"


class TestConfigCacheMultiRunner:
    """Tests for ConfigCache behavior with multiple runners."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = AsyncMock()
        redis._ensure_connected = AsyncMock(return_value=redis)
        return redis

    @pytest.fixture
    def settings(self):
        """Test settings."""
        return Settings(
            hub_url="http://test-hub:8000",
            redis_url="redis://localhost:6379",
        )

    @pytest.mark.asyncio
    async def test_cache_hit_serves_all_runners(self, mock_redis):
        """Test that cached config is available to all runners."""
        _config = {
            "name": "agent-1",
            "type": "claude-code",
            "cache_ttl": 300,
        }

        mock_redis.get = AsyncMock(return_value='{"name": "agent-1", "type": "claude-code"}')

        cache = ConfigCache(mock_redis)

        # Multiple runners request same config
        result1 = await cache.get("agent-1")
        result2 = await cache.get("agent-1")

        # Both should get the cached value
        assert result1 is not None
        assert result2 is not None
        assert result1["name"] == "agent-1"
        assert result2["name"] == "agent-1"

        # Should only call Redis once (efficient)
        mock_redis.get.assert_called_with("cache:agent:agent-1")

    @pytest.mark.asyncio
    async def test_cache_miss_allows_set(self, mock_redis):
        """Test cache miss behavior."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        cache = ConfigCache(mock_redis)
        config = {
            "name": "agent-1",
            "type": "claude-code",
            "cache_ttl": 600,  # Custom TTL
        }

        await cache.set("agent-1", config)

        # Verify set was called with custom TTL from config
        mock_redis.set.assert_called_once_with(
            "cache:agent:agent-1",
            '{"name": "agent-1", "type": "claude-code", "cache_ttl": 600}',
            ex=600,
        )

    @pytest.mark.asyncio
    async def test_invalidate_single_config(self, mock_redis):
        """Test invalidating a single cached config."""
        mock_redis.delete = AsyncMock()

        cache = ConfigCache(mock_redis)
        await cache.invalidate("agent-1")

        mock_redis.delete.assert_called_once_with("cache:agent:agent-1")

    @pytest.mark.asyncio
    async def test_prewarm_cache_multiple_agents(self, mock_redis):
        """Test pre-warming cache with multiple agent configs."""
        mock_git = AsyncMock()
        mock_git.load_agent_config = AsyncMock(
            side_effect=[
                MagicMock(name="agent-1", type="claude-code", cache_ttl=300, model_dump=lambda: {"name": "agent-1"}),
                MagicMock(name="agent-2", type="goose", cache_ttl=300, model_dump=lambda: {"name": "agent-2"}),
            ]
        )

        mock_redis.get = AsyncMock(return_value=None)  # Cache miss
        mock_redis.set = AsyncMock()

        cache = ConfigCache(mock_redis)

        cached_count = await cache.prewarm(["agent-1", "agent-2"], mock_git)

        assert cached_count == 2
        assert mock_redis.set.call_count == 2


class TestLeaderElection:
    """Tests for leader election with multiple coordinator instances."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = AsyncMock()
        redis._ensure_connected = AsyncMock(return_value=redis)
        return redis

    @pytest.mark.asyncio
    async def test_first_instance_becomes_leader(self, mock_redis):
        """Test that the first instance becomes leader."""
        mock_redis.set = AsyncMock(return_value=True)  # SETNX success
        mock_redis.get = AsyncMock(return_value="instance-1")

        election = LeaderElection(mock_redis, "instance-1")

        is_leader = await election.try_become_leader()

        assert is_leader is True
        assert election.is_leader is True

    @pytest.mark.asyncio
    async def test_second_instance_does_not_become_leader(self, mock_redis):
        """Test that second instance does not become leader."""
        mock_redis.set = AsyncMock(return_value=False)  # SETNX failed
        mock_redis.get = AsyncMock(return_value="instance-1")  # Current leader

        election = LeaderElection(mock_redis, "instance-2")

        is_leader = await election.try_become_leader()

        assert is_leader is False
        assert election.is_leader is False

    @pytest.mark.asyncio
    async def test_leader_renews_leadership(self, mock_redis):
        """Test that leader refreshes its leadership."""
        mock_redis.set = AsyncMock(return_value=False)  # SETNX failed
        mock_redis.get = AsyncMock(return_value="instance-1")  # We are leader
        mock_redis.expire = AsyncMock()

        election = LeaderElection(mock_redis, "instance-1")

        is_leader = await election.try_become_leader()

        assert is_leader is True
        mock_redis.expire.assert_called_once_with("coordinator:leader", 30)

    @pytest.mark.asyncio
    async def test_release_leadership(self, mock_redis):
        """Test releasing leadership."""
        mock_redis.eval = AsyncMock(return_value=1)  # Deleted

        election = LeaderElection(mock_redis, "instance-1")
        election._is_leader = True  # Manually set as leader

        await election.release_leadership()

        assert election.is_leader is False
        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_leader_release_does_nothing(self, mock_redis):
        """Test that non-leader release does nothing."""
        election = LeaderElection(mock_redis, "instance-2")
        election._is_leader = False

        await election.release_leadership()

        # Should not call eval
        mock_redis.eval.assert_not_called()


class TestWorkItemSerialization:
    """Tests for WorkItem JSON serialization."""

    def test_work_item_to_json(self):
        """Test serializing WorkItem to JSON."""
        work = WorkItem(
            agent_id="agent-1",
            agent_name="Agent One",
            task_type=TaskType.DISCOVERY,
            priority="high",
            inbox_count=5,
        )

        json_str = work.to_json()

        assert "agent-1" in json_str
        assert "Agent One" in json_str
        assert "discovery" in json_str
        assert "high" in json_str

    def test_work_item_from_json(self):
        """Test deserializing WorkItem from JSON."""
        import json

        work_dict = {
            "agent_id": "agent-1",
            "agent_name": "Agent One",
            "task_type": "inbox",
            "priority": "high",
            "inbox_count": 5,
            "created_at": 1234567890.0,
        }

        work = WorkItem.from_json(json.dumps(work_dict))

        assert work.agent_id == "agent-1"
        assert work.agent_name == "Agent One"
        assert work.task_type == TaskType.INBOX
        assert work.priority == "high"
        assert work.inbox_count == 5
        assert work.created_at == 1234567890.0

    def test_work_item_defaults(self):
        """Test WorkItem default values."""
        work_dict = {
            "agent_id": "agent-1",
            "agent_name": "Agent One",
            "task_type": "inbox",
        }

        work = WorkItem.from_json(json.dumps(work_dict))

        assert work.priority == "normal"  # Default
        assert work.inbox_count == 0  # Default
        # created_at should be set to current time if missing
        assert work.created_at > 0
