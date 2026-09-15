"""Circuit breaker for repeatedly failing agents.

Implements the classic closed/open/half-open state machine per agent:

- **CLOSED** - normal operation. Failures are counted; activations proceed.
- **OPEN** - the failure threshold has been reached. Activations for the
  agent are skipped entirely (the coordinator never enqueues work for it).
- **HALF_OPEN** - the recovery window has elapsed. A single probe
  activation is admitted; success closes the circuit, failure re-opens it
  immediately with an escalated backoff.

The state itself is not stored - it is *derived* from two Redis hashes
shared with the work queue:

- ``work:failures`` (``AGENT_FAILURES``): consecutive failure count per agent
- ``work:backoff`` (``AGENT_BACKOFF``): epoch timestamp until which the
  agent's circuit is open

Deriving state keeps the layout backward compatible (older coordinators
wrote the same hashes) and lets the OPEN -> HALF_OPEN transition happen
lazily on read, with no background sweeper.

Thresholds are configurable at runtime through the Redis config cache
(``ConfigCache``): a ``CircuitBreakerConfig`` stored under
``CONFIG_CACHE_ID`` is picked up by every coordinator/runner within
``CONFIG_REFRESH_INTERVAL`` seconds, without a restart. Values pinned via
``set_thresholds`` (or the ``WorkQueue.max_failures`` aliases) take
precedence over the shared config.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from botburrow_agents.clients.redis import RedisClient
    from botburrow_agents.coordinator.work_queue import ConfigCache

logger = structlog.get_logger(__name__)

# Redis keys (shared with WorkQueue - the queue's failure/backoff tracking
# and the circuit breaker state machine are the same data)
AGENT_FAILURES = "work:failures"  # Hash: agent_id -> consecutive failure count
AGENT_BACKOFF = "work:backoff"  # Hash: agent_id -> circuit-open-until timestamp


class CircuitState(StrEnum):
    """Circuit breaker state for an agent."""

    CLOSED = "closed"  # Normal operation, failures being counted
    OPEN = "open"  # Threshold exceeded, activations skipped
    HALF_OPEN = "half_open"  # Recovery window elapsed, probe allowed


@dataclass
class CircuitBreakerConfig:
    """Runtime-tunable circuit breaker thresholds.

    Persisted as JSON in the Redis config cache under
    ``CircuitBreaker.CONFIG_CACHE_ID`` so operators can tune the breaker
    without redeploying.
    """

    # Consecutive failures before the circuit opens
    failure_threshold: int = 5
    # First backoff duration in seconds (doubles per extra failure)
    backoff_base: int = 60
    # Upper bound on the backoff duration in seconds
    backoff_max: int = 3600

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for the config cache."""
        return {
            "failure_threshold": self.failure_threshold,
            "backoff_base": self.backoff_base,
            "backoff_max": self.backoff_max,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CircuitBreakerConfig:
        """Build from a (possibly partial) config cache entry.

        Unknown keys are ignored; missing keys fall back to defaults.
        """
        defaults = cls()
        kwargs: dict[str, Any] = {}
        for field in fields(cls):
            if field.name in data:
                raw = data[field.name]
                kwargs[field.name] = type(getattr(defaults, field.name))(raw)
        return cls(**kwargs)


class CircuitBreaker:
    """Per-agent circuit breaker backed by Redis.

    Args:
        redis: Redis client (shared with the work queue)
        config_cache: Optional ConfigCache to read runtime thresholds from.
            When provided, thresholds stored in the Redis config cache are
            picked up within ``CONFIG_REFRESH_INTERVAL`` seconds.
        failure_threshold: Optional pinned failure threshold override
        backoff_base: Optional pinned base backoff override
        backoff_max: Optional pinned max backoff override
    """

    # Config cache entry holding the shared runtime thresholds
    CONFIG_CACHE_ID = "_circuit_breaker"
    # How often to re-read thresholds from the config cache (seconds)
    CONFIG_REFRESH_INTERVAL = 60.0
    # TTL for the config cache entry written by save_runtime_config
    CONFIG_TTL = 86400  # 24 hours

    def __init__(
        self,
        redis: RedisClient,
        config_cache: ConfigCache | None = None,
        *,
        failure_threshold: int | None = None,
        backoff_base: int | None = None,
        backoff_max: int | None = None,
    ) -> None:
        self.redis = redis
        self.config_cache = config_cache
        self.config = CircuitBreakerConfig()
        self._pinned: set[str] = set()
        self._config_loaded_at = 0.0

        self.set_thresholds(
            failure_threshold=failure_threshold,
            backoff_base=backoff_base,
            backoff_max=backoff_max,
        )

    # ------------------------------------------------------------------
    # Runtime configuration
    # ------------------------------------------------------------------

    def set_thresholds(
        self,
        *,
        failure_threshold: int | None = None,
        backoff_base: int | None = None,
        backoff_max: int | None = None,
    ) -> None:
        """Pin threshold overrides programmatically.

        Pinned values win over the Redis config cache on refresh.
        """
        if failure_threshold is not None:
            self.config.failure_threshold = failure_threshold
            self._pinned.add("failure_threshold")
        if backoff_base is not None:
            self.config.backoff_base = backoff_base
            self._pinned.add("backoff_base")
        if backoff_max is not None:
            self.config.backoff_max = backoff_max
            self._pinned.add("backoff_max")

    @classmethod
    async def load_runtime_config(cls, config_cache: ConfigCache) -> CircuitBreakerConfig | None:
        """Read the shared thresholds from the Redis config cache."""
        data = await config_cache.get(cls.CONFIG_CACHE_ID)
        if not data:
            return None
        return CircuitBreakerConfig.from_dict(data)

    @classmethod
    async def save_runtime_config(
        cls,
        config_cache: ConfigCache,
        config: CircuitBreakerConfig,
    ) -> None:
        """Persist shared thresholds to the Redis config cache.

        All coordinators and runners pick them up within
        ``CONFIG_REFRESH_INTERVAL`` seconds.
        """
        await config_cache.set(cls.CONFIG_CACHE_ID, config.to_dict(), ttl=cls.CONFIG_TTL)
        logger.info("circuit_breaker_config_saved", **config.to_dict())

    async def _refresh_config_if_stale(self) -> None:
        """Re-read thresholds from the config cache at most once per interval."""
        if self.config_cache is None:
            return

        now = time.time()
        if now - self._config_loaded_at < self.CONFIG_REFRESH_INTERVAL:
            return
        self._config_loaded_at = now

        try:
            data = await self.config_cache.get(self.CONFIG_CACHE_ID)
        except Exception as exc:
            logger.warning("circuit_breaker_config_refresh_failed", error=str(exc))
            return

        if not data:
            return

        remote = CircuitBreakerConfig.from_dict(data)
        for field in fields(CircuitBreakerConfig):
            if field.name not in self._pinned:
                setattr(self.config, field.name, getattr(remote, field.name))
        logger.debug("circuit_breaker_config_refreshed", **self.config.to_dict())

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_backoff(value: Any) -> float | None:
        """Parse a backoff hash value into a timestamp, tolerating junk.

        Accepts ``bytes`` as well as ``str`` - Redis clients without
        ``decode_responses=True`` return byte strings.
        """
        if not isinstance(value, str | bytes | bytearray):
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _resolve_state(self, backoff_value: Any) -> CircuitState:
        """Derive the circuit state from the raw backoff hash value."""
        until = self._parse_backoff(backoff_value)
        if until is None:
            return CircuitState.CLOSED
        if until > time.time():
            return CircuitState.OPEN
        return CircuitState.HALF_OPEN

    async def get_state(self, agent_id: str) -> CircuitState:
        """Get the current circuit state for an agent."""
        r = await self.redis._ensure_connected()
        return self._resolve_state(await r.hget(AGENT_BACKOFF, agent_id))

    async def allow_activation(self, agent_id: str) -> bool:
        """Whether an activation may be enqueued for this agent.

        Activations for OPEN agents are skipped. An agent whose recovery
        window has elapsed (HALF_OPEN) admits one probe activation and has
        its expired backoff entry cleared; the probe's outcome at
        ``record_success``/``record_failure`` closes or re-opens the circuit.
        """
        await self._refresh_config_if_stale()
        r = await self.redis._ensure_connected()

        state = self._resolve_state(await r.hget(AGENT_BACKOFF, agent_id))
        if state is CircuitState.OPEN:
            return False

        if state is CircuitState.HALF_OPEN:
            # Recovery window elapsed - clear the stale entry and let a
            # probe activation through
            await r.hdel(AGENT_BACKOFF, agent_id)
            logger.info("circuit_half_open_probe_allowed", agent_id=agent_id)

        return True

    async def record_failure(self, agent_id: str) -> CircuitState:
        """Record a failed activation.

        Increments the consecutive failure count and opens the circuit when
        the threshold is reached (or immediately when the agent was
        half-open and its probe failed). The open duration escalates
        exponentially per extra failure, capped at ``backoff_max``.

        Returns:
            The resulting circuit state
        """
        await self._refresh_config_if_stale()
        r = await self.redis._ensure_connected()

        failures = int(await r.hincrby(AGENT_FAILURES, agent_id, 1))
        prev_state = self._resolve_state(await r.hget(AGENT_BACKOFF, agent_id))

        if prev_state is CircuitState.HALF_OPEN or failures >= self.config.failure_threshold:
            # Escalate: double the base backoff per failure beyond the
            # threshold, capped at backoff_max
            extra = min(failures - self.config.failure_threshold, 20)
            backoff_secs = min(
                self.config.backoff_base * (2 ** max(0, extra)),
                self.config.backoff_max,
            )
            await r.hset(AGENT_BACKOFF, agent_id, str(time.time() + backoff_secs))

            logger.warning(
                "agent_circuit_breaker",
                agent_id=agent_id,
                state=CircuitState.OPEN.value,
                previous_state=prev_state.value,
                failures=failures,
                failure_threshold=self.config.failure_threshold,
                backoff_seconds=backoff_secs,
                half_open_retry=prev_state is CircuitState.HALF_OPEN,
            )
            return CircuitState.OPEN

        return CircuitState.CLOSED

    async def record_success(self, agent_id: str) -> CircuitState:
        """Record a successful activation.

        Clears the failure count and any backoff, closing the circuit.

        Returns:
            The resulting circuit state (always CLOSED)
        """
        r = await self.redis._ensure_connected()
        await r.hdel(AGENT_FAILURES, agent_id)
        await r.hdel(AGENT_BACKOFF, agent_id)
        return CircuitState.CLOSED

    async def reset(self, agent_id: str) -> None:
        """Manually reset an agent's circuit to CLOSED (operator action)."""
        r = await self.redis._ensure_connected()
        await r.hdel(AGENT_FAILURES, agent_id)
        await r.hdel(AGENT_BACKOFF, agent_id)
        logger.info("circuit_breaker_reset", agent_id=agent_id)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    async def get_status(self, agent_id: str) -> dict[str, Any]:
        """Get detailed circuit status for a single agent."""
        r = await self.redis._ensure_connected()

        backoff_raw = await r.hget(AGENT_BACKOFF, agent_id)
        state = self._resolve_state(backoff_raw)
        until = self._parse_backoff(backoff_raw)

        failures_raw = await r.hget(AGENT_FAILURES, agent_id)
        try:
            failures = int(failures_raw) if failures_raw else 0
        except ValueError:
            failures = 0

        return {
            "agent_id": agent_id,
            "state": state.value,
            "failures": failures,
            "backoff_until": until,
            "backoff_seconds_remaining": max(0.0, until - time.time()) if until else 0.0,
            "thresholds": self.config.to_dict(),
        }

    async def get_all_states(self) -> dict[str, CircuitState]:
        """Get the resolved circuit state for every agent with backoff data.

        Agents without an entry are CLOSED and are not included.
        """
        r = await self.redis._ensure_connected()
        entries = await r.hgetall(AGENT_BACKOFF)
        return {agent_id: self._resolve_state(value) for agent_id, value in entries.items()}
