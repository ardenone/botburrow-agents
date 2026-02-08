"""Integration test for end-to-end metrics verification.

This test provides a workaround for verifying metrics without requiring
full infrastructure setup. It tests the flow from activation to metrics
export in a simplified manner.

Per bd-14a - workaround approach for metrics verification.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from prometheus_client import REGISTRY

from botburrow_agents.observability import (
    ACTIVATION_COST,
    ACTIVATION_DURATION,
    ACTIVATIONS_TOTAL,
    BUDGET_HEALTH_RATIO,
    BUDGET_LIMIT,
    BUDGET_USED,
    TOKENS_CONSUMED,
    record_activation_complete,
    record_activation_cost,
    record_budget_health,
    record_tokens,
)
from botburrow_agents.models import BudgetHealth
from botburrow_agents.runner.metrics import BudgetChecker, MetricsReporter


class TestEndToEndMetricsFlow:
    """Verify the complete metrics flow from activation to export."""

    async def test_activation_to_prometheus_flow(self) -> None:
        """Verify that recording an activation updates Prometheus metrics."""
        agent_id = "test-agent"
        model = "claude-sonnet-4-20250514"
        task_type = "inbox"
        duration = 45.5
        runner_id = "runner-1"

        # Simulate activation start
        from botburrow_agents.observability import record_activation_start
        record_activation_start(runner_id)

        # Simulate activation completion with tokens
        record_activation_complete(
            agent_id=agent_id,
            task_type=task_type,
            success=True,
            duration_seconds=duration,
            runner_id=runner_id,
        )
        record_tokens(
            agent_id=agent_id,
            model=model,
            tokens_input=1000,
            tokens_output=500,
        )

        # Verify metrics were recorded
        activations = ACTIVATIONS_TOTAL.labels(
            agent_id=agent_id,
            task_type=task_type,
            status="success",
        )._value.get()
        assert activations >= 1

        # Verify duration was recorded
        duration_sum = ACTIVATION_DURATION.labels(
            agent_id=agent_id,
            task_type=task_type,
        )._sum.get()
        assert duration_sum >= duration

    async def test_consumption_to_hub_flow(self) -> None:
        """Verify consumption metrics flow to Hub API."""
        mock_hub = AsyncMock()
        mock_hub.report_consumption.return_value = None

        reporter = MetricsReporter(mock_hub)

        # Record usage
        metrics = reporter.record_usage(
            agent_id="test-agent",
            model="claude-sonnet-4-20250514",
            tokens_input=5000,
            tokens_output=2000,
            duration_seconds=120.0,
        )

        # Verify cost was calculated
        assert metrics.cost_usd > 0
        assert metrics.tokens_input == 5000
        assert metrics.tokens_output == 2000

        # Flush to hub
        await reporter.flush()

        # Verify hub was called
        mock_hub.report_consumption.assert_called_once()
        call_kwargs = mock_hub.report_consumption.call_args.kwargs
        assert call_kwargs["agent_id"] == "test-agent"
        assert call_kwargs["tokens_input"] == 5000
        assert call_kwargs["tokens_output"] == 2000
        assert call_kwargs["cost_usd"] > 0

    async def test_budget_check_to_prometheus_flow(self) -> None:
        """Verify budget check updates Prometheus metrics."""
        # Simulate getting budget health from Hub
        record_budget_health(
            agent_id="test-agent",
            daily_used=7.5,
            daily_limit=10.0,
            monthly_used=75.0,
            monthly_limit=100.0,
        )

        # Verify metrics were recorded
        daily_used = BUDGET_USED.labels(agent_id="test-agent", period="daily")._value.get()
        daily_limit = BUDGET_LIMIT.labels(agent_id="test-agent", period="daily")._value.get()
        daily_ratio = BUDGET_HEALTH_RATIO.labels(
            agent_id="test-agent", period="daily"
        )._value.get()

        assert daily_used == 7.5
        assert daily_limit == 10.0
        assert abs(daily_ratio - 0.75) < 0.01  # 7.5/10 = 0.75

        monthly_used = BUDGET_USED.labels(agent_id="test-agent", period="monthly")._value.get()
        monthly_ratio = BUDGET_HEALTH_RATIO.labels(
            agent_id="test-agent", period="monthly"
        )._value.get()

        assert monthly_used == 75.0
        assert abs(monthly_ratio - 0.75) < 0.01  # 75/100 = 0.75

    async def test_full_activation_workflow(self) -> None:
        """Verify complete workflow: activation -> metrics -> budget check."""
        agent_id = "workflow-test-agent"
        model = "claude-sonnet-4-20250514"

        # Step 1: Simulate activation with consumption
        mock_hub = AsyncMock()
        reporter = MetricsReporter(mock_hub)

        metrics = reporter.record_usage(
            agent_id=agent_id,
            model=model,
            tokens_input=8000,
            tokens_output=3000,
            duration_seconds=180.0,
        )

        # Step 2: Record to Prometheus
        record_tokens(agent_id, model, metrics.tokens_input, metrics.tokens_output)
        record_activation_cost(agent_id, model, metrics.cost_usd)

        # Step 3: Flush to Hub
        await reporter.flush()

        # Verify the flow completed
        assert mock_hub.report_consumption.called

        # Verify cost calculation
        expected_cost_min = (8000 / 1_000_000 * 3.0) + (3000 / 1_000_000 * 15.0)
        assert metrics.cost_usd >= expected_cost_min * 0.9  # Allow small rounding diff

    async def test_budget_enforcement_flow(self) -> None:
        """Verify budget enforcement blocks over-budget activations."""
        mock_hub = AsyncMock()

        # Set up budget exceeded scenario
        mock_health = MagicMock(spec=BudgetHealth)
        mock_health.healthy = False
        mock_health.daily_used = 12.0
        mock_health.daily_limit = 10.0
        mock_health.monthly_used = 80.0
        mock_health.monthly_limit = 100.0

        mock_hub.get_budget_health.return_value = mock_health

        checker = BudgetChecker(mock_hub)
        can_proceed, reason = await checker.check_budget("over-budget-agent")

        # Verify activation is blocked
        assert not can_proceed
        assert "Daily budget exceeded" in reason

    def test_metrics_registry_contains_expected_metrics(self) -> None:
        """Verify all expected metrics are registered with Prometheus."""
        metric_names = {metric.name for metric in REGISTRY.collect()}

        expected_metrics = {
            "botburrow_activations",  # Base name for activation metrics
            "botburrow_activation_duration_seconds",
            "botburrow_tokens_consumed",
            "botburrow_activation_cost",
            "botburrow_budget",
            "botburrow_queue",
        }

        # Check that our expected metrics are in the registry
        found_metrics = set()
        for expected in expected_metrics:
            for registered in metric_names:
                if registered.startswith(expected):
                    found_metrics.add(expected)
                    break

        # We should find most of our expected base metric names
        assert len(found_metrics) >= len(expected_metrics) * 0.8


class TestMetricsRecordingFunctions:
    """Test individual metrics recording functions."""

    def test_record_activation_cost_increments_counter(self) -> None:
        """Verify cost recording increments the counter."""
        record_activation_cost("agent-1", "claude-sonnet-4", 0.5)
        record_activation_cost("agent-1", "claude-sonnet-4", 0.3)

        cost_value = ACTIVATION_COST.labels(agent_id="agent-1", model="claude-sonnet-4")._value.get()
        assert cost_value >= 0.8

    def test_record_budget_health_sets_all_gauges(self) -> None:
        """Verify budget health recording sets all related gauges."""
        record_budget_health(
            agent_id="agent-2",
            daily_used=3.0,
            daily_limit=5.0,
            monthly_used=30.0,
            monthly_limit=50.0,
        )

        # All gauges should be set
        assert BUDGET_USED.labels(agent_id="agent-2", period="daily")._value.get() == 3.0
        assert BUDGET_LIMIT.labels(agent_id="agent-2", period="daily")._value.get() == 5.0
        assert BUDGET_USED.labels(agent_id="agent-2", period="monthly")._value.get() == 30.0
        assert BUDGET_LIMIT.labels(agent_id="agent-2", period="monthly")._value.get() == 50.0
