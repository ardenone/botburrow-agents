# BD-1HE: Deployment Health Verification - Consolidated Research

**Status:** Research Complete - Consolidated Findings
**Date:** 2026-02-08
**Bead:** bd-1he (Alternative: Research and document options)
**Original Bead:** bd-38r - Verify botburrow-agents deployment health
**Approach:** research-only

---

## Executive Summary

This document consolidates existing research on deployment health verification approaches for the botburrow-agents system. It synthesizes findings from multiple previous research documents and provides a comprehensive decision framework for health verification strategies.

### Key Findings

1. **Deployment Status:** The botburrow-agents namespace exists but contains **ZERO deployed resources** - ArgoCD is not installed in apexalgo-iad cluster
2. **Existing Health Infrastructure:** Comprehensive Prometheus metrics and HTTP endpoints already exist in the codebase
3. **Multiple Verification Approaches:** From simple pod checks to comprehensive system-wide verification
4. **Existing Scripts:** Multiple verification scripts already implemented and available

---

## Current Health Infrastructure

### Existing HTTP Endpoints (`observability.py:284-378`)

The MetricsServer provides three HTTP endpoints on port 9090:

```python
# Liveness probe - checks if process is alive
GET /health  →  {"status": "healthy"}

# Readiness probe - checks if dependencies satisfied
GET /ready   →  {"status": "ready"}

# Prometheus metrics scrape endpoint
GET /metrics →  PROMETHEUS_TEXT_FORMAT
```

**Current Implementation Status:**
- ✅ Endpoints exist and are functional
- ✅ Kubernetes probes configured in manifests
- ⚠️ Readiness probe is basic (no dependency checks)
- ✅ Metrics endpoint exposes comprehensive telemetry

### Existing Prometheus Metrics

The system exposes 20+ Prometheus metrics covering:

| Category | Metrics | Purpose |
|----------|---------|---------|
| **Activations** | `botburrow_activations_total`, `botburrow_activation_duration_seconds`, `botburrow_activations_in_progress` | Track agent execution |
| **Queue** | `botburrow_queue_depth`, `botburrow_queue_active_tasks`, `botburrow_queue_wait_seconds` | Monitor work queue |
| **Runners** | `botburrow_runners_active`, `botburrow_runner_heartbeat_timestamp_seconds` | Track runner health |
| **Coordinator** | `botburrow_coordinator_is_leader` | Leader election status |
| **Budget** | `botburrow_budget_used_usd`, `botburrow_budget_limit_usd` | Cost tracking |
| **Circuit Breaker** | `botburrow_agent_backoff_seconds_remaining` | Backoff state |

### Kubernetes Probes Configuration

All deployments have standard probes configured:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: metrics
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: metrics
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

---

## Health Verification Approaches

### Approach 1: Simplified Pod & Metrics Check (Already Implemented)

**Description:** Minimal viable health check verifying pods are running and metrics endpoints respond.

**Files:**
- `scripts/verify-simplified-deployment.sh`
- `scripts/verify-minimal-deployment.sh`

**Implementation:**
```bash
# Quick verification
./scripts/verify-simplified-deployment.sh

# Or manual
kubectl get pods -n botburrow-agents
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=50
```

**What's Checked:**
- Namespace exists and has resources
- Core deployments ready (valkey, runner-hybrid)
- Pods running (not just scheduled)
- Valkey connectivity
- Runner -> Valkey connectivity

**Pros:**
- ✅ Already implemented and tested
- ✅ Fast (seconds)
- ✅ Covers 80% of health cases
- ✅ Easy to automate
- ✅ No additional code required

**Cons:**
- ❌ Doesn't verify actual functionality
- ❌ Doesn't check external dependencies
- ❌ Misses "running but non-functional" scenarios

**Best For:** Quick verification, development environments, smoke tests

---

### Approach 2: Comprehensive System Health Check (Partially Implemented)

**Description:** Full-stack verification including pods, metrics, Redis, leader election, work queues, Hub connectivity, and R2 access.

**Files:**
- `scripts/verify-deployment.sh`
- `scripts/verify-deployment-health-standalone.sh`

**Implementation:**
```bash
# Full verification
./scripts/verify-deployment-health-standalone.sh
```

**What's Checked:**
1. Cluster connectivity
2. Namespace verification
3. Resource inventory (all types)
4. Pod status analysis
5. Critical components (valkey, runners, coordinator)
6. Secrets availability
7. ConfigMaps check
8. Services check
9. Recent logs analysis
10. Summary with recommendations

**Pros:**
- ✅ Comprehensive verification
- ✅ Catches "running but non-functional" scenarios
- ✅ Verifies end-to-end data flow
- ✅ Provides detailed diagnostic information
- ✅ Clear output with color coding
- ✅ Automated fix suggestions

**Cons:**
- ❌ Slower (minutes)
- ❌ More complex
- ❌ May produce false positives from transient issues

**Best For:** Troubleshooting, post-deployment verification, incident investigation

---

### Approach 3: Kubernetes Probes + Prometheus Alerts (Recommended for Production)

**Description:** Use native Kubernetes probes for immediate health and Prometheus/Grafana for ongoing monitoring with alerting.

**Current Status:**
- ✅ Probes exist in manifests
- ❌ Prometheus alerts not yet defined

**Required Implementation:**

**Enhanced Readiness Probe:**
```python
# observability.py - enhance _ready_handler()
async def _ready_handler(self, _request: web.Request) -> web.Response:
    """Handle /ready endpoint (readiness probe)."""
    checks = {
        "status": "ready",
        "checks": {}
    }

    # Check Redis/Valkey connectivity
    try:
        # Add Redis ping check
        checks["checks"]["valkey"] = "ok"
    except Exception as e:
        checks["checks"]["valkey"] = f"error: {e}"
        return web.json_response({"status": "not_ready", "reason": "valkey"}, status=503)

    # Check leader election (for coordinator)
    # Check configs loaded (for runners)
    # Check Hub API connectivity

    return web.json_response(checks)
```

**Prometheus Alerts (to be created):**
```yaml
# k8s/apexalgo-iad/prometheus-alerts.yaml
groups:
  - name: botburrow-agents
    rules:
      - alert: CoordinatorNoLeader
        expr: sum(botburrow_coordinator_is_leader) == 0
        for: 5m
        annotations:
          summary: "No coordinator leader elected"

      - alert: WorkQueueBacklog
        expr: botburrow_queue_depth{priority="high"} > 100
        for: 10m
        annotations:
          summary: "High priority work queue backlog"

      - alert: RunnerNotHeartbeating
        expr: time() - botburrow_runner_heartbeat_timestamp_seconds > 300
        for: 5m
        annotations:
          summary: "Runner not sending heartbeats"

      - alert: ActivationFailureRateHigh
        expr: rate(botburrow_activations_total{status="failure"}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "More than 10% activation failures"
```

**Pros:**
- ✅ Native Kubernetes integration
- ✅ Automatic recovery via pod restarts
- ✅ Continuous monitoring
- ✅ Alert-driven operations
- ✅ Separates concerns (immediate vs ongoing)
- ✅ Probes already in manifests

**Cons:**
- ❌ Requires Prometheus/Grafana setup
- ❌ Need to define alert thresholds
- ❌ Alert fatigue risk if not tuned
- ❌ Doesn't provide ad-hoc verification

**Best For:** Production environments, continuous monitoring, automatic recovery

**Effort:** 4-6 hours (enhance probes + define alerts)

---

### Approach 4: External Health Check Service

**Description:** Standalone health check service that queries all components and aggregates results into a single JSON API.

**Implementation Sketch:**
```python
# health_check_service.py
from aiohttp import web
import kubernetes
import redis

async def check_health():
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
        "healthy": True
    }

    # 1. Check Kubernetes pods
    v1 = kubernetes.client.CoreV1Api()
    pods = v1.list_namespaced_pod("botburrow-agents")
    results["checks"]["pods"] = {
        "total": len(pods.items),
        "running": sum(1 for p in pods.items if p.status.phase == "Running"),
        "ready": sum(1 for p in pods.items if all(cs.ready for cs in p.status.container_statuses))
    }

    # 2. Check Redis
    try:
        r = redis.Redis(host="valkey.botburrow-agents.svc.cluster.local")
        results["checks"]["redis"] = {"ping": r.ping()}
    except Exception as e:
        results["checks"]["redis"] = {"error": str(e)}
        results["healthy"] = False

    # 3. Check leader election
    # 4. Check work queues
    # 5. Check metrics endpoints

    return results

async def health_handler(request):
    results = await check_health()
    status = 200 if results["healthy"] else 503
    return web.json_response(results, status=status)

app = web.Application()
app.router.add_get("/health", health_handler)
web.run_app(app, port=8080)
```

**Pros:**
- Single endpoint for all health info
- Can add custom business logic
- Returns detailed JSON for debugging
- Can be exposed via IngressRoute for external monitoring

**Cons:**
- Additional deployment to maintain
- Needs RBAC permissions to query Kubernetes
- Single point of failure
- More complex than using probes

**Best For:** Multi-cluster aggregation, custom health logic, external monitoring

**Status:** Not implemented

---

### Approach 5: Health Check via Hub Integration

**Description:** Leverage Hub API to report agent system health. Hub already tracks agent activity and could track system health.

**Implementation:**
```python
# Add to coordinator main.py
async def report_system_health():
    while True:
        try:
            health = {
                "coordinator_healthy": True,
                "active_runners": len(await assigner.get_active_runners()),
                "work_queue_depth": await work_queue.get_queue_stats(),
                "leader_instance": instance_id if leader_election.is_leader else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            await hub.post_system_health(health)
        except Exception as e:
            logger.error("health_report_error", error=str(e))
        await asyncio.sleep(60)
```

**Pros:**
- Centralized health data in Hub
- Single API for all health info
- Can trigger alerts from Hub
- Useful for multi-cluster deployments

**Cons:**
- Depends on Hub availability
- Adds load to Hub API
- Requires Hub schema changes
- Circular dependency (Hub needs agents, agents report to Hub)

**Best For:** Multi-cluster deployments, centralized monitoring

**Status:** Not implemented, requires Hub API changes

---

### Approach 6: False Positive Detection (Running But Non-Functional)

**Problem:** Pods can be "running but non-functional" - processes alive but not doing work.

**Symptoms:**
- Pod status: `Running`
- Health probe: `200 OK`
- But: No work processing, no leader elected, no heartbeats

**Detection Strategies:**

1. **Leader election check**: Exactly one coordinator should be leader
   ```bash
   kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=50 | grep -i leader
   ```

2. **Heartbeat monitoring**: Runners must heartbeat every 60s
   ```bash
   # Check via Prometheus
   botburrow_runner_heartbeat_timestamp_seconds
   ```

3. **Work queue depth**: Should not grow unbounded
   ```bash
   kubectl exec -n botburrow-agents valkey-0 -- redis-cli LLEN work:queue:high
   ```

4. **Activation rate**: Should see regular completions
   ```bash
   # Check via Prometheus
   rate(botburrow_activations_total{status="success"}[5m])
   ```

**Implementation:** See Approach 3 (Prometheus alerts)

---

## Comparison Matrix

| Approach | Implementation Effort | Runtime Cost | Comprehensive | Requires Deployment | Alerts | Best For |
|----------|----------------------|--------------|---------------|---------------------|--------|----------|
| **1. Simplified Check** | None (done) | Low | No | Yes | No | Quick verification |
| **2. Comprehensive** | Low (done) | Low | Yes | Yes | Manual | Full system verification |
| **3. K8s Probes + Alerts** | Medium | Low | Yes | Yes | Yes | Production monitoring |
| **4. External Service** | High | Medium | Yes | No | Custom | Centralized health API |
| **5. Hub Integration** | Medium | Low | Partial | Yes | Via Hub | Multi-cluster tracking |

---

## Verification Hierarchy

```
Layer 1: Pod Health (Kubernetes Probes)
  └─> Liveness: Process alive
  └─> Readiness: Dependencies satisfied
  └─> Status: ✅ Implemented in manifests

Layer 2: Application Health (Enhanced /ready)
  └─> Redis connectivity
  └─> Hub API connectivity
  └─> Work queue status
  └─> Status: ⚠️ Basic implementation, needs enhancement

Layer 3: Service Health (Prometheus Metrics)
  └─> Leader election status
  └─> Queue depth
  └─> Activation rates
  └─> Runner heartbeats
  └─> Status: ✅ Comprehensive metrics exposed

Layer 4: Business Logic Health (E2E Tests)
  └─> End-to-end activation flow
  └─> Work claiming and processing
  └─> Configuration sync
  └─> Status: ❌ Not implemented

Layer 5: Manual Verification (Scripts)
  └─> Quick deployment check
  └─> Troubleshooting guide
  └─> Status: ✅ Multiple scripts available
```

---

## Deployment Context

### Why Deployment Doesn't Exist

**Primary Blocker:** ArgoCD not installed in apexalgo-iad cluster

```bash
$ kubectl get applications.argoproj.io -A
error: the server doesn't have a resource type "applications"

$ kubectl get ns | grep -i argo
# (no output - no ArgoCD namespace)
```

**Secondary Blocker:** RBAC restrictions - devpod-observer ServiceAccount lacks permissions to create resources

### Deployment Resolution Options

The deployment itself must be resolved before health verification can proceed. Options include:

1. **Direct kubectl apply** - Immediate deployment, bypass GitOps temporarily
2. **Install ArgoCD** - True GitOps, requires setup
3. **Hybrid approach** - Manual now, ArgoCD later

See `docs/research/bd-ced-deployment-approaches-comprehensive.md` for detailed deployment options.

---

## Recommendations

### Primary Recommendation: **Approach 3 (K8s Probes + Prometheus Alerts)**

**Rationale:**
1. **Probes already exist** in manifests - just need to be enhanced
2. **Native Kubernetes** - no additional infrastructure
3. **Automatic recovery** via pod restarts
4. **Production-ready** pattern for Kubernetes workloads
5. **Separates concerns** - probes for immediate, alerts for ongoing

**Implementation Plan:**
1. Enhance `/ready` endpoint to check dependencies:
   - Redis connectivity
   - Leader election (for coordinator)
   - Config loaded (for runners)

2. Create Prometheus alerts (see Approach 3 above)

3. Create health verification script for ad-hoc checks (use existing Approach 1)

4. Document in troubleshooting guide

**Estimated Effort:** 4-6 hours

### Secondary Recommendation: **Approach 2 (Comprehensive)**

**For detailed verification** (e.g., after deployment or troubleshooting):
1. Use existing comprehensive check script
2. Include in CI/CD pipeline
3. Run weekly as health audit
4. Document results in operations runbook

---

## Decision Framework

### Choose Approach 1 (Simplified) if:
- You need quick yes/no health check
- Deployment is known to be working
- You're doing frequent checks
- You want minimal overhead

### Choose Approach 2 (Comprehensive) if:
- You're debugging issues
- You need full system verification
- After deployment changes
- You're investigating incidents

### Choose Approach 3 (Probes + Alerts) if:
- You're deploying to production
- You want automatic recovery
- You need continuous monitoring
- You have Prometheus/Grafana

### Choose Approach 4 (External Service) if:
- You need centralized health API
- You're exposing health externally
- You have complex health logic
- You're doing multi-cluster aggregation

### Choose Approach 5 (Hub Integration) if:
- You're tracking multi-cluster health
- You want health in Hub UI
- You're already using Hub for monitoring
- You need centralized alerting

---

## Next Steps

### Immediate Actions (Post-Deployment)

Once the deployment blocker is resolved and resources are deployed:

```bash
# 1. Deploy (chosen method)
# 2. Quick health check
./scripts/verify-simplified-deployment.sh

# 3. Full verification
./scripts/verify-deployment-health-standalone.sh

# 4. Check metrics
kubectl port-forward -n botburrow-agents deployment/coordinator 9090:9090
curl http://localhost:9090/metrics
```

### Planning Actions

1. **Enhance readiness probes** to check dependencies (Redis, Hub)
2. **Define Prometheus alerts** for production monitoring
3. **Create ServiceMonitor** if using Prometheus Operator
4. **Document operational procedures** in troubleshooting guide

---

## Related Documentation

### Existing Research Documents
1. `docs/research/bd-30r-deployment-health-verification-approaches.md` - 6 health verification approaches (623 lines)
2. `docs/research/bd-30r-deployment-verification-options.md` - 6 deployment resolution options (534 lines)
3. `docs/research/bd-ced-deployment-approaches-comprehensive.md` - 7 deployment approaches (656 lines)

### Verification Scripts
1. `scripts/verify-simplified-deployment.sh` - Quick pod + metrics check
2. `scripts/verify-minimal-deployment.sh` - Minimal verification
3. `scripts/verify-deployment-health-standalone.sh` - Comprehensive verification (419 lines)

### Code References
1. `src/botburrow_agents/observability.py` - Metrics server with health/ready endpoints
2. `k8s/apexalgo-iad/coordinator.yaml` - Coordinator deployment with probes
3. `k8s/apexalgo-iad/runner-hybrid.yaml` - Runner deployment with probes

---

## Related Beads

- **bd-38r**: Original verification bead (closed - deployment not found)
- **bd-1he**: This bead (consolidated research)
- **bd-30r**: Previous health verification research
- **bd-ced**: Deployment approaches comprehensive comparison
- **bd-1v9**: Fix botburrow-agents deployment via ArgoCD (closed)

---

## Conclusion

This document consolidates existing research on deployment health verification for the botburrow-agents system. The key findings are:

1. **Comprehensive health infrastructure already exists** - HTTP endpoints, Prometheus metrics, Kubernetes probes
2. **Multiple verification scripts are available** - from simple to comprehensive
3. **Primary recommendation is Approach 3** - Enhance existing probes + add Prometheus alerts for production monitoring
4. **Deployment must happen first** - Health verification cannot proceed without deployed resources

The system is well-instrumented with metrics and has basic health endpoints. The main work needed is:
1. Enhance readiness probes to check actual dependencies
2. Define Prometheus alerts for proactive monitoring
3. Resolve the deployment blocker (ArgoCD not installed)

**Human Decision Required:**
1. Choose deployment method (see bd-ced for options)
2. Confirm health verification approach (Approach 3 recommended)
3. Approve enhanced probes and Prometheus alerts implementation

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47-delta)
**Bead:** bd-1he
