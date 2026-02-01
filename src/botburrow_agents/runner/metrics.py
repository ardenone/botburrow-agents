"""Metrics reporting for agent activations.

Reports consumption metrics to Hub for:
- Token usage
- Cost tracking
- Daily/monthly budget enforcement
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import ActivationResult

if TYPE_CHECKING:
    from botburrow_agents.clients.hub import HubClient

logger = structlog.get_logger(__name__)


# Approximate costs per 1M tokens (as of 2026)
MODEL_COSTS = {
    # Anthropic
    "claude-opus-4-5-20251101": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-3-20250515": {"input": 0.25, "output": 1.25},
    # OpenAI
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # Default for unknown models
    "default": {"input": 3.0, "output": 15.0},
}


@dataclass
class UsageMetrics:
    """Token usage and cost metrics."""

    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    model: str = ""
    duration_seconds: float = 0.0


class MetricsReporter:
    """Reports usage metrics to Hub."""

    def __init__(
        self,
        hub: HubClient,
        settings: Settings | None = None,
    ) -> None:
        self.hub = hub
        self.settings = settings or get_settings()
        self._pending_metrics: list[tuple[str, UsageMetrics]] = []

    def record_usage(
        self,
        agent_id: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        duration_seconds: float = 0.0,
    ) -> UsageMetrics:
        """Record usage for later reporting.

        Args:
            agent_id: Agent that used tokens
            model: Model used
            tokens_input: Input tokens
            tokens_output: Output tokens
            duration_seconds: Activation duration

        Returns:
            UsageMetrics with calculated cost
        """
        cost = self._calculate_cost(model, tokens_input, tokens_output)

        metrics = UsageMetrics(
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost,
            model=model,
            duration_seconds=duration_seconds,
        )

        self._pending_metrics.append((agent_id, metrics))

        logger.debug(
            "usage_recorded",
            agent_id=agent_id,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost,
        )

        return metrics

    async def flush(self) -> None:
        """Report all pending metrics to Hub."""
        if not self._pending_metrics:
            return

        # Aggregate by agent
        agent_totals: dict[str, UsageMetrics] = {}

        for agent_id, metrics in self._pending_metrics:
            if agent_id not in agent_totals:
                agent_totals[agent_id] = UsageMetrics()

            total = agent_totals[agent_id]
            total.tokens_input += metrics.tokens_input
            total.tokens_output += metrics.tokens_output
            total.cost_usd += metrics.cost_usd
            total.duration_seconds += metrics.duration_seconds

        # Report to Hub
        for agent_id, total in agent_totals.items():
            try:
                await self.hub.report_consumption(
                    agent_id=agent_id,
                    tokens_input=total.tokens_input,
                    tokens_output=total.tokens_output,
                    cost_usd=total.cost_usd,
                )
                logger.info(
                    "metrics_reported",
                    agent_id=agent_id,
                    tokens_total=total.tokens_input + total.tokens_output,
                    cost_usd=total.cost_usd,
                )
            except Exception as e:
                logger.error(
                    "metrics_report_failed",
                    agent_id=agent_id,
                    error=str(e),
                )

        self._pending_metrics.clear()

    def _calculate_cost(
        self,
        model: str,
        tokens_input: int,
        tokens_output: int,
    ) -> float:
        """Calculate cost in USD."""
        costs = MODEL_COSTS.get(model, MODEL_COSTS["default"])

        input_cost = (tokens_input / 1_000_000) * costs["input"]
        output_cost = (tokens_output / 1_000_000) * costs["output"]

        return round(input_cost + output_cost, 6)

    @staticmethod
    def from_activation_result(result: ActivationResult) -> UsageMetrics:
        """Extract metrics from activation result."""
        return UsageMetrics(
            tokens_input=0,  # Not tracked separately in current result
            tokens_output=0,
            cost_usd=0.0,
            duration_seconds=result.duration_seconds,
        )


class BudgetChecker:
    """Check budget health before/during activation."""

    def __init__(
        self,
        hub: HubClient,
        settings: Settings | None = None,
    ) -> None:
        self.hub = hub
        self.settings = settings or get_settings()

    async def check_budget(self, agent_id: str) -> tuple[bool, str]:
        """Check if agent has budget for activation.

        Returns:
            Tuple of (can_proceed, reason)
        """
        try:
            health = await self.hub.get_budget_health(agent_id)

            if not health.healthy:
                if health.daily_used >= health.daily_limit:
                    return False, "Daily budget exceeded"
                if health.monthly_used >= health.monthly_limit:
                    return False, "Monthly budget exceeded"
                return False, "Budget unhealthy"

            # Calculate remaining budget
            daily_remaining = health.daily_limit - health.daily_used
            monthly_remaining = health.monthly_limit - health.monthly_used

            logger.debug(
                "budget_checked",
                agent_id=agent_id,
                daily_remaining=daily_remaining,
                monthly_remaining=monthly_remaining,
            )

            return True, "Budget OK"

        except Exception as e:
            logger.warning(
                "budget_check_failed",
                agent_id=agent_id,
                error=str(e),
            )
            # If we can't check, allow with warning
            return True, "Budget check failed, proceeding anyway"

    async def estimate_activation_cost(
        self,
        model: str,
        estimated_tokens: int = 10000,
    ) -> float:
        """Estimate cost for an activation."""
        # Assume 70% input, 30% output
        tokens_input = int(estimated_tokens * 0.7)
        tokens_output = int(estimated_tokens * 0.3)

        costs = MODEL_COSTS.get(model, MODEL_COSTS["default"])
        input_cost = (tokens_input / 1_000_000) * costs["input"]
        output_cost = (tokens_output / 1_000_000) * costs["output"]

        return round(input_cost + output_cost, 4)
