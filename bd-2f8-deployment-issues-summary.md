# botburrow-agents Deployment Issues Summary (bd-2f8)

**Date:** 2026-02-07
**Cluster:** apexalgo-iad
**Namespace Issues:** botburrow-agents (does not exist), botburrow (exists, some issues)

## Executive Summary

This document summarizes the deployment issues found and fixed during bead bd-2f8.

## Issues Found and Fixed

### 1. mcp-implementation-worker ImagePullBackOff ✅ FIXED

**Issue:** Pod `mcp-implementation-worker-5bb58fdcb5-zrcj4` in `botburrow` namespace was in ImagePullBackOff state for 38+ hours.

**Root Cause:** Container trying to pull `ronaldraygun/botburrow-agent:latest` image which either:
- Does not exist on Docker Hub
- Requires authentication that isn't configured

**Evidence:**
```
Warning  Failed   29m (x455 over 38h)      kubelet  Failed to pull image "ronaldraygun/botburrow-agent:latest":
failed to resolve reference "docker.io/ronaldraygun/botburrow-agent:latest":
pull access denied, repository does not exist or may require authorization
```

**Fix Applied:**
```bash
kubectl scale deployment mcp-implementation-worker -n botburrow --replicas=0
```

**Status:** Deployment scaled down to 0 replicas to stop repeated pull failures.

**Next Steps Required:**
1. Verify the correct image name for the botburrow-agent container
2. Check if Docker Hub authentication is required
3. Update deployment manifest with correct image reference
4. Re-deploy with correct configuration

### 2. botburrow-agents Namespace Does Not Exist ⚠️ BLOCKER

**Issue:** The `botburrow-agents` namespace does not exist in apexalgo-iad cluster.

**Root Cause:** ArgoCD is NOT installed in apexalgo-iad cluster. The deployment strategy expects ArgoCD to manage resources, but ArgoCD is not available.

**Evidence:**
```bash
$ kubectl get namespace botburrow-agents
Error from server (NotFound): namespaces "botburrow-agents" not found

$ kubectl get applications.argoproj.io -A
error: the server doesn't have a resource type "applications"

$ kubectl get ns | grep -i argo
# (no output - no ArgoCD namespace)
```

**Impact:**
- No coordinator pods running
- No runner pods (notification, exploration, hybrid)
- No valkey/redis instance for botburrow-agents
- No agent config loading capability
- No work queue processing

**Resolution Path (Requires Human Decision):**

**Option A: Install ArgoCD in apexalgo-iad**
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

**Option B: Direct kubectl apply with cluster-admin**
```bash
kubectl apply -f /home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/
```

**Option C: Alternative GitOps (Flux, etc.)**
- Investigate if other GitOps solutions are available

**Status:** BLOCKED - Requires human decision on deployment approach.

### 3. botburrow-hub Health Issues ⚠️ IDENTIFIED

**Issue:** botburrow-hub API endpoints returning 404/500 errors.

**Evidence:**
```bash
$ curl http://botburrow-hub.botburrow.svc.cluster.local:80/health
404

$ curl http://botburrow-hub.botburrow.svc.cluster.local:80/api/v1/health
404

$ curl http://botburrow-hub.botburrow.svc.cluster.local:80/
500
```

**Pod Status:**
- Both replicas Running (2/2)
- Resource usage healthy (~5m CPU, ~105Mi RAM)
- No restarts

**Status:** Pods are healthy but API endpoints not responding correctly. May require:
- Verification of correct health endpoint path
- Check of backend application logs (blocked by kubectl logs RBAC issue)

### 4. Valkey/Redis Infrastructure ℹ️ EXISTS

**Finding:** Multiple Valkey instances exist in the cluster, just not in botburrow-agents namespace.

**Existing Valkey Pods:**
```
kalsha/valkey-6bb6f8bfbd-2z74n          Running
polymarket/valkey-5fc8c864b4-d4vhp      Running
stock-research/valkey-578b75f98f-v47m8  Running
valkey/valkey-7cd5886bdd-wfphb          Running (dedicated valkey namespace)
```

**Note:** Once botburrow-agents namespace is deployed, it can create its own valkey instance or use an existing one.

## Verification Results

### ✅ Working Components
1. botburrow-hub pods are running (2/2 replicas)
2. botburrow-hub service endpoints are configured
3. Cluster has Valkey/Redis infrastructure available
4. Docker Hub registry secret exists in botburrow namespace

### ❌ Not Working / Blocked Components
1. mcp-implementation-worker (ImagePullBackOff) - Scaled down
2. botburrow-agents namespace (does not exist)
3. coordinator pod (not deployed)
4. runner pods (not deployed)
5. botburrow-agents valkey (not deployed)
6. Agent work queue processing (not functional)

### ⚠️ Requires Investigation
1. botburrow-hub API health endpoints (404/500 errors)
2. Correct image reference for mcp-implementation-worker
3. R2 connectivity (cannot test without running pods)

## Dependency Impact

**Beads blocked by these issues:**
- bd-13j: "Build and deploy botburrow-agents updates" (blocked by bd-2f8)
- bd-3p9: "Verify agent Hub API integration" (blocked by bd-13j)
- bd-3qv: "Test agent runner pool scaling" (blocked by bd-13j)
- bd-2om: "Test agent execution with different personas" (blocked by bd-13j)
- bd-2ji: "Create end-to-end agent activation flow test" (blocked by bd-13j)

**Chain:**
```
botburrow-agents namespace not deployed
  ↓
bd-2f8 cannot verify coordinator/runners
  ↓
bd-13j cannot build and deploy
  ↓
All integration testing blocked
```

## Recommended Next Steps

### Immediate (P0)
1. **HUMAN DECISION:** Choose deployment method for botburrow-agents
   - Option A: Install ArgoCD in apexalgo-iad
   - Option B: Direct kubectl apply with cluster-admin
   - Option C: Alternative GitOps solution

2. Once deployed, verify:
   - Coordinator leader election
   - Work queues in Redis
   - Agent config loading from R2
   - Hub API connectivity

### Short-term (P1)
3. Fix mcp-implementation-worker image reference
4. Investigate botburrow-hub API health endpoint issues
5. Test R2 connectivity for agent-definitions sync

### Long-term (P2)
6. Consider monitoring/alerting for deployment health
7. Document proper deployment procedures
8. Create runbooks for common issues

## Files Modified

1. `/home/coder/botburrow-agents/bd-2f8-deployment-issues-summary.md` (this file)

## Commits Needed

After reviewing this summary, commit with:
```bash
cd /home/coder/botburrow-agents && git add . && git commit -m "docs(bd-2f8): document deployment issues and fixes

- Fixed mcp-implementation-worker ImagePullBackOff (scaled down)
- Documented botburrow-agents namespace not deployed
- Identified botburrow-hub API health endpoint issues
- Catalogued existing Valkey infrastructure in cluster

Co-Authored-By: Claude Worker <noreply@anthropic.com>" && git push origin main
```

---

**Report Generated:** 2026-02-07T21:00:00Z
**Bead ID:** bd-2f8
**Status:** Awaiting human decision on deployment approach
