"""Simplified tests for agent runner metrics and budget tracking.

This is a simplified-scope alternative to bd-23c. Tests only core functionality:
1. Prometheus metrics endpoint is accessible
2. Consumption tracking (tokens, cost, duration)
3. Budget checking works

Deferred (not in simplified scope):
- Circuit breaker triggers testing
- Runner pool utilization monitoring
- Execution latency percentiles (P50, P95, P99)
- Failed activation retry logic testing
- Priority queue ordering verification
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from botburrow_agents.observability import (
    ACTIVATION_COST,
    ACTIVATION_DURATION,
    ACTIVATIONS_TOTAL,
    BUDGET_HEALTH_RATIO,
    BUDGET_LIMIT,
    BUDGET_USED,
    TOKENS_CONSUMED,
    MetricsServer,
    record_activation_complete,
    record_activation_cost,
    record_activation_start,
    record_budget_health,
    record_tokens,
)
from botburrow_agents.runner.metrics import BudgetChecker, MetricsReporter


class TestPrometheusMetricsEndpoint:
    """Simplified tests for Prometheus metrics endpoint (Requirement 1)."""

    @pytest.mark.asyncio
    async def test_metrics_server_starts(self) -> None:
        """Test that metrics server can start."""
        server = MetricsServer(port=19093, host="127.0.0.1")
        await server.start()
        assert server._site is not None
        await server.stop()

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_data(self) -> None:
        """Test that /metrics endpoint returns Prometheus formatted data."""
        server = MetricsServer(port=19094, host="127.0.0.1")
        await server.start()

        try:
            mock_request = MagicMock()
            response = await server._metrics_handler(mock_request)

            assert response.status == 200
            body = response.body.decode() if hasattr(response, "body") else response.text

            # Should have some Prometheus metrics output
            assert "botburrow" in body or "HELP" in body or "TYPE" in body
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_metrics_exported(self) -> None:
        """Test that key metrics are exported in Prometheus format."""
        # Record some test data
        record_tokens("test-agent", "claude-sonnet-4", 1000, 500)
        record_activation_complete(
            agent_id="test-agent",
            task_type="inbox",
            success=True,
            duration_seconds=10.5,
            runner_id="test-runner",
        )
        record_activation_cost("test-agent", "claude-sonnet-4", 0.05)

        # Start server and get metrics
        server = MetricsServer(port=19095, host="127.0.0.1")
        await server.start()

        try:
            mock_request = MagicMock()
            response = await server._metrics_handler(mock_request)
            body = response.body.decode() if hasattr(response, "body") else response.text

            # Check that our metrics appear in output
            assert "botburrow_tokens_consumed_total" in body
            assert "botburrow_activations_total" in body
            assert "botburrow_activation_cost_usd_total" in body
        finally:
            await server.stop()


class TestConsumptionTracking:
    """Simplified tests for consumption tracking (Requirement 2)."""

    def test_token_tracking_records_input_tokens(self) -> None:
        """Test that input tokens are tracked."""
        record_tokens("token-test-agent", "claude-sonnet-4", tokens_input=5000, tokens_output=0)

        value = TOKENS_CONSUMED.labels(
            agent_id="token-test-agent",
            model="claude-sonnet-4",
            direction="input",
        )._value.get()

        assert value >= 5000

    def test_token_tracking_records_output_tokens(self) -> None:
        """Test that output tokens are tracked."""
        record_tokens("token-test-agent", "claude-sonnet-4", tokens_input=0, tokens_output=2000)

        value = TOKENS_CONSUMED.labels(
            agent_id="token-test-agent",
            model="claude-sonnet-4",
            direction="output",
        )._value.get()

        assert value >= 2000

    def test_cost_tracking_records_usd(self) -> None:
        """Test that activation cost is tracked in USD."""
        record_activation_cost("cost-test-agent", "claude-sonnet-4", 0.123)

        value = ACTIVATION_COST.labels(
            agent_id="cost-test-agent",
            model="claude-sonnet-4",
        )._value.get()

        assert value >= 0.123

    def test_duration_tracking_records_seconds(self) -> None:
        """Test that activation duration is tracked."""
        record_activation_start("duration-test-runner")
        record_activation_complete(
            agent_id="duration-test-agent",
            task_type="inbox",
            success=True,
            duration_seconds=42.5,
            runner_id="duration-test-runner",
        )

        # Verify the duration histogram received the observation
        # ACTIVATION_DURATION should have at least one observation
        assert ACTIVATION_DURATION.labels(
            agent_id="duration-test-agent",
            task_type="inbox",
        )._sum.get() >= 42.5 or ACTIVATION_DURATION.labels(
            agent_id="duration-test-agent",
            task_type="inbox",
        )._count.get() >= 1


class TestMetricsReporter:
    """Tests for MetricsReporter class."""

    def test_record_usage_stores_metrics(self) -> None:
        """Test that record_usage stores metrics for later reporting."""
        mock_hub = AsyncMock()
        reporter = MetricsReporter(mock_hub)

        metrics = reporter.record_usage(
            agent_id="usage-test-agent",
            model="claude-sonnet-4",
            tokens_input=3000,
            tokens_output=1500,
            duration_seconds=30.0,
        )

        assert metrics.tokens_input == 3000
        assert metrics.tokens_output == 1500
        assert metrics.cost_usd > 0
        assert metrics.model == "claude-sonnet-4"
        assert metrics.duration_seconds == 30.0

    def test_calculate_cost_for_known_model(self) -> None:
        """Test cost calculation for known models."""
        mock_hub = AsyncMock()
        reporter = MetricsReporter(mock_hub)

        # Claude Sonnet: $3/M input, $15/M output
        cost = reporter._calculate_cost("claude-sonnet-4-20250514", 1_000_000, 500_000)

        # (1M * $3/M) + (0.5M * $15/M) = $3 + $7.5 = $10.5
        assert cost == 10.5

    def test_calculate_cost_for_unknown_model(self) -> None:
        """Test cost calculation falls back to default for unknown models."""
        mock_hub = AsyncMock()
        reporter = MetricsReporter(mock_hub)

        # Unknown model uses default: $3/M input, $15/M output
        cost = reporter._calculate_cost("unknown-model", 1_000_000, 1_000_000)

        # (1M * $3/M) + (1M * $15/M) = $3 + $15 = $18
        assert cost == 18.0


class TestBudgetChecking:
    """Simplified tests for budget checking (Requirement 3)."""

    @pytest.mark.asyncio
    async def test_budget_check_passes_when_healthy(self) -> None:
        """Test budget check passes when budget is healthy."""
        mock_hub = AsyncMock()
        mock_health = MagicMock()
        mock_health.healthy = True
        mock_health.daily_used = 5.0
        mock_health.daily_limit = 10.0
        mock_health.monthly_used = 50.0
        mock_health.monthly_limit = 100.0
        mock_hub.get_budget_health.return_value = mock_health

        settings = MagicMock()
        checker = BudgetChecker(mock_hub, settings)

        can_proceed, reason = await checker.check_budget("healthy-agent")

        assert can_proceed is True
        assert "budget" in reason.lower() and "ok" in reason.lower()

    @pytest.mark.asyncio
    async def test_budget_check_fails_when_daily_exceeded(self) -> None:
        """Test budget check fails when daily budget exceeded."""
        mock_hub = AsyncMock()
        mock_health = MagicMock()
        mock_health.healthy = False
        mock_health.daily_used = 10.5
        mock_health.daily_limit = 10.0
        mock_health.monthly_used = 50.0
        mock_health.monthly_limit = 100.0
        mock_hub.get_budget_health.return_value = mock_health

        settings = MagicMock()
        checker = BudgetChecker(mock_hub, settings)

        can_proceed, reason = await checker.check_budget("over-budget-agent")

        assert can_proceed is False
        assert "daily" in reason.lower()

    @pytest.mark.asyncio
    async def test_budget_check_fails_when_monthly_exceeded(self) -> None:
        """Test budget check fails when monthly budget exceeded."""
        mock_hub = AsyncMock()
        mock_health = MagicMock()
        mock_health.healthy = False
        mock_health.daily_used = 5.0
        mock_health.daily_limit = 10.0
        mock_health.monthly_used = 100.5
        mock_health.monthly_limit = 100.0
        mock_hub.get_budget_health.return_value = mock_health

        settings = MagicMock()
        checker = BudgetChecker(mock_hub, settings)

        can_proceed, reason = await checker.check_budget("over-monthly-agent")

        assert can_proceed is False
        assert "monthly" in reason.lower()

    @pytest.mark.asyncio
    async def test_budget_check_allows_on_error(self) -> None:
        """Test budget check allows proceeding when check fails."""
        mock_hub = AsyncMock()
        mock_hub.get_budget_health.side_effect = Exception("Hub unavailable")

        settings = MagicMock()
        checker = BudgetChecker(mock_hub, settings)

        can_proceed, reason = await checker.check_budget("error-agent")

        # Should allow proceeding with warning when check fails
        assert can_proceed is True
        assert "failed" in reason.lower() or "anyway" in reason.lower()


class TestBudgetHealthMetrics:
    """Tests for budget health metric recording."""

    def test_record_budget_health_sets_gauges(self) -> None:
        """Test that budget health recording sets Prometheus gauges."""
        record_budget_health(
            agent_id="budget-metrics-agent",
            daily_used=7.5,
            daily_limit=10.0,
            monthly_used=75.0,
            monthly_limit=100.0,
        )

        # Check daily metrics
        assert BUDGET_USED.labels(agent_id="budget-metrics-agent", period="daily")._value.get() == 7.5
        assert BUDGET_LIMIT.labels(agent_id="budget-metrics-agent", period="daily")._value.get() == 10.0

        # Check monthly metrics
        assert BUDGET_USED.labels(agent_id="budget-metrics-agent", period="monthly")._value.get() == 75.0
        assert BUDGET_LIMIT.labels(agent_id="budget-metrics-agent", period="monthly")._value.get() == 100.0

    def test_budget_health_ratio_calculation(self) -> None:
        """Test that budget health ratio is calculated correctly."""
        record_budget_health(
            agent_id="ratio-test-agent",
            daily_used=5.0,
            daily_limit=10.0,
            monthly_used=50.0,
            monthly_limit=100.0,
        )

        # Daily ratio: 5.0 / 10.0 = 0.5
        daily_ratio = BUDGET_HEALTH_RATIO.labels(agent_id="ratio-test-agent", period="daily")._value.get()
        assert abs(daily_ratio - 0.5) < 0.01

        # Monthly ratio: 50.0 / 100.0 = 0.5
        monthly_ratio = BUDGET_HEALTH_RATIO.labels(agent_id="ratio-test-agent", period="monthly")._value.get()
        assert abs(monthly_ratio - 0.5) < 0.01

    def test_budget_health_ratio_handles_zero_limit(self) -> None:
        """Test that budget health ratio handles zero limit gracefully."""
        record_budget_health(
            agent_id="zero-limit-agent",
            daily_used=1.0,
            daily_limit=0.0,
            monthly_used=10.0,
            monthly_limit=0.0,
        )

        # Should set ratio to 0 when limit is 0 (avoid division by zero)
        daily_ratio = BUDGET_HEALTH_RATIO.labels(agent_id="zero-limit-agent", period="daily")._value.get()
        monthly_ratio = BUDGET_HEALTH_RATIO.labels(agent_id="zero-limit-agent", period="monthly")._value.get()

        assert daily_ratio == 0.0
        assert monthly_ratio == 0.0
