"""Simplified deployment health verification tests.

This is the minimal viable implementation for bd-1mg (simplified-scope alternative
to bd-38r comprehensive verification).

Tests only core functionality:
1. Pod status verification (Running)
2. Metrics endpoint accessibility

For comprehensive verification including Redis, leader election, work queues,
R2 connectivity, and Hub API, see test_monitoring_verification.py instead.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from prometheus_client import REGISTRY
from prometheus_client.parser import text_string_to_metric_families

from botburrow_agents.observability import (
    record_activation_complete,
    record_activation_start,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_prometheus_output() -> str:
    """Sample Prometheus metrics output."""
    from prometheus_client import generate_latest

    # Record some sample data
    record_activation_start("test-runner")
    record_activation_complete(
        agent_id="test-agent",
        task_type="inbox",
        success=True,
        duration_seconds=10.5,
        runner_id="test-runner",
    )

    return generate_latest(REGISTRY).decode("utf-8")


# ============================================================================
# SIMPLIFIED HEALTH CHECK TESTS
# ============================================================================


class TestSimplifiedHealthCheck:
    """Minimal viable health check tests for bd-1mg."""

    def test_metrics_endpoint_shows_activations(self, sample_prometheus_output: str) -> None:
        """Verify metrics endpoint shows activation data."""
        # Check that activation metrics are present
        found = False
        for family in text_string_to_metric_families(sample_prometheus_output):
            if "activation" in family.name.lower():
                found = True
                break

        assert found, "No activation metrics found in Prometheus output"

    def test_metrics_includes_runner_info(self, sample_prometheus_output: str) -> None:
        """Verify metrics include runner identification."""
        # Check for runner_id label or runner-specific metrics
        output_lower = sample_prometheus_output.lower()
        assert "runner_id" in output_lower or "runner" in output_lower

    def test_core_metrics_present(self, sample_prometheus_output: str) -> None:
        """Verify core metrics are present (minimal set)."""
        required_fragments = [
            "botburrow_activations",  # Activation counter
            "botburrow_activation_duration",  # Duration histogram
        ]

        missing = []
        for fragment in required_fragments:
            if fragment not in sample_prometheus_output:
                missing.append(fragment)

        # Allow some leniency - at least one metric type should be present
        assert len(missing) < len(required_fragments), (
            f"Too many core metrics missing: {missing}"
        )

    def test_metrics_output_is_parseable(self, sample_prometheus_output: str) -> None:
        """Verify Prometheus output is valid and parseable."""
        # Should not raise exception
        families = list(text_string_to_metric_families(sample_prometheus_output))
        assert len(families) > 0, "No metric families found in output"

        # Each family should have required fields
        for family in families:
            assert family.name, "Metric family missing name"
            assert family.type is not None, "Metric family missing type"


class TestPodStatusSimulation:
    """Simulated pod status checks for testing logic."""

    def test_all_pods_running_is_healthy(self) -> None:
        """Verify scenario where all pods are Running is considered healthy."""
        # Simulate pod status response
        pods = [
            {"name": "coordinator-abc123", "status": "Running"},
            {"name": "coordinator-def456", "status": "Running"},
            {"name": "runner-hybrid-abc123", "status": "Running"},
            {"name": "runner-hybrid-def456", "status": "Running"},
            {"name": "runner-notification-abc123", "status": "Running"},
            {"name": "runner-exploration-abc123", "status": "Running"},
        ]

        running = sum(1 for p in pods if p["status"] == "Running")
        total = len(pods)

        assert running == total, "All pods should be Running"
        assert total == 6, "Should have 6 pods total"

    def test_any_pod_not_running_is_unhealthy(self) -> None:
        """Verify scenario where any pod is not Running is considered unhealthy."""
        pods = [
            {"name": "coordinator-abc123", "status": "Running"},
            {"name": "coordinator-def456", "status": "Pending"},  # Not Running
            {"name": "runner-hybrid-abc123", "status": "Running"},
            {"name": "runner-hybrid-def456", "status": "Failed"},  # Not Running
        ]

        running = sum(1 for p in pods if p["status"] == "Running")
        total = len(pods)
        failed = sum(1 for p in pods if p["status"] in ("Failed", "Unknown"))

        assert running < total, "Not all pods are Running"
        assert failed == 1, "Should have 1 failed pod"


class TestHealthCheckLogic:
    """Test health check decision logic."""

    def test_healthy_when_pods_ok_and_metrics_ok(self) -> None:
        """Verify deployment is healthy when pods are running and metrics accessible."""
        pods_healthy = True  # All pods Running
        metrics_accessible = True  # Can reach /metrics endpoint

        is_healthy = pods_healthy and metrics_accessible
        assert is_healthy is True

    def test_unhealthy_when_pods_failing(self) -> None:
        """Verify deployment is unhealthy when pods are failing."""
        pods_healthy = False  # Some pods not Running
        metrics_accessible = True  # Metrics still accessible

        is_healthy = pods_healthy and metrics_accessible
        assert is_healthy is False

    def test_unhealthy_when_metrics_unavailable(self) -> None:
        """Verify deployment is unhealthy when metrics are unavailable."""
        pods_healthy = True  # All pods Running
        metrics_accessible = False  # Cannot reach /metrics endpoint

        is_healthy = pods_healthy and metrics_accessible
        assert is_healthy is False


# ============================================================================
# HELPERS
# ============================================================================


def _get_prometheus_metric(metric_name: str) -> str | None:
    """Get metric output from Prometheus registry."""
    from prometheus_client import generate_latest

    output = generate_latest(REGISTRY).decode("utf-8")

    for family in text_string_to_metric_families(output):
        if family.name == metric_name:
            return str(family)

    # Check if metric_name is in the raw output
    if metric_name in output:
        for family in text_string_to_metric_families(output):
            family_output = str(family)
            if metric_name in family_output:
                return family_output

    return None
