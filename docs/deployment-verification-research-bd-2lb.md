# Deployment Health Verification Approaches for botburrow-agents

**Research Bead:** bd-2lb
**Original Bead:** bd-38r - Verify botburrow-agents deployment health
**Research Approach:** Create detailed comparison document of possible approaches
**Date:** 2026-02-08

## Executive Summary

This document researches and compares different approaches for verifying the health of the botburrow-agents deployment in the apexalgo-iad Kubernetes cluster. The system consists of:

- **Coordinator** (2 replicas) - Leader election, work queue management
- **Runners** (hybrid/notification/exploration) - Agent execution
- **Valkey/Redis** - Coordination layer
- **Skill Sync** - Background configuration sync
- **Dependencies:** Hub API (ardenone-cluster), R2/S3 storage, Git-based agent configs

---

## Current State Analysis

### Existing Infrastructure

**Health Endpoints:**
- `:9090/health` - Coordinator liveness (returns `{"status": "healthy"}`)
- `:9090/ready` - Coordinator readiness (returns `{"status": "ready"}`)
- `:9091/health` - Runner liveness (returns `{"status": "healthy"}`)
- `:9091/ready` - Runner readiness (returns `{"status": "ready"}`)
- `:9090/metrics` - Prometheus metrics (coordinator)
- `:9091/metrics` - Prometheus metrics (runners)

**Kubernetes Probes:**
- Liveness: HTTP `/health` (10s initial, 10s period, 3 failures threshold)
- Readiness: HTTP `/ready` (5s initial, 5s period, 3 failures threshold)
- Valkey: `redis-cli ping` (10s initial, 10s period)

**Prometheus Metrics (18 core metrics):**
```
botburrow_activations_total{agent_id, task_type, status}
botburrow_activation_duration_seconds{agent_id, task_type}
botburrow_activations_in_progress{runner_id}
botburrow_queue_depth{priority}
botburrow_queue_active_tasks
botburrow_queue_agents_in_backoff
botburrow_tokens_consumed_total{agent_id, model, direction}
botburrow_activation_cost_usd_total{agent_id, model}
botburrow_budget_used_usd{agent_id, period}
botburrow_budget_limit_usd{agent_id, period}
botburrow_budget_health_ratio{agent_id, period}
botburrow_coordinator_is_leader{instance_id}
botburrow_runner_heartbeat_timestamp_seconds{runner_id}
botburrow_queue_wait_seconds{agent_id, priority}
botburrow_agent_backoff_seconds_remaining{agent_id}
botburrow_activation_retries_total{agent_id}
```

### Existing Verification Tools

1. **Deployment Guide** (`docs/deployment/deployment.md`) - Manual kubectl commands
2. **Monitoring Tests** (`tests/test_monitoring_verification.py`) - Unit tests for metrics
3. **Kubernetes Probes** - Built-in health checks
4. **Prometheus ServiceMonitor** - Metrics scraping every 15s
5. **HPA** - Horizontal Pod Autoscaler for runners

---

## Verification Approaches Comparison

### Approach 1: Manual kubectl Commands

**Description:** Use kubectl commands directly from a devpod or local machine to check deployment status.

**Implementation:**
```bash
# Check pod status
kubectl get pods -n botburrow-agents

# Check logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=50

# Verify Redis connectivity
kubectl exec -n botburrow-agents valkey-0 -- redis-cli ping

# Check metrics
kubectl port-forward -n botburrow-agents svc/coordinator 9090:9090
curl http://localhost:9090/metrics
```

**Pros:**
- No additional infrastructure required
- Immediate access to detailed information
- Flexible - can check anything on demand
- Already documented in deployment guide

**Cons:**
- Manual process - not automated
- Requires kubectl access and permissions
- Time-consuming for repeated checks
- No continuous monitoring
- Human error prone
- Not suitable for CI/CD integration

**Use Cases:**
- Ad-hoc troubleshooting
- Initial deployment verification
- Debugging specific issues

**Effort:** Low (already documented)
**Maintenance:** Low

---

### Approach 2: Shell Script Automation

**Description:** Create a shell script that runs predefined kubectl commands and reports health status.

**Implementation:**
```bash
#!/bin/bash
# verify-deployment.sh

NAMESPACE="botburrow-agents"
EXIT_CODE=0

echo "=== Checking Pod Status ==="
PODS=$(kubectl get pods -n $NAMESPACE -o json)
RUNNING=$(echo "$PODS" | jq -r '.items[] | select(.status.phase!="Running") | .metadata.name')
if [ -z "$RUNNING" ]; then
    echo "✓ All pods running"
else
    echo "✗ Non-running pods: $RUNNING"
    EXIT_CODE=1
fi

echo "=== Checking Leader Election ==="
LEADER_COUNT=$(kubectl exec -n $NAMESPACE valkey-0 -- redis-cli GET "coordinator:leader" 2>/dev/null | wc -l)
if [ "$LEADER_COUNT" -eq 1 ]; then
    echo "✓ Leader elected"
else
    echo "✗ No leader found"
    EXIT_CODE=1
fi

# ... more checks

exit $EXIT_CODE
```

**Pros:**
- Simple to implement and understand
- Portable across environments
- Easy to modify and extend
- Can be run manually or in CI/CD
- Fast execution

**Cons:**
- Limited to kubectl output
- Hard to parse complex JSON outputs
- No persistent state/history
- Requires jq/other tools for JSON parsing
- No alerting capability
- Linear execution (no parallel checks)

**Use Cases:**
- CI/CD pipeline verification
- Periodic health checks via cron
- Pre-deployment verification
- Quick diagnostics

**Effort:** Medium
**Maintenance:** Medium

**Existing Implementation:** `verify-deployment.sh` already exists (from bd-yct)

---

### Approach 3: Python Verification Script

**Description:** Create a Python script using kubernetes-client API for programmatic health checks.

**Implementation:**
```python
#!/usr/bin/env python3
"""Verify botburrow-agents deployment health."""

from kubernetes import client, config
import requests
import sys

def check_pods(namespace):
    """Check all pods are running."""
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace)
    for pod in pods.items:
        if pod.status.phase != "Running":
            print(f"✗ Pod {pod.metadata.name} not running: {pod.status.phase}")
            return False
    print("✓ All pods running")
    return True

def check_leader(namespace):
    """Check coordinator leader election."""
    v1 = client.CoreV1Api()
    # Check via metrics endpoint or Redis
    resp = v1.connect_get_namespaced_pod_exec("valkey-0", namespace,
        command=["redis-cli", "GET", "coordinator:leader"])
    if resp:
        print("✓ Leader elected")
        return True
    print("✗ No leader")
    return False

def check_metrics(namespace):
    """Check Prometheus metrics are available."""
    v1 = client.CoreV1Api()
    # Port-forward or use service
    svc = v1.read_namespaced_service("coordinator", namespace)
    # Check metrics endpoint
    r = requests.get(f"http://{svc.spec.cluster_ip}:9090/metrics")
    if r.status_code == 200 and "botburrow" in r.text:
        print("✓ Metrics available")
        return True
    return False

def main():
    # Load kubeconfig
    config.load_kube_config()
    namespace = "botburrow-agents"

    checks = [
        check_pods(namespace),
        check_leader(namespace),
        check_metrics(namespace),
    ]

    if all(checks):
        print("\n✓ Deployment healthy")
        return 0
    else:
        print("\n✗ Deployment unhealthy")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**Pros:**
- Rich kubernetes-client API
- Better error handling
- Easier to extend with complex logic
- Can use Python libraries for HTTP, JSON, etc.
- Testable (unit tests)
- Can integrate with existing Python tooling

**Cons:**
- Requires Python environment
- Dependency management (kubernetes-client)
- More complex than shell script
- Slower startup than pure shell

**Use Cases:**
- Programmatic health checks
- Integration with Python-based monitoring
- Complex verification logic
- Test-driven verification

**Effort:** Medium
**Maintenance:** Medium

---

### Approach 4: Prometheus Queries + Alerting

**Description:** Use PromQL queries to monitor deployment health and set up alerts.

**Implementation:**

**PromQL Queries:**
```promql
# Pod health
up{namespace="botburrow-agents", job="coordinator"} == 1
up{namespace="botburrow-agents", job="runner-*"} == 1

# Leader election
botburrow_coordinator_is_leader == 1

# Queue health
botburrow_queue_depth{priority="high"} < 100
botburrow_queue_agents_in_backoff < 5

# Activation health
rate(botburrow_activations_total{status="failure"}[5m]) / rate(botburrow_activations_total[5m]) < 0.1

# Runner health
botburrow_runner_heartbeat_timestamp_seconds > time() - 300
```

**Alertmanager Rules:**
```yaml
groups:
  - name: botburrow-agents
    rules:
      - alert: CoordinatorDown
        expr: up{namespace="botburrow-agents", job="coordinator"} == 0
        for: 2m
        annotations:
          summary: "Coordinator pod down"

      - alert: NoCoordinatorLeader
        expr: sum(botburrow_coordinator_is_leader) == 0
        for: 5m
        annotations:
          summary: "No coordinator leader elected"

      - alert: HighQueueBacklog
        expr: botburrow_queue_depth{priority="high"} > 50
        for: 10m
        annotations:
          summary: "High priority queue backlog"
```

**Pros:**
- Continuous monitoring
- Built-in alerting
- Historical data and trends
- Integration with existing Prometheus
- Scalable to many services
- Rich query language

**Cons:**
- Requires Prometheus infrastructure
- Alert tuning required (reduce false positives)
- Additional complexity
- Dependent on metrics availability
- May need custom exporters

**Use Cases:**
- Production monitoring
- 24/7 health visibility
- Trend analysis
- SLO/SLI monitoring
- Incident response

**Effort:** Low-Medium (Prometheus already deployed)
**Maintenance:** Low

**Existing Infrastructure:** ServiceMonitor already configured

---

### Approach 5: Kubernetes Health Probes Enhanced

**Description:** Enhance the existing Kubernetes liveness/readiness probes with deeper health checks.

**Implementation:**

**Enhanced `/ready` endpoint:**
```python
async def _ready_handler(self, _request: web.Request) -> web.Response:
    """Handle /ready endpoint with deep health checks."""
    checks = {
        "redis": await self._check_redis(),
        "hub_api": await self._check_hub_api(),
        "work_queue": await self._check_work_queue(),
        "config_cache": await self._check_config_cache(),
    }

    all_healthy = all(checks.values())
    status_code = 503 if not all_healthy else 200

    return web.json_response({
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
    }, status=status_code)

async def _check_redis(self):
    """Check Redis connectivity."""
    try:
        await self.redis.ping()
        return True
    except Exception:
        return False

async def _check_hub_api(self):
    """Check Hub API connectivity."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.hub_url}/health", timeout=5) as resp:
                return resp.status == 200
    except Exception:
        return False
```

**Updated Probes:**
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: metrics
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
  # Pod marked not ready if any dependency fails
```

**Pros:**
- Native Kubernetes integration
- Automatic traffic management (service routing)
- No additional infrastructure
- Fast failure detection
- Prevents routing to unhealthy pods
- Already partially implemented

**Cons:**
- Pod restarts on liveness failure (disruptive)
- Limited to pod-local checks
- No cross-pod visibility
- Probe timeouts can cause cascading failures
- Difficult to debug transient failures

**Use Cases:**
- Dependency health checking
- Graceful degradation
- Zero-downtime deployments
- Service mesh integration

**Effort:** Medium
**Maintenance:** Low

---

### Approach 6: Dedicated Health Check Service

**Description:** Create a separate deployment that runs comprehensive health checks and reports status.

**Implementation:**

**Health Check Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: health-checker
  namespace: botburrow-agents
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: health-checker
        image: ghcr.io/botburrow/botburrow-agents:latest
        command: ["python", "-m", "botburrow_agents.health.main"]
        env:
        - name: CHECK_INTERVAL
          value: "60"
        - name: ALERT_WEBHOOK
          value: "https://hooks.example.com/alerts"
```

**Health Check Logic:**
```python
"""Comprehensive health check service."""

import asyncio
import aiohttp
from kubernetes import client, config

class HealthChecker:
    """Run comprehensive health checks."""

    CHECKS = [
        "pods_running",
        "leader_election",
        "redis_connectivity",
        "hub_api_connectivity",
        "work_queue_health",
        "metrics_availability",
        "runner_heartbeats",
        "r2_connectivity",
    ]

    async def run_all_checks(self) -> dict:
        """Run all health checks and return results."""
        results = {}
        for check in self.CHECKS:
            checker = getattr(self, f"check_{check}")
            results[check] = await checker()
        return results

    async def send_alert(self, failed_checks: list[str]):
        """Send alert webhook."""
        async with aiohttp.ClientSession() as session:
            await session.post(
                os.environ["ALERT_WEBHOOK"],
                json={"failed_checks": failed_checks}
            )
```

**Pros:**
- Centralized health logic
- Can check cross-pod dependencies
- Custom alerting integrations
- No impact on main services
- Rich health information
- Can expose dashboard

**Cons:**
- Additional deployment to maintain
- Single point of failure (unless replicated)
- Another service to monitor
- Additional resource usage
- More complex architecture

**Use Cases:**
- Multi-service health aggregation
- Custom alerting requirements
- Health dashboards
- Complex dependency checks

**Effort:** High
**Maintenance:** Medium

---

### Approach 7: ArgoCD Resource Health Checks

**Description:** Use ArgoCD's built-in health assessment for Kubernetes resources.

**Implementation:**

ArgoCD already provides health status for:
- Deployments (replicas available)
- StatefulSets (replicas ready)
- Services (endpoints available)
- ConfigMaps/Secrets (synced)

**Custom Health Checks:**
```yaml
# In ArgoCD Application resource
spec:
  destination:
    namespace: botburrow-agents
  syncPolicy:
    syncOptions:
    - CreateNamespace=true
  healthChecks:
  - kind: Deployment
    name: coordinator
    namespace: botburrow-agents
  - kind: Deployment
    name: runner-hybrid
    namespace: botburrow-agents
```

**Pros:**
- Already integrated with GitOps
- No additional infrastructure
- UI visibility of health status
- Automatic sync on health changes
- Supports custom health checks

**Cons:**
- Limited to resource-level health
- Not application-aware
- Doesn't check business logic
- ArgoCD dependency
- Limited customization

**Use Cases:**
- GitOps deployment verification
- Quick health status in UI
- Automated rollback on unhealthy

**Effort:** Low (already configured)
**Maintenance:** Low

---

### Approach 8: E2E Tests with Deployment Verification

**Description:** Create end-to-end tests that verify the deployment by interacting with the system.

**Implementation:**

```python
"""E2E deployment verification tests."""

import pytest
from kubernetes import client, config
import redis
import requests

@pytest.fixture(scope="module")
def k8s():
    config.load_kube_config()
    return client.CoreV1Api()

def test_coordinator_pods_running(k8s):
    """Verify coordinator pods are running."""
    pods = k8s.list_namespaced_pod(
        "botburrow-agents",
        label_selector="app.kubernetes.io/name=coordinator"
    )
    assert len(pods.items) == 2
    for pod in pods.items:
        assert pod.status.phase == "Running"
        assert pod.status.container_statuses[0].ready

def test_redis_connectivity():
    """Verify Redis/Valkey is accessible."""
    r = redis.Redis(host="valkey.botburrow-agents.svc.cluster.local", port=6379)
    assert r.ping()

def test_coordinator_leader_election():
    """Verify coordinator leader election."""
    r = redis.Redis(host="valkey.botburrow-agents.svc.cluster.local", port=6379)
    leader = r.get("coordinator:leader")
    assert leader is not None

def test_metrics_endpoints():
    """Verify Prometheus metrics are available."""
    resp = requests.get(
        "http://coordinator.botburrow-agents.svc.cluster.local:9090/metrics",
        timeout=5
    )
    assert resp.status_code == 200
    assert "botburrow" in resp.text

def test_health_endpoints():
    """Verify health endpoints return healthy."""
    resp = requests.get(
        "http://coordinator.botburrow-agents.svc.cluster.local:9090/health",
        timeout=5
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

def test_work_queue_exists():
    """Verify work queues exist in Redis."""
    r = redis.Redis(host="valkey.botburrow-agents.svc.cluster.local", port=6379)
    # Queues may be empty but should exist as keys
    assert r.type("work:queue:high") == b"list" or r.type("work:queue:high") == b"none"
```

**Run in CI/CD:**
```yaml
# .github/workflows/deployment-verification.yml
name: Deployment Verification
on: [deployment_status]
jobs:
  verify:
    if: github.event.deployment_status.state == 'success'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install pytest pytest-asyncio kubernetes redis requests
      - name: Configure kubectl
        run: echo "${{ secrets.KUBECONFIG }}" > kubeconfig
      - name: Run E2E tests
        run: pytest tests/e2e/test_deployment_verification.py -v
```

**Pros:**
- Automated testing
- Version controlled
- CI/CD integration
- Testable business logic
- Can run on schedule
- Failure history tracking

**Cons:**
- Requires test framework
- Test maintenance overhead
- May need test environment
- Can be flaky with external dependencies
- Additional CI/CD pipeline setup

**Use Cases:**
- Post-deployment verification
- Pre-production testing
- Scheduled health checks
- Regression testing

**Effort:** Medium-High
**Maintenance:** Medium

---

## Comparison Matrix

| Approach | Complexity | Effort | Maintenance | CI/CD Ready | Real-time | Custom Alerts | Best For |
|----------|------------|--------|-------------|-------------|-----------|---------------|----------|
| Manual kubectl | Low | Low | Low | No | No | No | Ad-hoc troubleshooting |
| Shell Script | Low | Medium | Medium | Yes | No | No | Quick automation |
| Python Script | Medium | Medium | Medium | Yes | No | No | Complex checks |
| Prometheus | Medium | Low | Low | Yes | Yes | Yes | Production monitoring |
| Enhanced Probes | Medium | Medium | Low | Yes | Yes | No | Pod-level health |
| Health Service | High | High | Medium | Yes | Yes | Yes | Multi-service checks |
| ArgoCD Health | Low | Low | Low | Yes | Yes | No | GitOps verification |
| E2E Tests | Medium | High | Medium | Yes | No | No | Automated testing |

---

## Recommended Strategy

### For Immediate Deployment Verification (bd-38r context)

**Best Approach: Shell Script + Manual kubectl**

Since the original bead bd-38r required immediate verification of the deployment, the shell script approach (already implemented in bd-yct) provides the best balance:

1. **Quick to run** - Can execute in seconds
2. **No new infrastructure** - Uses existing kubectl access
3. **Clear output** - Easy to understand results
4. **Documentation** - Serves as verification guide

**Implementation already exists:**
- `verify-deployment.sh` - Comprehensive shell script
- `quick-check.md` - Quick reference guide

### For Ongoing Production Monitoring

**Best Approach: Prometheus Queries + Alerting**

Once the deployment is verified, Prometheus provides the best ongoing monitoring:

1. **Already deployed** - ServiceMonitor configured
2. **Rich metrics** - 18 core metrics available
3. **Alerting** - Built-in Alertmanager integration
4. **Historical data** - Trends and patterns

**Recommended Alerts:**
```yaml
- CoordinatorDown (up == 0 for 2m)
- NoCoordinatorLeader (sum(is_leader) == 0 for 5m)
- HighQueueBacklog (queue_depth > 50 for 10m)
- HighFailureRate (failure_rate > 10% for 5m)
- RunnerStale (heartbeat > 5m ago)
```

### For CI/CD Integration

**Best Approach: E2E Tests + Enhanced Probes**

For automated verification in deployment pipelines:

1. **E2E tests** - Comprehensive verification
2. **Enhanced probes** - Pod-level health
3. **ArgoCD sync** - GitOps integration

---

## Hybrid Approach (Recommended)

**Combine multiple approaches for comprehensive coverage:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Deployment Health Layers                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: Pod Health (Kubernetes Probes)                   │
│  └─> Liveness: Process alive                                │
│  └─> Readiness: Dependencies satisfied                      │
│                                                             │
│  Layer 2: Application Health (Enhanced /ready)              │
│  └─> Redis connectivity                                     │
│  └─> Hub API connectivity                                   │
│  └─> Work queue status                                      │
│                                                             │
│  Layer 3: Service Health (Prometheus Metrics)               │
│  └─> Leader election status                                 │
│  └─> Queue depth                                            │
│  └─> Activation rates                                       │
│  └─> Runner heartbeats                                      │
│                                                             │
│  Layer 4: Business Logic Health (E2E Tests)                 │
│  └─> End-to-end activation flow                            │
│  └─> Work claiming and processing                          │
│  └─> Configuration sync                                     │
│                                                             │
│  Layer 5: Manual Verification (Shell Script)                │
│  └─> Quick deployment check                                 │
│  └─> Troubleshooting guide                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Order:**

1. **Phase 1: Immediate** (Shell Script)
   - Already implemented in bd-yct
   - Use for initial deployment verification

2. **Phase 2: Basic Monitoring** (Prometheus)
   - Set up core alerts
   - Dashboard for key metrics

3. **Phase 3: Enhanced Probes** (Deep Health)
   - Add dependency checks to `/ready`
   - Prevent routing to unhealthy pods

4. **Phase 4: E2E Tests** (CI/CD)
   - Add deployment verification tests
   - Run in CI/CD pipeline

5. **Phase 5: Advanced** (if needed)
   - Dedicated health checker service
   - Custom alerting integrations

---

## Implementation Guidance

### Quick Start (Use Existing)

The shell script approach is already implemented:

```bash
# Run the existing verification script
./verify-deployment.sh

# Or use the quick check guide
cat quick-check.md
```

### Prometheus Alert Setup

Create `k8s/apexalgo-iad/prometheus-rules.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: botburrow-agents-alerts
  namespace: botburrow-agents
spec:
  groups:
    - name: botburrow-agents
      rules:
        - alert: CoordinatorDown
          expr: up{namespace="botburrow-agents",job="coordinator"} == 0
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "Coordinator pod is down"
            description: "Coordinator pod {{ $labels.instance }} has been down for more than 2 minutes"

        - alert: NoCoordinatorLeader
          expr: sum(botburrow_coordinator_is_leader) == 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "No coordinator leader elected"
            description: "No coordinator leader has been elected for 5 minutes"

        - alert: HighQueueBacklog
          expr: botburrow_queue_depth{priority="high"} > 50
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "High priority queue backlog"
            description: "High priority queue has {{ $value }} items pending"

        - alert: HighFailureRate
          expr: |
            rate(botburrow_activations_total{status="failure"}[5m]) /
            rate(botburrow_activations_total[5m]) > 0.1
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High activation failure rate"
            description: "Failure rate is {{ $value | humanizePercentage }}"

        - alert: RunnerStale
          expr: |
            botburrow_runner_heartbeat_timestamp_seconds <
            (time() - 300)
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Runner has stale heartbeat"
            description: "Runner {{ $labels.runner_id }} last heartbeat was more than 5 minutes ago"
```

Apply with:
```bash
kubectl apply -f k8s/apexalgo-iad/prometheus-rules.yaml
```

---

## Conclusion

For **bd-38r (Verify botburrow-agents deployment health)**, the recommended approach is:

1. **Immediate:** Use the existing `verify-deployment.sh` shell script (from bd-yct)
2. **Short-term:** Set up Prometheus alerts for continuous monitoring
3. **Long-term:** Add E2E tests to CI/CD pipeline

The hybrid layered approach provides comprehensive coverage while leveraging existing infrastructure. Start simple and add complexity as needed based on operational requirements.

---

## References

- **Deployment Guide:** `/home/coder/botburrow-agents/docs/deployment/deployment.md`
- **Monitoring Tests:** `/home/coder/botburrow-agents/tests/test_monitoring_verification.py`
- **Observability Code:** `/home/coder/botburrow-agents/src/botburrow_agents/observability.py`
- **Coordinator Deployment:** `/home/coder/botburrow-agents/k8s/apexalgo-iad/coordinator.yaml`
- **ServiceMonitor:** `/home/coder/botburrow-agents/k8s/apexalgo-iad/servicemonitor.yaml`
- **Kubernetes Probes Documentation:** https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- **Prometheus Best Practices:** https://prometheus.io/docs/practices/naming/
- **ArgoCD Health Checks:** https://argo-cd.readthedocs.io/en/stable/user-guide/health/
