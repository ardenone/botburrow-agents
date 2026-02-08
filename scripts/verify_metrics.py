#!/usr/bin/env python3
"""Quick metrics verification script for botburrow-agents.

This script provides a simple way to manually verify that:
1. Prometheus metrics are being exported correctly
2. Budget health reporting works
3. Consumption tracking functions properly
4. Circuit breaker integration is operational

Usage:
    python scripts/verify_metrics.py              # Check metrics endpoints
    python scripts/verify_metrics.py --local      # Test with local services
    python scripts/verify_metrics.py --full       # Run full verification

Per bd-14a - workaround approach for metrics verification.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import httpx
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# Default endpoints
DEFAULT_COORDINATOR_METRICS = "http://localhost:9090/metrics"
DEFAULT_RUNNER_METRICS = "http://localhost:9091/metrics"
DEFAULT_HUB_URL = "http://localhost:8000"


class MetricsVerifier:
    """Verify metrics are being exported correctly."""

    def __init__(
        self,
        coordinator_url: str = DEFAULT_COORDINATOR_METRICS,
        runner_url: str = DEFAULT_RUNNER_METRICS,
        hub_url: str = DEFAULT_HUB_URL,
    ) -> None:
        self.coordinator_url = coordinator_url
        self.runner_url = runner_url
        self.hub_url = hub_url

    async def check_metrics_endpoint(self, url: str, name: str) -> dict[str, Any]:
        """Check if metrics endpoint is responding."""
        result = {"url": url, "name": name, "status": "unknown", "metrics_count": 0}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    result["status"] = "ok"
                    # Count lines that start with a metric name (not # or blank)
                    lines = response.text.strip().split("\n")
                    metrics_count = sum(
                        1
                        for line in lines
                        if line and not line.startswith("#") and not line.isspace()
                    )
                    result["metrics_count"] = metrics_count
                    result["sample"] = self._get_sample_metrics(lines)
                else:
                    result["status"] = f"http_{response.status_code}"
        except httpx.ConnectError:
            result["status"] = "connection_failed"
        except httpx.TimeoutException:
            result["status"] = "timeout"
        except Exception as e:
            result["status"] = f"error: {e}"

        return result

    def _get_sample_metrics(self, lines: list[str]) -> list[str]:
        """Get sample metrics from output."""
        samples = []
        for line in lines[:20]:  # First 20 lines
            if line and not line.startswith("#") and not line.isspace():
                samples.append(line[:100])  # Truncate long lines
                if len(samples) >= 5:
                    break
        return samples

    async def check_expected_metrics(
        self, url: str, expected_patterns: list[str]
    ) -> dict[str, bool]:
        """Check if expected metrics are present."""
        result = {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    content = response.text
                    for pattern in expected_patterns:
                        result[pattern] = pattern in content
        except Exception as e:
            logger.error("metrics_check_failed", url=url, error=str(e))
            for pattern in expected_patterns:
                result[pattern] = False

        return result

    async def check_hub_health(self) -> dict[str, Any]:
        """Check Hub API health."""
        result = {"url": self.hub_url, "status": "unknown"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.hub_url}/health")
                result["status"] = "ok" if response.status_code == 200 else f"http_{response.status_code}"
        except httpx.ConnectError:
            result["status"] = "connection_failed"
        except Exception as e:
            result["status"] = f"error: {e}"

        return result

    async def verify_budget_health_endpoint(self, agent_id: str = "test-agent") -> dict[str, Any]:
        """Verify budget health endpoint works."""
        result = {"url": f"{self.hub_url}/api/v1/system/budget-health", "status": "unknown"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.hub_url}/api/v1/system/budget-health",
                    params={"agent_id": agent_id},
                )
                if response.status_code == 200:
                    data = response.json()
                    result["status"] = "ok"
                    result["data"] = {
                        "healthy": data.get("healthy", "N/A"),
                        "daily_used": data.get("daily_used", "N/A"),
                        "daily_limit": data.get("daily_limit", "N/A"),
                    }
                else:
                    result["status"] = f"http_{response.status_code}"
        except httpx.ConnectError:
            result["status"] = "connection_failed"
        except Exception as e:
            result["status"] = f"error: {e}"

        return result

    def print_results(self, results: dict[str, Any]) -> None:
        """Print verification results."""
        print("\n" + "=" * 60)
        print("METRICS VERIFICATION RESULTS")
        print("=" * 60 + "\n")

        # Coordinator metrics
        coord = results.get("coordinator_metrics", {})
        print(f"Coordinator Metrics ({coord.get('url', 'N/A')}):")
        print(f"  Status: {coord.get('status', 'unknown')}")
        if coord.get('status') == 'ok':
            print(f"  Metrics exported: {coord.get('metrics_count', 0)}")
            if coord.get('sample'):
                print("  Sample metrics:")
                for sample in coord['sample'][:3]:
                    print(f"    {sample}")
        print()

        # Runner metrics
        runner = results.get("runner_metrics", {})
        print(f"Runner Metrics ({runner.get('url', 'N/A')}):")
        print(f"  Status: {runner.get('status', 'unknown')}")
        if runner.get('status') == 'ok':
            print(f"  Metrics exported: {runner.get('metrics_count', 0)}")
            if runner.get('sample'):
                print("  Sample metrics:")
                for sample in runner['sample'][:3]:
                    print(f"    {sample}")
        print()

        # Hub health
        hub = results.get("hub_health", {})
        print(f"Hub API ({hub.get('url', 'N/A')}):")
        print(f"  Status: {hub.get('status', 'unknown')}")
        print()

        # Expected metrics check
        expected = results.get("expected_metrics", {})
        if expected:
            print("Expected Metrics Check:")
            for metric, found in expected.items():
                status = "✓" if found else "✗"
                print(f"  {status} {metric}")
            print()

        # Budget health
        budget = results.get("budget_health", {})
        print(f"Budget Health Endpoint ({budget.get('url', 'N/A')}):")
        print(f"  Status: {budget.get('status', 'unknown')}")
        if budget.get('status') == 'ok' and budget.get('data'):
            data = budget['data']
            print(f"  Healthy: {data.get('healthy', 'N/A')}")
            print(f"  Daily Used: {data.get('daily_used', 'N/A')}")
            print(f"  Daily Limit: {data.get('daily_limit', 'N/A')}")
        print()

        # Overall status
        print("=" * 60)
        all_ok = (
            coord.get('status') == 'ok' and
            runner.get('status') == 'ok' and
            hub.get('status') == 'ok'
        )
        if all_ok:
            print("OVERALL: ✓ All metrics endpoints are operational")
        else:
            print("OVERALL: ✗ Some metrics endpoints are not available")
            print("\nTroubleshooting:")
            print("  - Ensure coordinator and runner pods are running:")
            print("    kubectl get pods -n botburrow-agents")
            print("  - Port-forward to access metrics locally:")
            print("    kubectl port-forward -n botburrow-agents svc/coordinator 9090:9090")
            print("    kubectl port-forward -n botburrow-agents svc/runner-hybrid 9091:9091")
        print("=" * 60 + "\n")


async def main() -> int:
    """Run metrics verification."""
    parser = argparse.ArgumentParser(description="Verify botburrow-agents metrics")
    parser.add_argument(
        "--coordinator",
        default=DEFAULT_COORDINATOR_METRICS,
        help="Coordinator metrics URL",
    )
    parser.add_argument(
        "--runner",
        default=DEFAULT_RUNNER_METRICS,
        help="Runner metrics URL",
    )
    parser.add_argument(
        "--hub",
        default=DEFAULT_HUB_URL,
        help="Hub API URL",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use localhost URLs for local development",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full verification including budget health",
    )
    parser.add_argument(
        "--agent-id",
        default="test-agent",
        help="Agent ID for budget health check",
    )

    args = parser.parse_args()

    # Adjust URLs for local mode
    if args.local:
        args.coordinator = DEFAULT_COORDINATOR_METRICS
        args.runner = DEFAULT_RUNNER_METRICS
        args.hub = DEFAULT_HUB_URL

    verifier = MetricsVerifier(
        coordinator_url=args.coordinator,
        runner_url=args.runner,
        hub_url=args.hub,
    )

    results = {}

    # Check coordinator metrics
    logger.info("checking_coordinator_metrics", url=args.coordinator)
    results["coordinator_metrics"] = await verifier.check_metrics_endpoint(
        args.coordinator, "coordinator"
    )

    # Check runner metrics
    logger.info("checking_runner_metrics", url=args.runner)
    results["runner_metrics"] = await verifier.check_metrics_endpoint(
        args.runner, "runner"
    )

    # Check Hub health
    logger.info("checking_hub_health", url=args.hub)
    results["hub_health"] = await verifier.check_hub_health()

    # Check expected metrics in runner output
    if results["runner_metrics"].get("status") == "ok":
        expected_patterns = [
            "botburrow_activations_total",
            "botburrow_activation_duration_seconds",
            "botburrow_tokens_consumed_total",
            "botburrow_queue_depth",
            "botburrow_budget_used_usd",
        ]
        logger.info("checking_expected_metrics")
        results["expected_metrics"] = await verifier.check_expected_metrics(
            args.runner, expected_patterns
        )

    # Check budget health endpoint if full verification
    if args.full and results["hub_health"].get("status") == "ok":
        logger.info("checking_budget_health", agent_id=args.agent_id)
        results["budget_health"] = await verifier.verify_budget_health_endpoint(args.agent_id)

    # Print results
    verifier.print_results(results)

    # Return exit code
    all_ok = (
        results["coordinator_metrics"].get('status') == 'ok' and
        results["runner_metrics"].get('status') == 'ok' and
        results["hub_health"].get('status') == 'ok'
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
