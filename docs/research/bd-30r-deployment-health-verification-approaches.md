# BD-30R: Botburrow-Agents Deployment Health Verification - Approach Comparison

**Status:** Research Document
**Date:** 2026-02-08
**Original Bead:** bd-38r (Verify botburrow-agents deployment health)
**Alternative Bead:** bd-30r (Alternative: Research and document options)

---

## Executive Summary

This document provides a detailed comparison of possible approaches for verifying botburrow-agents deployment health in the apexalgo-iad cluster. **Key Finding:** The deployment is currently **not deployed** (namespace exists but has zero resources) due to missing ArgoCD and lack of cluster-admin access for direct deployment.

This research documents multiple health verification approaches to inform human decision on how to proceed once the deployment blocker is resolved.

---

## Context: Current Deployment State

### Current Situation (from bd-38r verification report)

1. **Namespace Status**: `botburrow-agents` namespace exists but is **EMPTY**
   - 0 pods
   - 0 deployments
   - 0 services
   - Only tracking-id annotations from non-existent ArgoCD

2. **Root Cause**: ArgoCD is **NOT installed** in apexalgo-iad cluster
   - Kustomization has `app.kubernetes.io/managed-by: argocd` labels
   - No ArgoCD controller exists to sync resources
   - No alternative GitOps solution configured

3. **Secondary Blocker**: RBAC restrictions
   - `devpod-observer` ServiceAccount lacks permissions to create resources
   - Cannot deploy directly via kubectl without cluster-admin credentials

### Expected Architecture (when deployed)

```
apexalgo-iad Cluster (botburrow-agents namespace)
├── coordinator (2 replicas, leader-elected)
│   └── /health, /ready, /metrics endpoints
├── runner-hybrid (2 replicas, HPA scaling)
│   └── /health, /ready, /metrics endpoints
├── runner-notification (2-3 replicas, HPA scaling)
│   └── /health, /ready, /metrics endpoints
├── runner-exploration (1-2 replicas, HPA scaling)
│   └── /health, /ready, /metrics endpoints
├── valkey (StatefulSet, 1 replica)
│   └── Redis/Valkey for coordination
├── skill-sync (Deployment, optional)
│   └── Syncs skills from ClawHub to R2
└── ConfigMaps, Secrets, RBAC, ServiceMonitor
```

---

## Problem Statement

**bd-38r** ("Verify botburrow-agents deployment health") was assigned to verify the deployment is healthy, but:
1. Deployment doesn't exist (no pods running)
2. Cannot verify health of non-existent resources
3. Worker got stuck - what should it do next?

**This research bead (bd-30r)** explores options for:
1. How to verify deployment health once deployed
2. How to handle the "no deployment" scenario
3. What a comprehensive health verification looks like for distributed agent systems

---

## Health Verification Approaches

### Approach 1: Simplified Pod & Metrics Check

**Description:** Minimal viable health check verifying only that pods are running and metrics endpoints respond.

**Implementation:**
```bash
# Check pod status
kubectl get pods -n botburrow-agents

# Verify metrics endpoint accessible
kubectl get pods -n botburrow-agents -o json | \
  jq -r '.items[].metadata.name' | \
  xargs -I {} kubectl exec {} -n botburrow-agents -- \
    curl -s http://localhost:9090/metrics | head -20
```

**Pros:**
- Simple and fast (seconds)
- Covers 80% of health cases
- Easy to automate
- Works with existing `/health` and `/ready` endpoints
- Already implemented as tests (bd-1mg workaround)

**Cons:**
- Doesn't verify actual functionality
- Pods could be "running but non-functional"
- Doesn't check Redis connectivity
- Doesn't verify leader election
- Doesn't check external dependencies (Hub, R2)

**Code Reference:** `tests/test_simplified_health_check.py`

**Status:** Already implemented (bd-1mg, bd-335)

---

### Approach 2: Comprehensive System Health Check

**Description:** Full-stack verification including pods, metrics, Redis, leader election, work queues, Hub connectivity, and R2 access.

**Implementation:**
```bash
# 1. Check pod status
kubectl get pods -n botburrow-agents

# 2. Verify metrics endpoints
for pod in $(kubectl get pods -n botburrow-agents -o jsonpath='{.items[*].metadata.name}'); do
  echo "Checking $pod metrics..."
  kubectl exec $pod -n botburrow-agents -- curl -s http://localhost:9090/metrics
done

# 3. Check Redis/Valkey connectivity
VALKEY_POD=$(kubectl get pods -n botburrow-agents -l app=valkey -o jsonpath='{.items[0].metadata.name}')
kubectl exec $VALKEY_POD -n botburrow-agents -- redis-cli PING

# 4. Verify leader election
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=50 | grep -i leader

# 5. Check work queues
kubectl exec $VALKEY_POD -n botburrow-agents -- redis-cli LLEN work:queue:high
kubectl exec $VALKEY_POD -n botburrow-agents -- redis-cli HGETALL work:active

# 6. Test Hub API connectivity
kubectl exec -n botburrow-agents deployment/coordinator -- \
  curl -s $HUB_URL/api/v1/system/health

# 7. Verify R2 connectivity
kubectl exec -n botburrow-agents deployment/coordinator -- \
  aws s3 ls s3://$R2_BUCKET --endpoint-url=$R2_ENDPOINT

# 8. Check agent configs loaded
kubectl exec -n botburrow-agents deployment/runner-hybrid -- \
  ls -la /configs/agent-definitions/
```

**Pros:**
- Comprehensive verification
- Catches "running but non-functional" scenarios
- Verifies end-to-end data flow
- Tests external dependencies
- Provides detailed diagnostic information

**Cons:**
- Complex (many failure points)
- Slower (minutes)
- Requires secrets to be deployed first
- More maintenance burden
- May produce false positives from transient issues

**Code Reference:** `tests/test_monitoring_verification.py`

**Status:** Partially implemented (bd-38r was blocked before completion)

---

### Approach 3: Kubernetes Probes + Prometheus Alerts

**Description:** Use native Kubernetes probes for immediate health and Prometheus/Grafana for ongoing monitoring.

**Implementation:**

**Kubernetes Probes (already in manifests):**
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

**Prometheus Alerts (to be created):**
```yaml
groups:
  - name: botburrow-agents
    rules:
      - alert: CoordinatorNotLeader
        expr: botburrow_coordinator_is_leader == 0
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
- Native Kubernetes integration
- Automatic recovery via pod restarts
- Continuous monitoring
- Alert-driven operations
- Separates concerns (immediate vs ongoing)
- Already has probes in manifests

**Cons:**
- Requires Prometheus/Grafana setup
- Need to define alert thresholds
- Alert fatigue if not tuned properly
- Doesn't provide ad-hoc verification

**Status:** Probes exist in manifests, alerts not yet defined

---

### Approach 4: External Health Check Service

**Description:** Standalone health check service that queries all components and aggregates results.

**Implementation:**
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
    try:
        leader_key = r.get("coordinator:leader")
        results["checks"]["leader"] = {"leader": leader_key.decode()}
    except Exception as e:
        results["checks"]["leader"] = {"error": str(e)}

    # 4. Check work queues
    try:
        results["checks"]["queues"] = {
            "high": r.llen("work:queue:high"),
            "normal": r.llen("work:queue:normal"),
            "low": r.llen("work:queue:low")
        }
    except Exception as e:
        results["checks"]["queues"] = {"error": str(e)}

    # 5. Check metrics endpoints
    for pod in pods.items:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://{pod.status.pod_ip}:9090/metrics") as resp:
                    results["checks"][f"metrics_{pod.metadata.name}"] = resp.status == 200
        except:
            results["checks"][f"metrics_{pod.metadata.name}"] = False

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
- Independent of application pods

**Cons:**
- Additional deployment to maintain
- Needs RBAC permissions to query Kubernetes
- Single point of failure for health checks
- More complex than using probes

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
- Leverages existing Hub infrastructure

**Cons:**
- Depends on Hub availability
- Adds load to Hub API
- Requires Hub schema changes
- Circular dependency (Hub needs agents, agents report to Hub)

**Status:** Not implemented, would require Hub API changes

---

### Approach 6: No Deployment - Accept Current State

**Description:** Acknowledge deployment doesn't exist, document why, and close beads until deployment happens.

**Implementation:**
1. Close bd-38r with "Deployment not found - cannot verify"
2. Create human bead for deployment decision
3. Document blockers in project README
4. No verification code written

**Pros:**
- Minimal effort
- Honest assessment of current state
- Prevents wasted work on non-existent deployment
- Forces decision on deployment approach

**Cons:**
- No health verification capability
- Doesn't solve underlying problem
- Leaves beads open indefinitely
- Doesn't advance the project

**Status:** Proposed (what worker should do when stuck)

---

## Comparison Matrix

| Approach | Implementation Effort | Runtime Cost | Comprehensive | Requires Deployment | Alerts | Best For |
|----------|----------------------|--------------|---------------|---------------------|--------|----------|
| 1. Simplified Check | Low (done) | Low | No | Yes | No | Quick verification |
| 2. Comprehensive | High | Low | Yes | Yes | Manual | Full system verification |
| 3. K8s Probes + Alerts | Medium | Low | Yes | Yes | Yes | Production monitoring |
| 4. External Service | High | Medium | Yes | No | Custom | Centralized health API |
| 5. Hub Integration | Medium | Low | Partial | Yes | Via Hub | Multi-cluster tracking |
| 6. Accept No Deployment | Very Low | None | N/A | No | No | Current state |

---

## Technical Details

### Existing Health Infrastructure

**Current Endpoints (observability.py:284-378):**
```python
class MetricsServer:
    async def _health_handler(self, _request: web.Request) -> web.Response:
        """Handle /health endpoint (liveness probe)."""
        return web.json_response({"status": "healthy"})

    async def _ready_handler(self, _request: web.Request) -> web.Response:
        """Handle /ready endpoint (readiness probe)."""
        return web.json_response({"status": "ready"})
```

**Existing Metrics:**
- `botburrow_coordinator_is_leader` - Leader election status
- `botburrow_queue_depth` - Work queue depth by priority
- `botburrow_activations_total` - Activation counter with status label
- `botburrow_runner_heartbeat_timestamp_seconds` - Runner heartbeat
- `botburrow_activations_in_progress` - Currently running activations

### False Positive Detection

**Problem:** Pods can be "running but non-functional" - processes alive but not doing work.

**Symptoms:**
- Pod status: `Running`
- Health probe: `200 OK`
- But: No work processing, no leader elected, no heartbeats

**Detection Strategies:**
1. **Leader election check**: Exactly one coordinator should be leader
2. **Heartbeat monitoring**: Runners must heartbeat every 60s
3. **Work queue depth**: Should not grow unbounded
4. **Activation rate**: Should see regular completions

**From verification-report-bd-38r.md:**
> "Healthy but non-functional" Kubernetes pods where only HTTP health endpoints work but actual system is broken.

---

## Deployment Blocker Analysis

### Why Deployment Doesn't Exist

**Primary Blocker:** ArgoCD not installed in apexalgo-iad

Evidence from verification report:
```bash
$ kubectl get applications.argoproj.io -A
error: the server doesn't have a resource type "applications"

$ kubectl get ns | grep -i argo
# (no output - no ArgoCD namespace)
```

**Secondary Blocker:** RBAC restrictions

```bash
Error: User "system:serviceaccount:devpod-observer:devpod-observer" \
  cannot create resource "deployments" in API group "apps" \
  in the namespace "botburrow-agents"
```

### Resolution Options

**Option A: Install ArgoCD in apexalgo-iad**
1. Install ArgoCD: `kubectl create namespace argocd && kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml`
2. Create ApplicationSet for botburrow-agents
3. Configure sync from git repo

**Option B: Direct kubectl apply**
1. Get cluster-admin credentials
2. Apply: `kubectl apply -k k8s/apexalgo-iad/`
3. Manage updates manually

**Option C: Alternative GitOps**
1. Check if Flux is installed
2. Configure botburrow-agents for Flux
3. Or use GitHub Actions deployment

---

## Recommended Approach

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
3. Create health verification script for ad-hoc checks (Approach 1)
4. Document in troubleshooting guide

**Estimated Effort:** 4-6 hours

### Secondary Recommendation: **Approach 2 (Comprehensive)**

**For detailed verification** (e.g., after deployment or troubleshooting):
1. Use comprehensive check script
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

### Choose Approach 6 (Accept No Deployment) if:
- Deployment doesn't exist (current state)
- You need human decision on deployment approach
- You want to pause verification until deployed

---

## Next Steps

**Human Decision Required:**

1. **Which deployment method?**
   - Install ArgoCD in apexalgo-iad?
   - Direct kubectl with cluster-admin?
   - Alternative GitOps solution?

2. **Which health verification approach?**
   - Approach 1: Simplified (already implemented)
   - Approach 2: Comprehensive (partial)
   - Approach 3: Probes + Alerts (recommended)
   - Approach 4: External service
   - Approach 5: Hub integration

3. **How to resolve deployment blocker?**
   - Human bead for ArgoCD installation?
   - Human bead for cluster-admin kubectl apply?
   - Close all verification beads until deployed?

**To proceed:**
1. Review this document
2. Choose deployment method (A, B, or C)
3. Choose verification approach (1-5)
4. Create follow-up beads or provide direction
5. Close bd-30r as completed (research done)

---

## Related Files

- `verification-report-bd-38r.md` - Current deployment verification findings
- `tests/test_simplified_health_check.py` - Simplified health check implementation
- `tests/test_monitoring_verification.py` - Comprehensive verification tests
- `src/botburrow_agents/observability.py` - Metrics server with health/ready endpoints
- `k8s/apexalgo-iad/coordinator.yaml` - Coordinator deployment with probes
- `k8s/apexalgo-iad/runner-hybrid.yaml` - Runner deployment with probes
- `docs/deployment/deployment.md` - Deployment guide

## Related Beads

- **bd-38r**: Original verification bead (blocked by no deployment)
- **bd-30r**: This bead (research alternative)
- **bd-3l1**: Create ArgoCD Application for botburrow-agents
- **bd-2f8**: Fix botburrow-agents deployment issues (depends on bd-38r)
- **bd-1mg**: Simplified health check implementation (completed)

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47-bravo)
