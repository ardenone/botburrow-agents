"""Coordinator service main module.

The coordinator:
1. Polls Hub for agents with work to do
2. Manages work queue in Redis
3. Tracks runner health and assignment status
4. Implements leader election for HA

Scalability features:
- Leader election (only one coordinator polls Hub)
- Priority work queues (high, normal, low)
- Config caching in Redis
- Circuit breaker for failing agents
- Jittered polling to avoid thundering herd
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import uuid

import click
import structlog

from botburrow_agents.clients.git import GitClient
from botburrow_agents.clients.hub import HubClient
from botburrow_agents.clients.r2 import R2Client
from botburrow_agents.clients.redis import RedisClient
from botburrow_agents.config import ActivationMode, Settings, get_settings
from botburrow_agents.coordinator.assigner import Assigner
from botburrow_agents.coordinator.scheduler import Scheduler
from botburrow_agents.coordinator.work_queue import (
    ConfigCache,
    LeaderElection,
    WorkItem,
    WorkQueue,
    jitter,
)
from botburrow_agents.models import Assignment
from botburrow_agents.observability import (
    MetricsServer,
    record_poll_duration,
    run_metrics_collector,
    set_leader_status,
)

logger = structlog.get_logger(__name__)


class Coordinator:
    """Main coordinator service.

    Responsibilities:
    - Poll Hub for agents needing activation
    - Manage work queue in Redis
    - Track runner health via heartbeats
    - Provide stats/metrics endpoint

    Scalability:
    - Uses leader election - only leader polls Hub
    - Non-leaders still process health checks and stats
    - Work queue distributes work to runners
    - Config cache reduces R2 fetches
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.hub = HubClient(self.settings)
        self.redis = RedisClient(self.settings)
        self.git = GitClient(self.settings)  # For loading configs from Git
        self.r2 = R2Client(self.settings)  # For binary assets only (avatars, images)
        self.scheduler = Scheduler(self.hub, self.redis, self.settings)
        self.assigner = Assigner(self.hub, self.redis, self.settings)

        # Scalability components
        self.instance_id = os.environ.get("HOSTNAME", str(uuid.uuid4())[:8])
        self.work_queue: WorkQueue | None = None
        self.config_cache: ConfigCache | None = None
        self.leader_election: LeaderElection | None = None

        # Observability (created after config cache is initialized)
        self.metrics_server: MetricsServer | None = None

        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the coordinator service."""
        logger.info(
            "coordinator_starting",
            poll_interval=self.settings.poll_interval,
            instance_id=self.instance_id,
        )

        # Connect to Redis
        await self.redis.connect()

        # Initialize scalability components
        self.work_queue = WorkQueue(self.redis, self.settings)
        self.config_cache = ConfigCache(self.redis)
        self.leader_election = LeaderElection(self.redis, self.instance_id)

        # Create metrics server with config cache for webhook endpoint
        self.metrics_server = MetricsServer(port=9090, config_cache=self.config_cache)

        # Start metrics server
        await self.metrics_server.start()

        # Pre-warm config cache (only on leader, checked in prewarm)
        await self._prewarm_config_cache()

        self._running = True

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)

        # Start background tasks
        tasks = [
            asyncio.create_task(self._leader_loop()),
            asyncio.create_task(self._poll_loop()),
            asyncio.create_task(self._health_check_loop()),
            asyncio.create_task(self._stats_loop()),
            asyncio.create_task(run_metrics_collector(self.work_queue)),
        ]

        logger.info("coordinator_started", instance_id=self.instance_id)

        # Wait for shutdown
        await self._shutdown_event.wait()

        # Release leadership before stopping
        if self.leader_election:
            await self.leader_election.release_leadership()

        # Cancel tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # Cleanup
        await self.metrics_server.stop()
        await self.hub.close()
        await self.redis.close()

        logger.info("coordinator_stopped")

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("coordinator_shutdown_requested", instance_id=self.instance_id)
        self._running = False
        self._shutdown_event.set()

    async def _leader_loop(self) -> None:
        """Leader election loop - try to become/stay leader."""
        while self._running:
            try:
                if self.leader_election:
                    was_leader = self.leader_election.is_leader
                    is_leader = await self.leader_election.try_become_leader()

                    # Update Prometheus metric
                    set_leader_status(self.instance_id, is_leader)

                    if is_leader and not was_leader:
                        logger.info("became_leader", instance_id=self.instance_id)
            except Exception as e:
                logger.error("leader_election_error", error=str(e))

            # Check leadership every 10 seconds
            await asyncio.sleep(10)

    async def _poll_loop(self) -> None:
        """Main polling loop - only leader polls Hub.

        Uses long-polling when available for efficient work detection.
        Falls back to regular polling if long-poll endpoint not available.
        """
        use_long_poll = True  # Try long-poll first

        while self._running:
            try:
                # Only poll if we're the leader
                if self.leader_election and self.leader_election.is_leader:
                    if use_long_poll:
                        # Try long-poll (blocks up to 30s if no work)
                        try:
                            await self._poll_long()
                        except Exception as e:
                            # If long-poll fails, fall back to regular polling
                            if "404" in str(e) or "not available" in str(e).lower():
                                logger.info("long_poll_not_available_falling_back")
                                use_long_poll = False
                            else:
                                raise
                    else:
                        await self._poll_once()
                else:
                    logger.debug("not_leader_skipping_poll", instance_id=self.instance_id)
            except Exception as e:
                logger.error("poll_error", error=str(e))

            # Jittered sleep to avoid thundering herd (shorter for long-poll)
            sleep_time = 5 if use_long_poll else self.settings.poll_interval
            await asyncio.sleep(jitter(sleep_time))

    async def _poll_long(self) -> None:
        """Long-poll for work - more efficient than regular polling.

        Uses Hub's long-poll endpoint that blocks until work is available
        or timeout occurs. This reduces load on Hub API.
        """
        import time

        start_time = time.time()

        # Long-poll for notifications (blocks up to 30s)
        notification_agents = await self.hub.poll_notifications(
            timeout=30,
            batch_size=100,
        )

        # Record poll duration metric
        record_poll_duration(time.time() - start_time)

        if notification_agents:
            logger.debug(
                "long_poll_notifications",
                count=len(notification_agents),
            )

            # Queue notification work with high priority
            for agent in notification_agents:
                await self._enqueue_work(agent, priority="high")

        # Also check for stale agents (but less frequently)
        # Only check staleness every few poll cycles to reduce load
        if time.time() % 60 < 5:  # Roughly every minute
            stale_agents = await self.hub.get_stale_agents(
                min_staleness_seconds=self.settings.min_activation_interval
            )
            if stale_agents:
                logger.debug("poll_stale", count=len(stale_agents))
                for agent in stale_agents:
                    await self._enqueue_work(agent, priority="normal")

    async def _poll_once(self) -> None:
        """Single poll iteration - fetch and enqueue work."""
        import time

        start_time = time.time()

        # Check for agents with notifications (batch fetch)
        notification_agents = await self.hub.get_agents_with_notifications()
        logger.debug(
            "poll_notifications",
            count=len(notification_agents),
        )

        # Queue notification work with high priority
        for agent in notification_agents:
            await self._enqueue_work(agent, priority="high")

        # Check for stale agents (for exploration) - batch fetch
        stale_agents = await self.hub.get_stale_agents(
            min_staleness_seconds=self.settings.min_activation_interval
        )
        logger.debug(
            "poll_stale",
            count=len(stale_agents),
        )

        # Record poll duration metric
        record_poll_duration(time.time() - start_time)

        # Queue exploration work with normal priority
        for agent in stale_agents:
            await self._enqueue_work(agent, priority="normal")

    async def _enqueue_work(self, assignment: Assignment, priority: str = "normal") -> None:
        """Add work to the queue using WorkQueue.

        Args:
            assignment: The assignment to enqueue
            priority: Priority level (high, normal, low)
        """
        if not self.work_queue:
            logger.warning("work_queue_not_initialized")
            return

        work_item = WorkItem(
            agent_id=assignment.agent_id,
            agent_name=assignment.agent_name,
            task_type=assignment.task_type,
            priority=priority,
            inbox_count=assignment.inbox_count or 0,
        )

        await self.work_queue.enqueue(work_item)

    async def _health_check_loop(self) -> None:
        """Monitor runner health."""
        while self._running:
            try:
                runners = await self.assigner.get_active_runners()
                locked = await self.assigner.get_locked_agents()

                # Check for stale locks (runner died without releasing)
                for lock in locked:
                    # If owner runner is not active, release the lock
                    runner_active = any(r["runner_id"] == lock["owner"] for r in runners)
                    if not runner_active and lock["ttl_seconds"] < 60:
                        logger.warning(
                            "stale_lock_detected",
                            agent_id=lock["agent_id"],
                            owner=lock["owner"],
                        )
                        # Let the lock expire naturally

            except Exception as e:
                logger.error("health_check_error", error=str(e))

            await asyncio.sleep(30)  # Check every 30 seconds

    async def _stats_loop(self) -> None:
        """Log periodic stats including work queue metrics."""
        while self._running:
            try:
                scheduler_stats = await self.scheduler.get_queue_stats()
                runners = await self.assigner.get_active_runners()

                # Get work queue stats if available
                queue_stats = {}
                if self.work_queue:
                    queue_stats = await self.work_queue.get_queue_stats()

                logger.info(
                    "coordinator_stats",
                    instance_id=self.instance_id,
                    is_leader=self.leader_election.is_leader if self.leader_election else False,
                    notification_queue=scheduler_stats["notification_queue"],
                    exploration_queue=scheduler_stats["exploration_queue"],
                    locked_agents=scheduler_stats["locked_agents"],
                    active_runners=len(runners),
                    work_queue_high=queue_stats.get("queue_high", 0),
                    work_queue_normal=queue_stats.get("queue_normal", 0),
                    work_queue_low=queue_stats.get("queue_low", 0),
                    active_tasks=queue_stats.get("active_tasks", 0),
                    agents_in_backoff=queue_stats.get("agents_in_backoff", 0),
                )
            except Exception as e:
                logger.error("stats_error", error=str(e))

            await asyncio.sleep(60)  # Log stats every minute

    async def get_assignment(self, runner_id: str, mode: ActivationMode) -> Assignment | None:
        """Get an assignment for a runner (called by runners via API or queue).

        Args:
            runner_id: ID of the requesting runner
            mode: Runner's activation mode

        Returns:
            Assignment if work is available
        """
        # Record runner heartbeat
        await self.assigner.heartbeat(runner_id, "requesting")

        # Get next assignment from scheduler
        assignment = await self.scheduler.get_next_assignment(mode)
        if not assignment:
            return None

        # Try to claim it
        if await self.assigner.try_claim(assignment, runner_id):
            return assignment

        # If claim failed, try next
        return await self.get_assignment(runner_id, mode)

    async def _prewarm_config_cache(self) -> None:
        """Pre-warm config cache with agent configurations.

        Fetches list of agents from Git and caches their configs.
        Only runs if we're the leader to avoid duplicate fetches.
        """
        if not self.config_cache:
            return

        try:
            # Check if we're the leader (or if leader election not yet run)
            if self.leader_election and not self.leader_election.is_leader:
                # Try to become leader first
                is_leader = await self.leader_election.try_become_leader()
                if not is_leader:
                    logger.debug("not_leader_skip_prewarm")
                    return

            # Get list of agents from Git
            agent_ids = await self.git.list_agents()
            if not agent_ids:
                logger.debug("no_agents_to_prewarm")
                return

            # Pre-warm cache
            cached = await self.config_cache.prewarm(agent_ids, self.git)
            logger.info(
                "config_cache_prewarmed",
                total_agents=len(agent_ids),
                cached=cached,
            )

        except Exception as e:
            # Don't fail startup if prewarm fails
            logger.warning("prewarm_error", error=str(e))


def setup_logging() -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if not get_settings().hub_url.startswith("http://localhost")
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@click.command()
@click.option(
    "--poll-interval",
    default=30,
    help="Seconds between polls",
)
def main(poll_interval: int) -> None:
    """Run the coordinator service."""
    setup_logging()

    settings = get_settings()
    settings.poll_interval = poll_interval

    coordinator = Coordinator(settings)

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(coordinator.start())


if __name__ == "__main__":
    main()
