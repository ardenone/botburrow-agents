"""Tests for observability module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from botburrow_agents.observability import (
    ACTIVATION_DURATION,
    ACTIVATIONS_IN_PROGRESS,
    ACTIVATIONS_TOTAL,
    COORDINATOR_IS_LEADER,
    POLL_DURATION,
    QUEUE_ACTIVE_TASKS,
    QUEUE_AGENTS_IN_BACKOFF,
    QUEUE_DEPTH,
    RUNNER_HEARTBEAT_TIMESTAMP,
    RUNNER_INFO,
    TOKENS_CONSUMED,
    MetricsServer,
    record_activation_complete,
    record_activation_start,
    record_poll_duration,
    record_tokens,
    run_metrics_collector,
    set_leader_status,
    set_runner_heartbeat,
    set_runner_info,
    update_queue_metrics,
)


class TestMetricFunctions:
    """Tests for metric recording functions."""

    def test_record_activation_start(self) -> None:
        """Test recording activation start."""
        # Get initial value
        initial = ACTIVATIONS_IN_PROGRESS.labels(runner_id="test-runner-1")._value.get()

        record_activation_start("test-runner-1")

        new_value = ACTIVATIONS_IN_PROGRESS.labels(runner_id="test-runner-1")._value.get()
        assert new_value == initial + 1

    def test_record_activation_complete_success(self) -> None:
        """Test recording successful activation completion."""
        # Increment first so we can decrement
        record_activation_start("test-runner-2")

        record_activation_complete(
            agent_id="test-agent",
            task_type="inbox",
            success=True,
            duration_seconds=10.5,
            runner_id="test-runner-2",
        )

        # Check counter incremented
        counter_value = ACTIVATIONS_TOTAL.labels(
            agent_id="test-agent",
            task_type="inbox",
            status="success",
        )._value.get()
        assert counter_value >= 1

    def test_record_activation_complete_failure(self) -> None:
        """Test recording failed activation."""
        record_activation_start("test-runner-3")

        record_activation_complete(
            agent_id="test-agent-fail",
            task_type="discovery",
            success=False,
            duration_seconds=5.0,
            runner_id="test-runner-3",
        )

        counter_value = ACTIVATIONS_TOTAL.labels(
            agent_id="test-agent-fail",
            task_type="discovery",
            status="failure",
        )._value.get()
        assert counter_value >= 1

    def test_record_tokens(self) -> None:
        """Test recording token consumption."""
        record_tokens(
            agent_id="token-agent",
            model="claude-sonnet-4",
            tokens_input=100,
            tokens_output=50,
        )

        input_value = TOKENS_CONSUMED.labels(
            agent_id="token-agent",
            model="claude-sonnet-4",
            direction="input",
        )._value.get()
        output_value = TOKENS_CONSUMED.labels(
            agent_id="token-agent",
            model="claude-sonnet-4",
            direction="output",
        )._value.get()

        assert input_value >= 100
        assert output_value >= 50

    def test_record_poll_duration(self) -> None:
        """Test recording poll duration."""
        # Just verify it doesn't raise
        record_poll_duration(1.5)

    def test_set_leader_status_true(self) -> None:
        """Test setting leader status to true."""
        set_leader_status("coordinator-1", True)

        value = COORDINATOR_IS_LEADER.labels(instance_id="coordinator-1")._value.get()
        assert value == 1

    def test_set_leader_status_false(self) -> None:
        """Test setting leader status to false."""
        set_leader_status("coordinator-2", False)

        value = COORDINATOR_IS_LEADER.labels(instance_id="coordinator-2")._value.get()
        assert value == 0

    def test_set_runner_info(self) -> None:
        """Test setting runner info."""
        # Just verify it doesn't raise
        set_runner_info("runner-1", "hybrid", "1.0.0")

    def test_set_runner_heartbeat(self) -> None:
        """Test setting runner heartbeat."""
        set_runner_heartbeat("heartbeat-runner")

        value = RUNNER_HEARTBEAT_TIMESTAMP.labels(runner_id="heartbeat-runner")._value.get()
        assert value > 0  # Should be a timestamp


class TestUpdateQueueMetrics:
    """Tests for update_queue_metrics function."""

    async def test_update_queue_metrics(self) -> None:
        """Test updating queue metrics from WorkQueue."""
        mock_queue = AsyncMock()
        mock_queue.get_queue_stats.return_value = {
            "queue_high": 5,
            "queue_normal": 10,
            "queue_low": 2,
            "active_tasks": 3,
            "agents_in_backoff": 1,
        }

        await update_queue_metrics(mock_queue)

        assert QUEUE_DEPTH.labels(priority="high")._value.get() == 5
        assert QUEUE_DEPTH.labels(priority="normal")._value.get() == 10
        assert QUEUE_DEPTH.labels(priority="low")._value.get() == 2
        assert QUEUE_ACTIVE_TASKS._value.get() == 3
        assert QUEUE_AGENTS_IN_BACKOFF._value.get() == 1

    async def test_update_queue_metrics_error(self) -> None:
        """Test that errors in queue stats don't propagate."""
        mock_queue = AsyncMock()
        mock_queue.get_queue_stats.side_effect = Exception("Redis error")

        # Should not raise
        await update_queue_metrics(mock_queue)


class TestMetricsServer:
    """Tests for MetricsServer class."""

    @pytest.fixture
    def server(self) -> MetricsServer:
        """Create test metrics server."""
        return MetricsServer(port=19090, host="127.0.0.1")

    async def test_start_and_stop(self, server: MetricsServer) -> None:
        """Test starting and stopping the server."""
        await server.start()
        assert server._site is not None
        assert server._runner is not None

        await server.stop()

    async def test_metrics_handler(self, server: MetricsServer) -> None:
        """Test /metrics endpoint handler."""
        await server.start()

        try:
            # Create a mock request
            mock_request = MagicMock()

            response = await server._metrics_handler(mock_request)

            assert response.status == 200
            assert "text/plain" in response.content_type
        finally:
            await server.stop()

    async def test_health_handler(self, server: MetricsServer) -> None:
        """Test /health endpoint handler."""
        await server.start()

        try:
            mock_request = MagicMock()

            response = await server._health_handler(mock_request)

            assert response.status == 200
            # Check response body
            body = response.body.decode() if hasattr(response, 'body') else str(response.text)
            assert "healthy" in body
        finally:
            await server.stop()

    async def test_ready_handler(self, server: MetricsServer) -> None:
        """Test /ready endpoint handler."""
        await server.start()

        try:
            mock_request = MagicMock()

            response = await server._ready_handler(mock_request)

            assert response.status == 200
            body = response.body.decode() if hasattr(response, 'body') else str(response.text)
            assert "ready" in body
        finally:
            await server.stop()

    async def test_stop_without_start(self, server: MetricsServer) -> None:
        """Test that stop handles case where server wasn't started."""
        # Should not raise
        await server.stop()


class TestMetricsCollector:
    """Tests for run_metrics_collector background task."""

    async def test_metrics_collector_runs(self) -> None:
        """Test that metrics collector updates queue metrics."""
        mock_queue = AsyncMock()
        mock_queue.get_queue_stats.return_value = {
            "queue_high": 1,
            "queue_normal": 2,
            "queue_low": 0,
            "active_tasks": 1,
            "agents_in_backoff": 0,
        }

        # Run collector with short interval
        task = asyncio.create_task(run_metrics_collector(mock_queue, interval=1))

        # Wait for at least one iteration
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify get_queue_stats was called
        mock_queue.get_queue_stats.assert_called()

    async def test_metrics_collector_handles_none_queue(self) -> None:
        """Test that collector handles None queue gracefully."""
        task = asyncio.create_task(run_metrics_collector(None, interval=1))

        # Wait briefly
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should complete without error

    async def test_metrics_collector_handles_errors(self) -> None:
        """Test that collector continues after errors."""
        mock_queue = AsyncMock()
        call_count = 0

        async def stats_with_error() -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary error")
            return {
                "queue_high": 0,
                "queue_normal": 0,
                "queue_low": 0,
                "active_tasks": 0,
                "agents_in_backoff": 0,
            }

        mock_queue.get_queue_stats = stats_with_error

        task = asyncio.create_task(run_metrics_collector(mock_queue, interval=0.05))

        # Wait for multiple iterations
        await asyncio.sleep(0.2)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have been called multiple times despite error
        assert call_count >= 2


class TestPrometheusMetricDefinitions:
    """Tests for Prometheus metric definitions."""

    def test_activation_metrics_exist(self) -> None:
        """Test activation metrics are defined."""
        assert ACTIVATIONS_TOTAL is not None
        assert ACTIVATION_DURATION is not None
        assert ACTIVATIONS_IN_PROGRESS is not None

    def test_queue_metrics_exist(self) -> None:
        """Test queue metrics are defined."""
        assert QUEUE_DEPTH is not None
        assert QUEUE_ACTIVE_TASKS is not None
        assert QUEUE_AGENTS_IN_BACKOFF is not None

    def test_runner_metrics_exist(self) -> None:
        """Test runner metrics are defined."""
        assert RUNNER_INFO is not None
        assert RUNNER_HEARTBEAT_TIMESTAMP is not None

    def test_coordinator_metrics_exist(self) -> None:
        """Test coordinator metrics are defined."""
        assert COORDINATOR_IS_LEADER is not None
        assert POLL_DURATION is not None

    def test_token_metrics_exist(self) -> None:
        """Test token consumption metrics are defined."""
        assert TOKENS_CONSUMED is not None
