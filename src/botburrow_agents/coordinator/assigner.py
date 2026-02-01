"""Assigner for distributing work to runners.

Handles:
- Claiming agents with distributed locks
- Releasing agents after completion
- Tracking runner status
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import ActivationResult, Assignment

if TYPE_CHECKING:
    from botburrow_agents.clients.hub import HubClient
    from botburrow_agents.clients.redis import RedisClient

logger = structlog.get_logger(__name__)


class Assigner:
    """Manages work assignment to runners.

    Uses Redis for:
    - Distributed locking (agent:lock:{agent_id})
    - Runner heartbeats (runner:heartbeat:{runner_id})
    - Activation tracking (agent:activation:{agent_id})
    """

    def __init__(
        self,
        hub: HubClient,
        redis: RedisClient,
        settings: Settings | None = None,
    ) -> None:
        self.hub = hub
        self.redis = redis
        self.settings = settings or get_settings()

    async def try_claim(
        self, assignment: Assignment, runner_id: str
    ) -> bool:
        """Try to claim an agent for a runner.

        Args:
            assignment: The assignment to claim
            runner_id: ID of the runner claiming the agent

        Returns:
            True if claim succeeded, False if already claimed
        """
        lock_key = f"agent_lock:{assignment.agent_id}"

        # Try to acquire lock atomically
        acquired = await self.redis.set(
            lock_key,
            runner_id,
            ex=self.settings.lock_ttl,
            nx=True,
        )

        if acquired:
            # Track assignment metadata
            await self._track_assignment(assignment, runner_id)
            logger.info(
                "agent_claimed",
                agent_id=assignment.agent_id,
                runner_id=runner_id,
                task_type=assignment.task_type.value,
            )
            return True
        else:
            logger.debug(
                "agent_already_claimed",
                agent_id=assignment.agent_id,
                runner_id=runner_id,
            )
            return False

    async def release(
        self,
        agent_id: str,
        runner_id: str,
        result: ActivationResult | None = None,
    ) -> bool:
        """Release an agent after processing.

        Args:
            agent_id: Agent to release
            runner_id: Runner that held the lock
            result: Optional activation result

        Returns:
            True if released successfully
        """
        lock_key = f"agent_lock:{agent_id}"

        # Only release if we own the lock
        current_owner = await self.redis.get(lock_key)
        if current_owner != runner_id:
            logger.warning(
                "lock_not_owned",
                agent_id=agent_id,
                runner_id=runner_id,
                current_owner=current_owner,
            )
            return False

        # Delete lock
        await self.redis.delete(lock_key)

        # Update activation timestamp in Hub
        try:
            await self.hub.update_agent_activation(agent_id)
        except Exception as e:
            logger.error("failed_to_update_activation", agent_id=agent_id, error=str(e))

        # Record result if provided
        if result:
            await self._record_result(result)

        # Clean up tracking
        await self._cleanup_assignment(agent_id)

        logger.info(
            "agent_released",
            agent_id=agent_id,
            runner_id=runner_id,
            success=result.success if result else None,
        )
        return True

    async def extend_lock(
        self, agent_id: str, runner_id: str, additional_ttl: int | None = None
    ) -> bool:
        """Extend lock TTL for long-running activations.

        Args:
            agent_id: Agent with active lock
            runner_id: Runner that holds the lock
            additional_ttl: Additional seconds (defaults to lock_ttl)

        Returns:
            True if extended successfully
        """
        lock_key = f"agent_lock:{agent_id}"
        ttl = additional_ttl or self.settings.lock_ttl

        # Check ownership and extend atomically
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('expire', KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        r = await self.redis._ensure_connected()
        result = await r.eval(script, 1, lock_key, runner_id, ttl)
        return result == 1

    async def heartbeat(self, runner_id: str, status: str = "active") -> None:
        """Record runner heartbeat.

        Args:
            runner_id: Runner ID
            status: Runner status (active, busy, idle)
        """
        key = f"runner:heartbeat:{runner_id}"
        value = json.dumps({
            "runner_id": runner_id,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        # Heartbeats expire after 2x poll interval
        await self.redis.set(key, value, ex=self.settings.poll_interval * 2)

    async def get_active_runners(self) -> list[dict]:
        """Get list of active runners based on heartbeats."""
        r = await self.redis._ensure_connected()

        # Scan for heartbeat keys
        runners = []
        cursor = 0
        while True:
            cursor, keys = await r.scan(
                cursor, match="runner:heartbeat:*", count=100
            )
            for key in keys:
                value = await r.get(key)
                if value:
                    runners.append(json.loads(value))
            if cursor == 0:
                break

        return runners

    async def get_locked_agents(self) -> list[dict]:
        """Get list of currently locked agents."""
        r = await self.redis._ensure_connected()

        locked = []
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="agent_lock:*", count=100)
            for key in keys:
                agent_id = key.split(":", 1)[1]
                owner = await r.get(key)
                ttl = await r.ttl(key)
                locked.append({
                    "agent_id": agent_id,
                    "owner": owner,
                    "ttl_seconds": ttl,
                })
            if cursor == 0:
                break

        return locked

    async def _track_assignment(
        self, assignment: Assignment, runner_id: str
    ) -> None:
        """Track assignment metadata."""
        key = f"agent:activation:{assignment.agent_id}"
        value = json.dumps({
            "agent_id": assignment.agent_id,
            "agent_name": assignment.agent_name,
            "runner_id": runner_id,
            "task_type": assignment.task_type.value,
            "started_at": datetime.now(UTC).isoformat(),
        })
        await self.redis.set(key, value, ex=self.settings.activation_timeout)

    async def _cleanup_assignment(self, agent_id: str) -> None:
        """Clean up assignment tracking."""
        key = f"agent:activation:{agent_id}"
        await self.redis.delete(key)

    async def _record_result(self, result: ActivationResult) -> None:
        """Record activation result for metrics."""
        # Store in a list for recent history
        key = "activation:results"
        value = json.dumps({
            "agent_id": result.agent_id,
            "agent_name": result.agent_name,
            "success": result.success,
            "posts_created": result.posts_created,
            "comments_created": result.comments_created,
            "notifications_processed": result.notifications_processed,
            "tokens_used": result.tokens_used,
            "duration_seconds": result.duration_seconds,
            "error": result.error,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        r = await self.redis._ensure_connected()
        await r.lpush(key, value)
        # Keep only last 1000 results
        await r.ltrim(key, 0, 999)

    async def get_recent_results(self, limit: int = 100) -> list[dict]:
        """Get recent activation results."""
        r = await self.redis._ensure_connected()
        results = await r.lrange("activation:results", 0, limit - 1)
        return [json.loads(r) for r in results]
