"""Prometheus metrics for botburrow-agents.

Provides observability for:
- Activation metrics (rate, duration, success/failure)
- Queue depth metrics
- Runner pool health
- Resource consumption
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import structlog
from aiohttp import web
from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

if TYPE_CHECKING:
    from botburrow_agents.coordinator.work_queue import WorkQueue

logger = structlog.get_logger(__name__)

# Activation metrics
ACTIVATIONS_TOTAL = Counter(
    "botburrow_activations_total",
    "Total agent activations",
    ["agent_id", "task_type", "status"],
)

ACTIVATION_DURATION = Histogram(
    "botburrow_activation_duration_seconds",
    "Activation duration in seconds",
    ["agent_id", "task_type"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
)

ACTIVATIONS_IN_PROGRESS = Gauge(
    "botburrow_activations_in_progress",
    "Number of activations currently in progress",
    ["runner_id"],
)

# Queue metrics
QUEUE_DEPTH = Gauge(
    "botburrow_queue_depth",
    "Number of items in work queue",
    ["priority"],
)

QUEUE_ACTIVE_TASKS = Gauge(
    "botburrow_queue_active_tasks",
    "Number of active (claimed) tasks",
)

QUEUE_AGENTS_IN_BACKOFF = Gauge(
    "botburrow_queue_agents_in_backoff",
    "Number of agents in circuit breaker backoff",
)

# Runner metrics
RUNNER_INFO = Info(
    "botburrow_runner",
    "Runner information",
)

RUNNERS_ACTIVE = Gauge(
    "botburrow_runners_active",
    "Number of active runners",
)

RUNNER_HEARTBEAT_TIMESTAMP = Gauge(
    "botburrow_runner_heartbeat_timestamp_seconds",
    "Last heartbeat timestamp",
    ["runner_id"],
)

# Coordinator metrics
COORDINATOR_IS_LEADER = Gauge(
    "botburrow_coordinator_is_leader",
    "Whether this coordinator instance is the leader",
    ["instance_id"],
)

POLL_DURATION = Histogram(
    "botburrow_poll_duration_seconds",
    "Duration of Hub polling in seconds",
    buckets=(0.1, 0.5, 1, 2, 5, 10),
)

# Token consumption
TOKENS_CONSUMED = Counter(
    "botburrow_tokens_consumed_total",
    "Total tokens consumed",
    ["agent_id", "model", "direction"],  # direction: input/output
)

# Cost tracking
ACTIVATION_COST = Counter(
    "botburrow_activation_cost_usd_total",
    "Total cost of activations in USD",
    ["agent_id", "model"],
)

# Budget health metrics
BUDGET_USED = Gauge(
    "botburrow_budget_used_usd",
    "Budget used in USD",
    ["agent_id", "period"],  # period: daily, monthly
)

BUDGET_LIMIT = Gauge(
    "botburrow_budget_limit_usd",
    "Budget limit in USD",
    ["agent_id", "period"],  # period: daily, monthly
)

BUDGET_HEALTH_RATIO = Gauge(
    "botburrow_budget_health_ratio",
    "Budget usage ratio (used/limit)",
    ["agent_id", "period"],  # period: daily, monthly
)

# Queue wait time metrics
QUEUE_WAIT_DURATION = Histogram(
    "botburrow_queue_wait_seconds",
    "Time work items spend waiting in queue before being claimed",
    ["agent_id", "priority"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
)

# Per-agent backoff state
AGENT_BACKOFF_SECONDS = Gauge(
    "botburrow_agent_backoff_seconds_remaining",
    "Seconds remaining in circuit breaker backoff",
    ["agent_id"],
)

# Activation retry counter
ACTIVATION_RETRIES = Counter(
    "botburrow_activation_retries_total",
    "Total number of activation retries",
    ["agent_id"],
)


def record_activation_start(runner_id: str) -> None:
    """Record activation starting."""
    ACTIVATIONS_IN_PROGRESS.labels(runner_id=runner_id).inc()


def record_activation_complete(
    agent_id: str,
    task_type: str,
    success: bool,
    duration_seconds: float,
    runner_id: str,
) -> None:
    """Record activation completion."""
    status = "success" if success else "failure"
    ACTIVATIONS_TOTAL.labels(
        agent_id=agent_id,
        task_type=task_type,
        status=status,
    ).inc()
    ACTIVATION_DURATION.labels(
        agent_id=agent_id,
        task_type=task_type,
    ).observe(duration_seconds)
    ACTIVATIONS_IN_PROGRESS.labels(runner_id=runner_id).dec()


def record_tokens(
    agent_id: str,
    model: str,
    tokens_input: int,
    tokens_output: int,
) -> None:
    """Record token consumption."""
    TOKENS_CONSUMED.labels(
        agent_id=agent_id,
        model=model,
        direction="input",
    ).inc(tokens_input)
    TOKENS_CONSUMED.labels(
        agent_id=agent_id,
        model=model,
        direction="output",
    ).inc(tokens_output)


def record_poll_duration(duration_seconds: float) -> None:
    """Record Hub poll duration."""
    POLL_DURATION.observe(duration_seconds)


def set_leader_status(instance_id: str, is_leader: bool) -> None:
    """Set leader status metric."""
    COORDINATOR_IS_LEADER.labels(instance_id=instance_id).set(1 if is_leader else 0)


def set_runner_info(runner_id: str, mode: str, version: str = "unknown") -> None:
    """Set runner info."""
    RUNNER_INFO.info(
        {
            "runner_id": runner_id,
            "mode": mode,
            "version": version,
        }
    )


def set_runner_heartbeat(runner_id: str) -> None:
    """Record runner heartbeat."""
    RUNNER_HEARTBEAT_TIMESTAMP.labels(runner_id=runner_id).set(time.time())


async def update_queue_metrics(work_queue: WorkQueue) -> None:
    """Update queue depth metrics from WorkQueue."""
    try:
        stats = await work_queue.get_queue_stats()
        QUEUE_DEPTH.labels(priority="high").set(stats["queue_high"])
        QUEUE_DEPTH.labels(priority="normal").set(stats["queue_normal"])
        QUEUE_DEPTH.labels(priority="low").set(stats["queue_low"])
        QUEUE_ACTIVE_TASKS.set(stats["active_tasks"])
        QUEUE_AGENTS_IN_BACKOFF.set(stats["agents_in_backoff"])
    except Exception as e:
        logger.warning("metrics_update_error", error=str(e))


def record_activation_cost(agent_id: str, model: str, cost_usd: float) -> None:
    """Record activation cost in USD."""
    ACTIVATION_COST.labels(agent_id=agent_id, model=model).inc(cost_usd)


def record_budget_health(
    agent_id: str,
    daily_used: float,
    daily_limit: float,
    monthly_used: float,
    monthly_limit: float,
) -> None:
    """Record budget health metrics."""
    BUDGET_USED.labels(agent_id=agent_id, period="daily").set(daily_used)
    BUDGET_LIMIT.labels(agent_id=agent_id, period="daily").set(daily_limit)
    BUDGET_HEALTH_RATIO.labels(agent_id=agent_id, period="daily").set(
        daily_used / daily_limit if daily_limit > 0 else 0
    )
    BUDGET_USED.labels(agent_id=agent_id, period="monthly").set(monthly_used)
    BUDGET_LIMIT.labels(agent_id=agent_id, period="monthly").set(monthly_limit)
    BUDGET_HEALTH_RATIO.labels(agent_id=agent_id, period="monthly").set(
        monthly_used / monthly_limit if monthly_limit > 0 else 0
    )


def record_queue_wait_time(agent_id: str, priority: str, wait_seconds: float) -> None:
    """Record queue wait time for a work item."""
    QUEUE_WAIT_DURATION.labels(agent_id=agent_id, priority=priority).observe(wait_seconds)


def record_agent_backoff(agent_id: str, backoff_seconds_remaining: float) -> None:
    """Record per-agent backoff state."""
    AGENT_BACKOFF_SECONDS.labels(agent_id=agent_id).set(backoff_seconds_remaining)


def clear_agent_backoff(agent_id: str) -> None:
    """Clear per-agent backoff metric."""
    AGENT_BACKOFF_SECONDS.labels(agent_id=agent_id).set(0)


def record_activation_retry(agent_id: str) -> None:
    """Record an activation retry."""
    ACTIVATION_RETRIES.labels(agent_id=agent_id).inc()


class MetricsServer:
    """HTTP server for Prometheus metrics endpoint."""

    def __init__(
        self,
        port: int = 9090,
        host: str = "0.0.0.0",
        config_cache: Any | None = None,
    ) -> None:
        self.port = port
        self.host = host
        self.config_cache = config_cache
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        """Start the metrics server."""
        self._app = web.Application()
        self._app.router.add_get("/metrics", self._metrics_handler)
        self._app.router.add_get("/health", self._health_handler)
        self._app.router.add_get("/ready", self._ready_handler)
        # Cache invalidation webhook endpoint (per ADR-028)
        self._app.router.add_post("/api/v1/cache/invalidate", self._invalidate_cache_handler)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(
            "metrics_server_started",
            host=self.host,
            port=self.port,
        )

    async def stop(self) -> None:
        """Stop the metrics server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("metrics_server_stopped")

    async def _metrics_handler(self, _request: web.Request) -> web.Response:
        """Handle /metrics endpoint."""
        metrics_output = generate_latest(REGISTRY)
        # Use content_type without charset (aiohttp 3.9+ requires this)
        return web.Response(
            body=metrics_output,
            content_type="text/plain",
            charset="utf-8",
        )

    async def _health_handler(self, _request: web.Request) -> web.Response:
        """Handle /health endpoint (liveness probe)."""
        return web.json_response({"status": "healthy"})

    async def _ready_handler(self, _request: web.Request) -> web.Response:
        """Handle /ready endpoint (readiness probe)."""
        # Could add more sophisticated checks here
        return web.json_response({"status": "ready"})

    async def _invalidate_cache_handler(self, request: web.Request) -> web.Response:
        """Handle cache invalidation webhook endpoint.

        Called by agent-definitions CI/CD pipeline when configs are updated.
        Supports:
        - Invalidate all: POST /api/v1/cache/invalidate
        - Invalidate specific agent: POST /api/v1/cache/invalidate?agent=agent-name

        Per ADR-028, this allows immediate cache invalidation when configs
        are updated in git without waiting for TTL expiration.
        """
        try:
            # Get optional agent parameter
            agent = request.query.get("agent")

            if self.config_cache:
                if agent:
                    await self.config_cache.invalidate(agent)
                    logger.info("cache_invalidated", agent=agent)
                else:
                    await self.config_cache.invalidate_all()
                    logger.info("cache_invalidated_all")
            else:
                logger.warning("cache_invalidate_requested_but_no_cache")

            return web.json_response({"status": "ok", "invalidated": agent or "all"})

        except Exception as e:
            logger.error("cache_invalidate_error", error=str(e))
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
            )


async def run_metrics_collector(
    work_queue: WorkQueue | None,
    interval: int = 15,
) -> None:
    """Background task to periodically collect metrics."""
    while True:
        try:
            if work_queue:
                await update_queue_metrics(work_queue)
        except Exception as e:
            logger.warning("metrics_collector_error", error=str(e))

        await asyncio.sleep(interval)
