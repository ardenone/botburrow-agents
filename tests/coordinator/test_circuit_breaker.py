"""Tests for the per-agent circuit breaker.

Covers the closed/open/half-open state machine, activation gating in the
work queue (routing), recovery, runtime thresholds from the Redis config
cache, and observability helpers.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fakeredis import aioredis as fakeredis

from botburrow_agents.config import Settings
from botburrow_agents.coordinator.circuit_breaker import (
    AGENT_BACKOFF,
    AGENT_FAILURES,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from botburrow_agents.coordinator.work_queue import (
    QUEUE_HIGH,
    QUEUE_NORMAL,
    ConfigCache,
    WorkItem,
    WorkQueue,
)
from botburrow_agents.models import TaskType


def make_client(fake_redis: fakeredis.FakeRedis) -> MagicMock:
    """Wrap a FakeRedis in the RedisClient interface the components expect."""
    client = MagicMock()
    client._ensure_connected = AsyncMock(return_value=fake_redis)
    return client


@pytest.fixture
async def breaker(fake_redis: fakeredis.FakeRedis) -> CircuitBreaker:
    """Circuit breaker backed by fakeredis (no config cache)."""
    return CircuitBreaker(make_client(fake_redis))


@pytest.fixture
async def work_queue(
    fake_redis: fakeredis.FakeRedis, settings: Settings
) -> WorkQueue:
    """Work queue backed by fakeredis."""
    return WorkQueue(make_client(fake_redis), settings)


@pytest.fixture
async def config_cache(fake_redis: fakeredis.FakeRedis) -> ConfigCache:
    """Config cache backed by fakeredis."""
    return ConfigCache(make_client(fake_redis), ttl=60)


def work_item(agent_id: str, priority: str = "normal") -> WorkItem:
    """Build a work item for the given agent."""
    return WorkItem(
        agent_id=agent_id,
        agent_name=f"Agent {agent_id}",
        task_type=TaskType.INBOX,
        priority=priority,
    )


async def breaker_state(work_queue: WorkQueue, agent_id: str) -> CircuitState:
    """Read the circuit state through the queue's breaker."""
    return await work_queue.circuit_breaker.get_state(agent_id)


class TestCircuitStates:
    """Tests for state derivation from failures and backoff."""

    async def test_new_agent_is_closed(self, breaker: CircuitBreaker) -> None:
        """An agent with no failure history is CLOSED."""
        assert await breaker.get_state("agent-1") is CircuitState.CLOSED

    @pytest.mark.parametrize("failures", [0, 1, 4])
    async def test_failures_below_threshold_stay_closed(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis, failures: int
    ) -> None:
        """Consecutive failures below the threshold keep the circuit CLOSED."""
        for _ in range(failures):
            state = await breaker.record_failure("agent-1")
            assert state is CircuitState.CLOSED

        assert await breaker.get_state("agent-1") is CircuitState.CLOSED

        stored = await fake_redis.hget(AGENT_FAILURES, "agent-1")
        assert (int(stored) if stored else 0) == failures

    async def test_threshold_failure_opens_circuit(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Reaching the failure threshold opens the circuit."""
        for _ in range(4):
            await breaker.record_failure("agent-1")

        state = await breaker.record_failure("agent-1")  # 5th failure

        assert state is CircuitState.OPEN
        assert await breaker.get_state("agent-1") is CircuitState.OPEN

        backoff = await fake_redis.hget(AGENT_BACKOFF, "agent-1")
        assert backoff is not None
        assert float(backoff) > time.time()

    async def test_expired_backoff_is_half_open(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """An elapsed backoff window is HALF_OPEN (awaiting probe resolution)."""
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() - 1))

        assert await breaker.get_state("agent-1") is CircuitState.HALF_OPEN

    async def test_junk_backoff_value_resolves_closed(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """A corrupt backoff entry is tolerated as CLOSED, not a wedged circuit."""
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", "not-a-timestamp")

        assert await breaker.get_state("agent-1") is CircuitState.CLOSED
        assert await breaker.allow_activation("agent-1") is True

        # Driving the agent over the threshold overwrites the junk with a
        # valid epoch, so the breaker still opens
        for _ in range(5):
            await breaker.record_failure("agent-1")
        assert await breaker.get_state("agent-1") is CircuitState.OPEN
        backoff = await fake_redis.hget(AGENT_BACKOFF, "agent-1")
        assert float(backoff) > time.time()

    async def test_success_closes_circuit(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Success clears failures and backoff."""
        await breaker.record_failure("agent-1")
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() + 60))

        state = await breaker.record_success("agent-1")

        assert state is CircuitState.CLOSED
        assert await fake_redis.hget(AGENT_FAILURES, "agent-1") is None
        assert await fake_redis.hget(AGENT_BACKOFF, "agent-1") is None


class TestActivationGating:
    """Tests for the effect of the breaker on work-queue routing."""

    async def test_closed_agent_enqueues(
        self, work_queue: WorkQueue, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """CLOSED agents are routed to the queue normally."""
        assert await work_queue.enqueue(work_item("agent-1")) is True
        assert await fake_redis.llen(QUEUE_NORMAL) == 1

    async def test_open_agent_activation_skipped(
        self, work_queue: WorkQueue, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Activations for OPEN agents are skipped and never reach a queue."""
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() + 600))

        assert await work_queue.enqueue(work_item("agent-1")) is False
        assert await fake_redis.llen(QUEUE_NORMAL) == 0

    async def test_open_agent_skipped_while_others_routed(
        self, work_queue: WorkQueue
    ) -> None:
        """Routing is blocked only for the open agent - others still flow."""
        r = await work_queue.redis._ensure_connected()

        # Open the circuit for one agent by driving it over the threshold
        for _ in range(5):
            await work_queue.complete(work_item("broken-agent"), success=False)

        # New activations for the failing agent are skipped - even high priority
        assert await work_queue.enqueue(work_item("broken-agent", "high")) is False
        assert await r.llen(QUEUE_HIGH) == 0

        # A healthy agent's work is still enqueued and claimable
        assert await work_queue.enqueue(work_item("healthy-agent", "high")) is True
        claimed = await work_queue.claim("runner-1", timeout=1)
        assert claimed is not None
        assert claimed.agent_id == "healthy-agent"

    async def test_expired_backoff_admits_probe(
        self, work_queue: WorkQueue, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """A HALF_OPEN agent admits a probe activation and clears the entry."""
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() - 1))

        assert await work_queue.enqueue(work_item("agent-1")) is True
        # The stale entry is cleared once the probe is admitted; the probe's
        # outcome at complete() closes or re-opens the circuit
        assert await fake_redis.hget(AGENT_BACKOFF, "agent-1") is None

    async def test_force_bypasses_open_circuit(
        self, work_queue: WorkQueue, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """force=True enqueues even when the circuit is open."""
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() + 600))

        assert await work_queue.enqueue(work_item("agent-1"), force=True) is True

    async def test_claim_unaffected_by_other_agents_circuits(
        self, work_queue: WorkQueue, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Items already in the queue are claimable even if the circuit opens after."""
        assert await work_queue.enqueue(work_item("agent-1")) is True

        # Circuit opens while the item sits in the queue
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() + 600))

        claimed = await work_queue.claim("runner-1", timeout=1)
        assert claimed is not None
        assert claimed.agent_id == "agent-1"


class TestBytesModeRedis:
    """Tests for Redis clients that return bytes (decode_responses=False)."""

    async def test_state_machine_on_bytes_responses(self) -> None:
        """The breaker works against a Redis returning byte strings."""
        import fakeredis.aioredis as fakeredis_aio

        raw_redis = fakeredis_aio.FakeRedis()  # decode_responses defaults to False
        work_queue = WorkQueue(make_client(raw_redis), Settings())

        # Consecutive failures open the circuit
        for _ in range(5):
            await work_queue.complete(work_item("agent-1"), success=False)
        assert await breaker_state(work_queue, "agent-1") is CircuitState.OPEN

        # Open circuits skip activations
        assert await work_queue.enqueue(work_item("agent-1")) is False
        assert await raw_redis.llen(QUEUE_NORMAL) == 0

        # Recovery window elapses -> probe -> success -> closed
        await raw_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() - 1))
        assert await work_queue.enqueue(work_item("agent-1")) is True
        await work_queue.complete(work_item("agent-1"), success=True)
        assert await breaker_state(work_queue, "agent-1") is CircuitState.CLOSED


class TestRecovery:
    """Tests for the open -> half-open -> closed/open transitions."""

    async def test_full_recovery_lifecycle(
        self, work_queue: WorkQueue, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Failures open the circuit; a successful probe closes it and resets counting."""
        # Open the circuit
        for _ in range(5):
            await work_queue.complete(work_item("agent-1"), success=False)
        assert await breaker_state(work_queue, "agent-1") is CircuitState.OPEN

        # Recovery window elapses
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() - 1))
        assert await breaker_state(work_queue, "agent-1") is CircuitState.HALF_OPEN

        # Probe activation goes through and succeeds -> circuit closed
        assert await work_queue.enqueue(work_item("agent-1")) is True
        assert await work_queue.claim("runner-1", timeout=1) is not None
        await work_queue.complete(work_item("agent-1"), success=True)

        assert await breaker_state(work_queue, "agent-1") is CircuitState.CLOSED
        assert await fake_redis.hget(AGENT_FAILURES, "agent-1") is None

        # Failure counting restarts from zero
        for _ in range(4):
            await work_queue.complete(work_item("agent-1"), success=False)
        assert await breaker_state(work_queue, "agent-1") is CircuitState.CLOSED

    async def test_probe_failure_reopens_with_escalated_backoff(
        self, work_queue: WorkQueue, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """A failed probe re-opens the circuit with a longer backoff."""
        for _ in range(5):
            await work_queue.complete(work_item("agent-1"), success=False)

        r = await work_queue.redis._ensure_connected()
        first_backoff = float(await r.hget(AGENT_BACKOFF, "agent-1"))

        # Recovery window elapses, probe is admitted and fails
        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() - 1))
        await work_queue.complete(work_item("agent-1"), success=False)

        assert await breaker_state(work_queue, "agent-1") is CircuitState.OPEN
        second_backoff = float(await r.hget(AGENT_BACKOFF, "agent-1"))
        # 6th failure: base 60s * 2^(6-5) = 120s, escalated past the first
        assert second_backoff - time.time() > first_backoff - time.time()
        assert second_backoff - time.time() >= 119

    async def test_backoff_escalation_capped_at_max(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Escalation doubles per extra failure up to backoff_max."""
        expected = [60, 120, 240, 480, 960, 1920, 3600, 3600]
        for index, expected_secs in enumerate(expected, start=5):
            await fake_redis.hset(AGENT_FAILURES, "agent-1", str(index - 1))

            await breaker.record_failure("agent-1")

            status = await breaker.get_status("agent-1")
            assert status["backoff_seconds_remaining"] == pytest.approx(
                expected_secs, abs=2
            ), f"failure #{index}: expected ~{expected_secs}s backoff"

    async def test_success_clears_backoff_metric_state(
        self, work_queue: WorkQueue
    ) -> None:
        """A success after opening removes the agent from backoff tracking."""
        for _ in range(5):
            await work_queue.complete(work_item("agent-1"), success=False)

        stats = await work_queue.get_queue_stats()
        assert stats["agents_in_backoff"] == 1

        await work_queue.complete(work_item("agent-1"), success=True)

        stats = await work_queue.get_queue_stats()
        assert stats["agents_in_backoff"] == 0


class TestRuntimeConfig:
    """Tests for thresholds configured via the Redis config cache."""

    async def test_save_and_load_runtime_config(self, config_cache: ConfigCache) -> None:
        """Runtime config round-trips through the Redis config cache."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            backoff_base=30,
            backoff_max=600,
        )

        await CircuitBreaker.save_runtime_config(config_cache, config)
        loaded = await CircuitBreaker.load_runtime_config(config_cache)

        assert loaded == config

    async def test_load_missing_config_returns_none(self, config_cache: ConfigCache) -> None:
        """No stored config yields None (defaults apply)."""
        assert await CircuitBreaker.load_runtime_config(config_cache) is None

    async def test_breaker_picks_up_cached_thresholds(
        self,
        fake_redis: fakeredis.FakeRedis,
        config_cache: ConfigCache,
    ) -> None:
        """A breaker with a config cache opens at the configured threshold."""
        await CircuitBreaker.save_runtime_config(
            config_cache, CircuitBreakerConfig(failure_threshold=2)
        )

        breaker = CircuitBreaker(make_client(fake_redis), config_cache=config_cache)

        assert await breaker.record_failure("agent-1") is CircuitState.CLOSED
        # Second failure crosses the runtime-configured threshold of 2
        assert await breaker.record_failure("agent-1") is CircuitState.OPEN

    async def test_partial_config_keeps_defaults(
        self,
        fake_redis: fakeredis.FakeRedis,
        config_cache: ConfigCache,
    ) -> None:
        """A partial config entry only overrides the keys it contains."""
        await CircuitBreaker.save_runtime_config(
            config_cache, CircuitBreakerConfig(failure_threshold=2)
        )

        breaker = CircuitBreaker(make_client(fake_redis), config_cache=config_cache)
        await breaker.record_failure("agent-1")
        await breaker.record_failure("agent-1")

        status = await breaker.get_status("agent-1")
        assert status["state"] == CircuitState.OPEN.value
        # Unspecified backoff knobs kept code defaults (60s base)
        assert status["backoff_seconds_remaining"] == pytest.approx(60, abs=2)
        assert status["thresholds"]["backoff_max"] == 3600

    async def test_pinned_override_wins_over_config_cache(
        self,
        fake_redis: fakeredis.FakeRedis,
        config_cache: ConfigCache,
    ) -> None:
        """Programmatically pinned thresholds take precedence over the cache."""
        await CircuitBreaker.save_runtime_config(
            config_cache, CircuitBreakerConfig(failure_threshold=2)
        )

        breaker = CircuitBreaker(
            make_client(fake_redis),
            config_cache=config_cache,
            failure_threshold=7,
        )

        for _ in range(2):
            assert await breaker.record_failure("agent-1") is CircuitState.CLOSED

        assert await breaker.get_state("agent-1") is CircuitState.CLOSED

    async def test_refresh_honors_interval(
        self,
        fake_redis: fakeredis.FakeRedis,
        config_cache: ConfigCache,
    ) -> None:
        """Config cache reads happen at most once per refresh interval."""
        await CircuitBreaker.save_runtime_config(
            config_cache, CircuitBreakerConfig(failure_threshold=3)
        )
        breaker = CircuitBreaker(make_client(fake_redis), config_cache=config_cache)

        # First failure refreshes: threshold is now 3, count 1 -> still closed
        assert await breaker.record_failure("agent-1") is CircuitState.CLOSED

        # Operator tightens the threshold to 1, but the refresh interval has
        # not elapsed - the breaker keeps using the value it already loaded
        await CircuitBreaker.save_runtime_config(
            config_cache, CircuitBreakerConfig(failure_threshold=1)
        )
        assert await breaker.record_failure("agent-1") is CircuitState.CLOSED

        # Interval elapses -> next failure sees the new threshold
        breaker._config_loaded_at = 0.0
        assert await breaker.record_failure("agent-1") is CircuitState.OPEN

    async def test_config_refresh_failure_keeps_previous_config(
        self,
        fake_redis: fakeredis.FakeRedis,
        config_cache: ConfigCache,
    ) -> None:
        """A broken config cache read falls back to the previously loaded config."""
        await CircuitBreaker.save_runtime_config(
            config_cache, CircuitBreakerConfig(failure_threshold=2)
        )
        breaker = CircuitBreaker(make_client(fake_redis), config_cache=config_cache)
        assert await breaker.record_failure("agent-1") is CircuitState.CLOSED

        # Corrupt the stored config; refresh errors must not raise
        await fake_redis.set(
            f"cache:agent:{CircuitBreaker.CONFIG_CACHE_ID}", "not-json{"
        )
        breaker._config_loaded_at = 0.0
        assert await breaker.record_failure("agent-1") is CircuitState.OPEN

    async def test_removed_config_entry_keeps_last_loaded_config(
        self,
        fake_redis: fakeredis.FakeRedis,
        config_cache: ConfigCache,
    ) -> None:
        """A deleted cache entry leaves the last-loaded thresholds in effect."""
        await CircuitBreaker.save_runtime_config(
            config_cache, CircuitBreakerConfig(failure_threshold=2)
        )
        breaker = CircuitBreaker(make_client(fake_redis), config_cache=config_cache)
        assert await breaker.record_failure("agent-1") is CircuitState.CLOSED

        # Operator removes the shared entry; a refresh must keep the loaded
        # threshold (2) rather than silently reverting to the default (5)
        await fake_redis.delete(f"cache:agent:{CircuitBreaker.CONFIG_CACHE_ID}")
        breaker._config_loaded_at = 0.0
        assert await breaker.record_failure("agent-1") is CircuitState.OPEN

    async def test_backoff_aliases_pin_breaker_over_config_cache(
        self,
        fake_redis: fakeredis.FakeRedis,
        settings: Settings,
        config_cache: ConfigCache,
    ) -> None:
        """The WorkQueue.backoff_base/backoff_max aliases beat the cache.

        Pinned knobs survive a config-cache refresh while unpinned ones
        (here the failure threshold) still follow the shared config.
        """
        await CircuitBreaker.save_runtime_config(
            config_cache,
            CircuitBreakerConfig(failure_threshold=2, backoff_base=10, backoff_max=100),
        )
        work_queue = WorkQueue(
            make_client(fake_redis), settings, config_cache=config_cache
        )
        work_queue.backoff_base = 30
        work_queue.backoff_max = 500

        # Second failure opens the circuit at the cache-driven threshold of 2,
        # using the pinned 30s base backoff instead of the cache's 10s
        await work_queue.complete(work_item("agent-1"), success=False)
        await work_queue.complete(work_item("agent-1"), success=False)

        breaker = work_queue.circuit_breaker
        assert await breaker.get_state("agent-1") is CircuitState.OPEN
        assert breaker.config.failure_threshold == 2
        assert breaker.config.backoff_base == 30
        assert breaker.config.backoff_max == 500

        status = await breaker.get_status("agent-1")
        assert status["backoff_seconds_remaining"] == pytest.approx(30, abs=2)

    async def test_work_queue_threshold_aliases_pin_breaker(
        self,
        fake_redis: fakeredis.FakeRedis,
        settings: Settings,
    ) -> None:
        """The WorkQueue.max_failures alias drives the breaker threshold."""
        work_queue = WorkQueue(make_client(fake_redis), settings)
        work_queue.max_failures = 2

        assert work_queue.circuit_breaker.config.failure_threshold == 2

        await work_queue.complete(work_item("agent-1"), success=False)
        await work_queue.complete(work_item("agent-1"), success=False)

        assert await breaker_state(work_queue, "agent-1") is CircuitState.OPEN


class TestObservability:
    """Tests for breaker status introspection."""

    async def test_get_status_per_state(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Status reports state, failure count, and remaining backoff."""
        closed = await breaker.get_status("agent-1")
        assert closed["state"] == CircuitState.CLOSED.value
        assert closed["failures"] == 0
        assert closed["backoff_seconds_remaining"] == 0.0

        for _ in range(3):
            await breaker.record_failure("agent-1")
        counting = await breaker.get_status("agent-1")
        assert counting["state"] == CircuitState.CLOSED.value
        assert counting["failures"] == 3

        await fake_redis.hset(AGENT_BACKOFF, "agent-1", str(time.time() + 120))
        opening = await breaker.get_status("agent-1")
        assert opening["state"] == CircuitState.OPEN.value
        assert opening["backoff_seconds_remaining"] == pytest.approx(120, abs=2)
        assert opening["thresholds"]["failure_threshold"] == 5

    async def test_get_status_tolerates_junk_failure_count(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """A corrupt failure count is reported as zero, not an error."""
        await fake_redis.hset(AGENT_FAILURES, "agent-1", "garbage")

        status = await breaker.get_status("agent-1")

        assert status["state"] == CircuitState.CLOSED.value
        assert status["failures"] == 0

    async def test_get_all_states_classifies_agents(
        self, breaker: CircuitBreaker, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """Agents with backoff entries are classified; closed agents are absent."""
        await fake_redis.hset(AGENT_BACKOFF, "open-agent", str(time.time() + 300))
        await fake_redis.hset(AGENT_BACKOFF, "probing-agent", str(time.time() - 1))

        states = await breaker.get_all_states()

        assert states["open-agent"] is CircuitState.OPEN
        assert states["probing-agent"] is CircuitState.HALF_OPEN
        assert "healthy-agent" not in states


class TestReset:
    """Tests for manual circuit reset."""

    async def test_clear_backoff_resets_circuit(
        self, work_queue: WorkQueue, fake_redis: fakeredis.FakeRedis
    ) -> None:
        """WorkQueue.clear_backoff forces the circuit closed."""
        for _ in range(5):
            await work_queue.complete(work_item("agent-1"), success=False)
        assert await breaker_state(work_queue, "agent-1") is CircuitState.OPEN

        await work_queue.clear_backoff("agent-1")

        assert await breaker_state(work_queue, "agent-1") is CircuitState.CLOSED
        assert await fake_redis.hget(AGENT_FAILURES, "agent-1") is None
        assert await fake_redis.hget(AGENT_BACKOFF, "agent-1") is None

        # Agent is routable again immediately
        assert await work_queue.enqueue(work_item("agent-1")) is True
