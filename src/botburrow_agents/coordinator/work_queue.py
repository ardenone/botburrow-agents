"""Work queue for scalable work distribution.

Implements Redis-based work queue with:
- Priority queues (high, normal, low)
- Atomic work claiming via BRPOP
- Deduplication (one task per agent)
- Circuit breaker for failed agents
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import TaskType

if TYPE_CHECKING:
    from botburrow_agents.clients.redis import RedisClient

logger = structlog.get_logger(__name__)


# Queue keys
QUEUE_HIGH = "work:queue:high"
QUEUE_NORMAL = "work:queue:normal"
QUEUE_LOW = "work:queue:low"
ACTIVE_TASKS = "work:active"  # Hash: agent_id -> runner_id
AGENT_FAILURES = "work:failures"  # Hash: agent_id -> failure count
AGENT_BACKOFF = "work:backoff"  # Hash: agent_id -> backoff_until timestamp


@dataclass
class WorkItem:
    """Work item in the queue."""

    agent_id: str
    agent_name: str
    task_type: TaskType
    priority: str = "normal"  # high, normal, low
    inbox_count: int = 0
    created_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps({
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "task_type": self.task_type.value,
            "priority": self.priority,
            "inbox_count": self.inbox_count,
            "created_at": self.created_at,
        })

    @classmethod
    def from_json(cls, data: str) -> WorkItem:
        """Deserialize from JSON."""
        d = json.loads(data)
        return cls(
            agent_id=d["agent_id"],
            agent_name=d["agent_name"],
            task_type=TaskType(d["task_type"]),
            priority=d.get("priority", "normal"),
            inbox_count=d.get("inbox_count", 0),
            created_at=d.get("created_at", time.time()),
        )


class WorkQueue:
    """Redis-based work queue for distributing work to runners.

    Features:
    - Priority queues for different urgency levels
    - Atomic claiming with BRPOP
    - Deduplication via active tasks tracking
    - Circuit breaker for repeatedly failing agents
    """

    def __init__(
        self,
        redis: RedisClient,
        settings: Settings | None = None,
    ) -> None:
        self.redis = redis
        self.settings = settings or get_settings()

        # Circuit breaker settings
        self.max_failures = 5
        self.backoff_base = 60  # seconds
        self.backoff_max = 3600  # 1 hour max

    async def enqueue(
        self,
        work: WorkItem,
        force: bool = False,
    ) -> bool:
        """Add work item to queue.

        Args:
            work: Work item to enqueue
            force: Skip deduplication check

        Returns:
            True if enqueued, False if duplicate
        """
        r = await self.redis._ensure_connected()

        # Check for deduplication (unless forced)
        if not force:
            # Check if agent already has active task
            active = await r.hget(ACTIVE_TASKS, work.agent_id)
            if active:
                logger.debug("duplicate_work_skipped", agent_id=work.agent_id)
                return False

            # Check if agent is in backoff
            backoff_until = await r.hget(AGENT_BACKOFF, work.agent_id)
            if backoff_until:
                if float(backoff_until) > time.time():
                    logger.debug("agent_in_backoff", agent_id=work.agent_id)
                    return False
                # Backoff expired, clear it
                await r.hdel(AGENT_BACKOFF, work.agent_id)

        # Choose queue by priority
        queue_key = self._get_queue_key(work.priority)

        # Add to queue
        await r.lpush(queue_key, work.to_json())

        logger.debug(
            "work_enqueued",
            agent_id=work.agent_id,
            priority=work.priority,
            queue=queue_key,
        )
        return True

    async def claim(
        self,
        runner_id: str,
        timeout: int = 30,
    ) -> WorkItem | None:
        """Claim next work item from queue.

        Checks queues in priority order: high, normal, low.
        Uses BRPOP for blocking wait.

        Args:
            runner_id: ID of runner claiming work
            timeout: Seconds to wait for work

        Returns:
            WorkItem if claimed, None if timeout
        """
        r = await self.redis._ensure_connected()

        # Try queues in priority order
        result = await r.brpop(
            [QUEUE_HIGH, QUEUE_NORMAL, QUEUE_LOW],
            timeout=timeout,
        )

        if not result:
            return None

        queue_key, work_json = result
        work = WorkItem.from_json(work_json)

        # Mark as active
        await r.hset(ACTIVE_TASKS, work.agent_id, runner_id)

        logger.info(
            "work_claimed",
            agent_id=work.agent_id,
            runner_id=runner_id,
            queue=queue_key,
        )
        return work

    async def complete(
        self,
        work: WorkItem,
        success: bool,
    ) -> None:
        """Mark work as complete.

        Args:
            work: Completed work item
            success: Whether task succeeded
        """
        r = await self.redis._ensure_connected()

        # Remove from active tasks
        await r.hdel(ACTIVE_TASKS, work.agent_id)

        if success:
            # Clear failure count on success
            await r.hdel(AGENT_FAILURES, work.agent_id)
            await r.hdel(AGENT_BACKOFF, work.agent_id)
        else:
            # Increment failure count
            failures = await r.hincrby(AGENT_FAILURES, work.agent_id, 1)

            if failures >= self.max_failures:
                # Enter circuit breaker backoff
                backoff_secs = min(
                    self.backoff_base * (2 ** (failures - self.max_failures)),
                    self.backoff_max,
                )
                backoff_until = time.time() + backoff_secs
                await r.hset(AGENT_BACKOFF, work.agent_id, str(backoff_until))

                logger.warning(
                    "agent_circuit_breaker",
                    agent_id=work.agent_id,
                    failures=failures,
                    backoff_seconds=backoff_secs,
                )

        logger.debug(
            "work_completed",
            agent_id=work.agent_id,
            success=success,
        )

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        r = await self.redis._ensure_connected()

        high_len = await r.llen(QUEUE_HIGH)
        normal_len = await r.llen(QUEUE_NORMAL)
        low_len = await r.llen(QUEUE_LOW)
        active = await r.hlen(ACTIVE_TASKS)
        backoff = await r.hlen(AGENT_BACKOFF)

        return {
            "queue_high": high_len,
            "queue_normal": normal_len,
            "queue_low": low_len,
            "total_queued": high_len + normal_len + low_len,
            "active_tasks": active,
            "agents_in_backoff": backoff,
        }

    async def clear_backoff(self, agent_id: str) -> None:
        """Manually clear backoff for an agent."""
        r = await self.redis._ensure_connected()
        await r.hdel(AGENT_BACKOFF, agent_id)
        await r.hdel(AGENT_FAILURES, agent_id)
        logger.info("backoff_cleared", agent_id=agent_id)

    def _get_queue_key(self, priority: str) -> str:
        """Get queue key for priority."""
        if priority == "high":
            return QUEUE_HIGH
        elif priority == "low":
            return QUEUE_LOW
        else:
            return QUEUE_NORMAL


class ConfigCache:
    """Cache for agent configurations.

    Caches agent configs in Redis with TTL to avoid
    repeated Git fetches. Uses agent-specific cache_ttl
    from config if available.
    """

    CACHE_PREFIX = "cache:agent:"
    DEFAULT_TTL = 300  # 5 minutes

    def __init__(
        self,
        redis: RedisClient,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        self.redis = redis
        self.ttl = ttl

    async def get(self, agent_id: str) -> dict[str, Any] | None:
        """Get cached agent config."""
        r = await self.redis._ensure_connected()
        key = f"{self.CACHE_PREFIX}{agent_id}"
        data = await r.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(
        self,
        agent_id: str,
        config: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Cache agent config.

        Args:
            agent_id: Agent identifier
            config: Config dict to cache
            ttl: Custom TTL (uses agent's cache_ttl if not provided)
        """
        r = await self.redis._ensure_connected()
        key = f"{self.CACHE_PREFIX}{agent_id}"
        cache_ttl = ttl or config.get("cache_ttl", self.ttl)
        await r.set(key, json.dumps(config), ex=cache_ttl)

    async def invalidate(self, agent_id: str) -> None:
        """Invalidate cached config."""
        r = await self.redis._ensure_connected()
        key = f"{self.CACHE_PREFIX}{agent_id}"
        await r.delete(key)

    async def invalidate_all(self) -> None:
        """Invalidate all cached configs (for webhook endpoint)."""
        r = await self.redis._ensure_connected()
        # Find all keys with the cache prefix
        pattern = f"{self.CACHE_PREFIX}*"
        keys = []
        async for key in r.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await r.delete(*keys)
        logger.info("cache_invalidated_all", count=len(keys))

    async def prewarm(
        self,
        agent_ids: list[str],
        git_client: Any,
    ) -> int:
        """Pre-warm cache with agent configs.

        Args:
            agent_ids: Agent IDs to cache
            git_client: Git client for loading configs

        Returns:
            Number of configs cached
        """
        cached = 0
        for agent_id in agent_ids:
            try:
                # Check if already cached
                if await self.get(agent_id):
                    continue

                # Load from Git
                config = await git_client.load_agent_config(agent_id)
                # Use agent's cache_ttl for caching
                await self.set(agent_id, config.model_dump(), ttl=config.cache_ttl)
                cached += 1
            except Exception as e:
                logger.warning(
                    "prewarm_failed",
                    agent_id=agent_id,
                    error=str(e),
                )

        logger.info("cache_prewarmed", count=cached)
        return cached


class LeaderElection:
    """Simple leader election using Redis SETNX.

    Only one coordinator should be polling Hub at a time.
    """

    LEADER_KEY = "coordinator:leader"
    HEARTBEAT_TTL = 30  # seconds

    def __init__(
        self,
        redis: RedisClient,
        instance_id: str,
    ) -> None:
        self.redis = redis
        self.instance_id = instance_id
        self._is_leader = False

    async def try_become_leader(self) -> bool:
        """Try to become leader.

        Returns:
            True if this instance is now leader
        """
        r = await self.redis._ensure_connected()

        # Try to claim leadership
        acquired = await r.set(
            self.LEADER_KEY,
            self.instance_id,
            nx=True,
            ex=self.HEARTBEAT_TTL,
        )

        if acquired:
            self._is_leader = True
            logger.info("became_leader", instance_id=self.instance_id)
            return True

        # Check if we're already leader
        current = await r.get(self.LEADER_KEY)
        if current == self.instance_id:
            # Refresh our leadership
            await r.expire(self.LEADER_KEY, self.HEARTBEAT_TTL)
            self._is_leader = True
            return True

        self._is_leader = False
        return False

    async def release_leadership(self) -> None:
        """Release leadership."""
        if not self._is_leader:
            return

        r = await self.redis._ensure_connected()

        # Only delete if we're the leader
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        await r.eval(script, 1, self.LEADER_KEY, self.instance_id)
        self._is_leader = False
        logger.info("released_leadership", instance_id=self.instance_id)

    @property
    def is_leader(self) -> bool:
        """Check if this instance is leader."""
        return self._is_leader


def jitter(base: float, factor: float = 0.1) -> float:
    """Add random jitter to a value.

    Helps avoid thundering herd.
    """
    return base * (1 + random.uniform(-factor, factor))
