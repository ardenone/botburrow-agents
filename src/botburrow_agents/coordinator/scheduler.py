"""Scheduler for determining which agents need activation.

Implements staleness-based scheduling per ADR-011:
1. Priority: Agents with unread notifications (sorted by inbox count)
2. Fallback: Agents that haven't run recently (sorted by staleness)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from botburrow_agents.config import ActivationMode, Settings, get_settings
from botburrow_agents.models import Assignment

if TYPE_CHECKING:
    from botburrow_agents.clients.hub import HubClient
    from botburrow_agents.clients.redis import RedisClient

logger = structlog.get_logger(__name__)


class Scheduler:
    """Determines which agents should be activated next.

    Scheduling algorithm:
    1. For NOTIFICATION mode: Only agents with inbox items
    2. For EXPLORATION mode: Only stale agents
    3. For HYBRID mode: Inbox first, then stale agents
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

    async def get_next_assignment(
        self, mode: ActivationMode
    ) -> Assignment | None:
        """Get the next agent that should be activated.

        Args:
            mode: Activation mode (NOTIFICATION, EXPLORATION, or HYBRID)

        Returns:
            Assignment if there's work to do, None otherwise
        """
        if mode == ActivationMode.NOTIFICATION:
            return await self._get_notification_assignment()
        elif mode == ActivationMode.EXPLORATION:
            return await self._get_exploration_assignment()
        else:  # HYBRID
            # Try notifications first
            assignment = await self._get_notification_assignment()
            if assignment:
                return assignment
            # Fall back to exploration
            return await self._get_exploration_assignment()

    async def _get_notification_assignment(self) -> Assignment | None:
        """Get an agent with pending notifications."""
        agents = await self.hub.get_agents_with_notifications()

        for agent in agents:
            # Check if agent is already locked
            if await self._is_locked(agent.agent_id):
                continue

            logger.debug(
                "notification_candidate",
                agent_id=agent.agent_id,
                inbox_count=agent.inbox_count,
            )
            return agent

        return None

    async def _get_exploration_assignment(self) -> Assignment | None:
        """Get a stale agent for exploration."""
        agents = await self.hub.get_stale_agents(
            min_staleness_seconds=self.settings.min_activation_interval
        )

        for agent in agents:
            # Check if agent is already locked
            if await self._is_locked(agent.agent_id):
                continue

            # Check if agent has exceeded daily limits
            if await self._check_daily_limits(agent.agent_id):
                continue

            logger.debug(
                "exploration_candidate",
                agent_id=agent.agent_id,
                last_activated=agent.last_activated,
            )
            return agent

        return None

    async def _is_locked(self, agent_id: str) -> bool:
        """Check if an agent is currently locked by a runner."""
        lock_key = f"agent_lock:{agent_id}"
        return await self.redis.exists(lock_key)

    async def _check_daily_limits(self, agent_id: str) -> bool:
        """Check if agent has exceeded daily activity limits.

        Returns True if limits exceeded (should skip).
        """
        try:
            health = await self.hub.get_budget_health(agent_id)
            if not health.healthy:
                logger.warning("agent_budget_exceeded", agent_id=agent_id)
                return True
        except Exception as e:
            # If we can't check, allow activation
            logger.warning("budget_check_failed", agent_id=agent_id, error=str(e))

        return False

    async def get_queue_stats(self) -> dict[str, int]:
        """Get current queue statistics."""
        notification_agents = await self.hub.get_agents_with_notifications()
        stale_agents = await self.hub.get_stale_agents(
            min_staleness_seconds=self.settings.min_activation_interval
        )

        # Count locked agents
        locked_count = 0
        for agent in notification_agents + stale_agents:
            if await self._is_locked(agent.agent_id):
                locked_count += 1

        return {
            "notification_queue": len(notification_agents),
            "exploration_queue": len(stale_agents),
            "locked_agents": locked_count,
            "total_pending": len(notification_agents) + len(stale_agents) - locked_count,
        }


class PriorityQueue:
    """Priority queue for agent activation.

    Uses Redis sorted set for distributed priority queue.
    Score = priority (lower = higher priority)

    For notifications: score = -inbox_count (more notifications = higher priority)
    For exploration: score = timestamp (older = higher priority)
    """

    NOTIFICATION_QUEUE = "queue:notifications"
    EXPLORATION_QUEUE = "queue:exploration"

    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis

    async def add_notification(
        self, agent_id: str, inbox_count: int
    ) -> None:
        """Add agent to notification queue with priority based on inbox count."""
        r = await self.redis._ensure_connected()
        # Higher inbox count = higher priority (lower score)
        score = -inbox_count
        await r.zadd(self.NOTIFICATION_QUEUE, {agent_id: score})

    async def add_exploration(
        self, agent_id: str, last_activated: datetime | None
    ) -> None:
        """Add agent to exploration queue with priority based on staleness."""
        r = await self.redis._ensure_connected()
        # Older = higher priority (lower score)
        score: float = 0 if last_activated is None else last_activated.timestamp()
        await r.zadd(self.EXPLORATION_QUEUE, {agent_id: score})

    async def pop_notification(self) -> str | None:
        """Pop highest priority agent from notification queue."""
        r = await self.redis._ensure_connected()
        result = await r.zpopmin(self.NOTIFICATION_QUEUE)
        if result:
            return result[0][0]  # (member, score)
        return None

    async def pop_exploration(self) -> str | None:
        """Pop highest priority agent from exploration queue."""
        r = await self.redis._ensure_connected()
        result = await r.zpopmin(self.EXPLORATION_QUEUE)
        if result:
            return result[0][0]
        return None

    async def remove(self, agent_id: str) -> None:
        """Remove agent from all queues."""
        r = await self.redis._ensure_connected()
        await r.zrem(self.NOTIFICATION_QUEUE, agent_id)
        await r.zrem(self.EXPLORATION_QUEUE, agent_id)

    async def get_queue_lengths(self) -> tuple[int, int]:
        """Get lengths of both queues."""
        r = await self.redis._ensure_connected()
        notif_len = await r.zcard(self.NOTIFICATION_QUEUE)
        explore_len = await r.zcard(self.EXPLORATION_QUEUE)
        return notif_len, explore_len
