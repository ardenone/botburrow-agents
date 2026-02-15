"""Simplified metrics and budget tracking verification tests.

This module provides minimal viable verification for:
1. Prometheus metrics are exported correctly
2. Consumption tracking (tokens, cost, execution time) works
3. Budget health reporting functions properly
4. Circuit breaker triggers for over-budget agents
5. Runner pool utilization metrics are available

Per bd-ghh (simplified-scope alternative to bd-23c).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from botburrow_agents.observability import (
    ACTIVATION_COST,
    ACTIVATION_DURATION,
    ACTIVATIONS_IN_PROGRESS,
    ACTIVATIONS_TOTAL,
    BUDGET_HEALTH_RATIO,
    BUDGET_LIMIT,
    BUDGET_USED,
    QUEUE_DEPTH,
    TOKENS_CONSUMED,
    record_activation_complete,
    record_activation_cost,
    record_activation_start,
    record_budget_health,
    record_tokens,
    update_queue_metrics,
)
from botburrow_agents.runner.metrics import MODEL_COSTS, BudgetChecker, MetricsReporter


class TestSimplifiedPrometheusMetrics:
    """Verify Prometheus metrics are exported (Requirement 1)."""

    def test_activations_total_counter_exists(self) -> None:
        """Verify activation counter is exported."""
        assert ACTIVATIONS_TOTAL is not None
        assert ACTIVATIONS_TOTAL._name == "botburrow_activations"

    def test_activation_duration_histogram_exists(self) -> None:
        """Verify duration histogram with percentile support exists."""
        assert ACTIVATION_DURATION is not None
        assert ACTIVATION_DURATION._name == "botburrow_activation_duration_seconds"
        # Histograms support P50, P95, P99 queries in Prometheus
        # Check histogram has label names defined
        assert ACTIVATION_DURATION._labelnames == ("agent_id", "task_type")

    def test_tokens_consumed_counter_exists(self) -> None:
        """Verify token consumption counter exists."""
        assert TOKENS_CONSUMED is not None
        assert TOKENS_CONSUMED._name == "botburrow_tokens_consumed"

    def test_activation_cost_counter_exists(self) -> None:
        """Verify cost tracking counter exists."""
        assert ACTIVATION_COST is not None
        assert ACTIVATION_COST._name == "botburrow_activation_cost_usd"

    def test_budget_gauges_exist(self) -> None:
        """Verify budget health gauges exist."""
        assert BUDGET_USED is not None
        assert BUDGET_LIMIT is not None
        assert BUDGET_HEALTH_RATIO is not None

    def test_queue_metrics_exist(self) -> None:
        """Verify queue depth metrics exist."""
        assert QUEUE_DEPTH is not None
        assert QUEUE_DEPTH._name == "botburrow_queue_depth"


class TestConsumptionTracking:
    """Verify consumption tracking (Requirement 2)."""

    def test_token_tracking_records_input_output(self) -> None:
        """Verify tokens_input and tokens_output are tracked separately."""
        record_tokens(
            agent_id="test-agent",
            model="claude-sonnet-4",
            tokens_input=1000,
            tokens_output=500,
        )

        input_value = TOKENS_CONSUMED.labels(
            agent_id="test-agent",
            model="claude-sonnet-4",
            direction="input",
        )._value.get()
        output_value = TOKENS_CONSUMED.labels(
            agent_id="test-agent",
            model="claude-sonnet-4",
            direction="output",
        )._value.get()

        assert input_value >= 1000
        assert output_value >= 500

    def test_execution_time_tracking(self) -> None:
        """Verify execution time is tracked via duration histogram."""
        record_activation_start("runner-1")
        record_activation_complete(
            agent_id="test-agent",
            task_type="inbox",
            success=True,
            duration_seconds=45.2,
            runner_id="runner-1",
        )

        # Histogram should have observed the duration
        assert ACTIVATION_DURATION.labels(
            agent_id="test-agent",
            task_type="inbox",
        )._sum.get() >= 45.0

    def test_cost_tracking_calculates_usd(self) -> None:
        """Verify cost is calculated and tracked in USD."""
        record_activation_cost(agent_id="test-agent", model="claude-sonnet-4", cost_usd=0.123)

        cost_value = ACTIVATION_COST.labels(
            agent_id="test-agent",
            model="claude-sonnet-4",
        )._value.get()

        assert cost_value >= 0.123


class TestBudgetHealthReporting:
    """Verify budget health reporting to Hub API (Requirement 3)."""

    async def test_budget_checker_queries_hub(self) -> None:
        """Verify BudgetChecker queries Hub API for budget health."""
        mock_hub = AsyncMock()
        mock_health = MagicMock()
        mock_health.healthy = True
        mock_health.daily_used = 5.0
        mock_health.daily_limit = 10.0
        mock_health.monthly_used = 50.0
        mock_health.monthly_limit = 100.0
        mock_hub.get_budget_health.return_value = mock_health

        checker = BudgetChecker(mock_hub)
        can_proceed, reason = await checker.check_budget("test-agent")

        assert can_proceed is True
        assert "Budget OK" in reason
        mock_hub.get_budget_health.assert_called_once_with("test-agent")

    async def test_budget_exceeded_blocks_activation(self) -> None:
        """Verify exceeding budget blocks activation."""
        mock_hub = AsyncMock()
        mock_health = MagicMock()
        mock_health.healthy = False
        mock_health.daily_used = 15.0
        mock_health.daily_limit = 10.0
        mock_health.monthly_used = 50.0
        mock_health.monthly_limit = 100.0
        mock_hub.get_budget_health.return_value = mock_health

        checker = BudgetChecker(mock_hub)
        can_proceed, reason = await checker.check_budget("test-agent")

        assert can_proceed is False
        assert "Daily budget exceeded" in reason


class TestMetricsReporterToHub:
    """Verify metrics are reported to Hub API."""

    async def test_consumption_metrics_flushed_to_hub(self) -> None:
        """Verify consumption metrics are flushed to Hub."""
        mock_hub = AsyncMock()
        mock_hub.report_consumption.return_value = None

        reporter = MetricsReporter(mock_hub)
        reporter.record_usage(
            agent_id="test-agent",
            model="claude-sonnet-4",
            tokens_input=1000,
            tokens_output=500,
            duration_seconds=30.0,
        )

        await reporter.flush()

        mock_hub.report_consumption.assert_called_once()
        call_args = mock_hub.report_consumption.call_args
        assert call_args.kwargs["agent_id"] == "test-agent"
        assert call_args.kwargs["tokens_input"] == 1000
        assert call_args.kwargs["tokens_output"] == 500
        assert call_args.kwargs["cost_usd"] > 0


class TestCircuitBreakerIntegration:
    """Verify circuit breaker for over-budget agents (Requirement 4)."""

    async def test_queue_metrics_track_backoff(self) -> None:
        """Verify queue metrics track agents in backoff (circuit breaker state)."""
        mock_queue = AsyncMock()
        mock_queue.get_queue_stats.return_value = {
            "queue_high": 0,
            "queue_normal": 0,
            "queue_low": 0,
            "active_tasks": 0,
            "agents_in_backoff": 3,  # 3 agents in circuit breaker backoff
        }

        await update_queue_metrics(mock_queue)

        # Check that agents_in_backoff metric is updated
        from botburrow_agents.observability import QUEUE_AGENTS_IN_BACKOFF

        assert QUEUE_AGENTS_IN_BACKOFF._value.get() == 3


class TestRunnerPoolUtilization:
    """Verify runner pool utilization metrics (Requirement 5)."""

    def test_activations_in_progress_gauge(self) -> None:
        """Verify runners track activations in progress."""
        # Reset gauge to ensure clean state (tests may share gauge state)
        ACTIVATIONS_IN_PROGRESS.labels(runner_id="runner-1").set(0)

        record_activation_start("runner-1")

        value = ACTIVATIONS_IN_PROGRESS.labels(runner_id="runner-1")._value.get()
        assert value >= 1

    def test_queue_depth_by_priority(self) -> None:
        """Verify queue depth is tracked by priority level."""
        async def mock_stats():
            return {
                "queue_high": 5,
                "queue_normal": 10,
                "queue_low": 2,
                "active_tasks": 3,
                "agents_in_backoff": 0,
            }

        mock_queue = AsyncMock()
        mock_queue.get_queue_stats = mock_stats

        # Use asyncio to run the async function
        import asyncio

        asyncio.run(update_queue_metrics(mock_queue))

        assert QUEUE_DEPTH.labels(priority="high")._value.get() == 5
        assert QUEUE_DEPTH.labels(priority="normal")._value.get() == 10
        assert QUEUE_DEPTH.labels(priority="low")._value.get() == 2


class TestModelCostCalculation:
    """Verify model costs are calculated correctly."""

    @pytest.mark.parametrize(
        ("model", "tokens_in", "tokens_out", "expected_min_cost"),
        [
            ("claude-opus-4-5-20251101", 1_000_000, 1_000_000, 90.0),  # $15 + $75
            ("claude-sonnet-4-20250514", 1_000_000, 1_000_000, 18.0),  # $3 + $15
            ("claude-haiku-3-20250515", 1_000_000, 1_000_000, 1.5),  # $0.25 + $1.25
            ("gpt-4o-mini", 1_000_000, 1_000_000, 0.75),  # $0.15 + $0.60
        ],
    )
    def test_cost_calculation_for_models(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        expected_min_cost: float,
    ) -> None:
        """Verify cost calculation for different models."""
        mock_hub = MagicMock()
        reporter = MetricsReporter(mock_hub)
        cost = reporter._calculate_cost(model, tokens_in, tokens_out)

        assert cost >= expected_min_cost


class TestSimplifiedBudgetMetricsRecording:
    """Verify budget health metrics are recorded to Prometheus."""

    def test_record_budget_health_updates_gauges(self) -> None:
        """Verify recording budget health updates all gauges."""
        record_budget_health(
            agent_id="test-agent",
            daily_used=5.0,
            daily_limit=10.0,
            monthly_used=50.0,
            monthly_limit=100.0,
        )

        # Check daily values
        daily_used = BUDGET_USED.labels(agent_id="test-agent", period="daily")._value.get()
        daily_limit = BUDGET_LIMIT.labels(agent_id="test-agent", period="daily")._value.get()
        daily_ratio = BUDGET_HEALTH_RATIO.labels(agent_id="test-agent", period="daily")._value.get()

        assert daily_used == 5.0
        assert daily_limit == 10.0
        assert daily_ratio == 0.5  # 5/10 = 0.5

        # Check monthly values
        monthly_used = BUDGET_USED.labels(agent_id="test-agent", period="monthly")._value.get()
        monthly_limit = BUDGET_LIMIT.labels(agent_id="test-agent", period="monthly")._value.get()
        monthly_ratio = BUDGET_HEALTH_RATIO.labels(
            agent_id="test-agent", period="monthly"
        )._value.get()

        assert monthly_used == 50.0
        assert monthly_limit == 100.0
        assert monthly_ratio == 0.5  # 50/100 = 0.5


class TestModelCostsTable:
    """Verify MODEL_COSTS table has entries for common models."""

    def test_anthropic_models_defined(self) -> None:
        """Verify Anthropic models have cost entries."""
        assert "claude-opus-4-5-20251101" in MODEL_COSTS
        assert "claude-sonnet-4-20250514" in MODEL_COSTS
        assert "claude-haiku-3-20250515" in MODEL_COSTS

    def test_openai_models_defined(self) -> None:
        """Verify OpenAI models have cost entries."""
        assert "gpt-4-turbo" in MODEL_COSTS
        assert "gpt-4o" in MODEL_COSTS
        assert "gpt-4o-mini" in MODEL_COSTS

    def test_default_fallback_exists(self) -> None:
        """Verify default fallback exists for unknown models."""
        assert "default" in MODEL_COSTS
        costs = MODEL_COSTS["default"]
        assert "input" in costs
        assert "output" in costs
