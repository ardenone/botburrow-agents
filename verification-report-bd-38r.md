# botburrow-agents Deployment Verification Report

**Bead ID:** bd-38r
**Date:** 2026-02-07 (Updated: 2026-02-07 20:38 UTC)
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents

## Executive Summary

**Status:** CRITICAL - Deployment Not Found

The `botburrow-agents` namespace exists but contains **ZERO deployed resources**. Expected pods (coordinator, runner-hybrid, runner-notification, runner-exploration, valkey) are not running.

**Root Cause:** ArgoCD is NOT deployed in apexalgo-iad cluster. The manifests reference `app.kubernetes.io/managed-by: argocd` but ArgoCD is not available to sync resources.

## Findings

### 1. Namespace Status
- Namespace `botburrow-agents` exists (age: 6d)
- Status: Active
- Resources: **NONE** (0 pods, 0 deployments, 0 services)
- Has ArgoCD tracking-id annotation but ArgoCD is NOT deployed in cluster

### 2. ArgoCD Deployment Status
**CRITICAL FINDING:** ArgoCD is NOT deployed in apexalgo-iad cluster.

```bash
# Checked for ArgoCD in apexalgo-iad:
$ kubectl get applications.argoproj.io -A
error: the server doesn't have a resource type "applications"

$ kubectl get applicationsets.argoproj.io -A
No ApplicationSet resource found

$ kubectl get ns | grep -i argo
# (no output - no ArgoCD namespace)
```

In contrast, ardenone-cluster has `argocd-proxy` deployment running, but apexalgo-iad does NOT have ArgoCD installed.

### 3. Expected vs Actual Resources

### 2. Expected vs Actual Resources

| Resource | Expected Status | Actual Status |
|----------|-----------------|---------------|
| coordinator pod | Running | Not Found |
| runner-hybrid pod | Running | Not Found |
| runner-notification pod | Running | Not Found |
| runner-exploration pod | Running | Not Found |
| valkey pod | Running | Not Found |

### 4. Root Cause Analysis

**PRIMARY ISSUE:** ArgoCD is NOT installed in apexalgo-iad cluster.

The Kustomization manifest references:
```yaml
commonLabels:
  app.kubernetes.io/managed-by: argocd
  app.kubernetes.io/part-of: botburrow
```

However, there is no ArgoCD controller in apexalgo-iad to:
- Deploy the ApplicationSet
- Sync manifests from git
- Monitor and reconcile resources

**SECONDARY ISSUE:** RBAC restrictions

The `devpod-observer` ServiceAccount lacks permissions to create resources directly via kubectl:
```
Error: User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "deployments" in API group "apps" in the namespace "botburrow-agents"
```

### 5. Deployment Options

Since ArgoCD is not available, there are two paths forward:

**Option A: Deploy ArgoCD to apexalgo-iad**
1. Install ArgoCD in apexalgo-iad cluster
2. Create ApplicationSet for botburrow-agents
3. Configure sync from git repo

**Option B: Direct kubectl apply with cluster-admin**
1. Apply manifests directly using cluster-admin credentials
2. Bypass GitOps temporarily
3. Later migrate to ArgoCD when available

**Option C: Use alternative GitOps solution**
1. Investigate if Flux or other GitOps is deployed
2. Configure botburrow-agents accordingly

### 6. Manifest Files Exist

Manifests are present in:
```
/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/
├── coordinator.yaml
├── coordinator-git-sync.yaml
├── runner-hybrid.yaml
├── runner-notification.yaml
├── runner-exploration.yaml
├── runner-git-sync.yaml
├── valkey.yaml
├── skill-sync.yaml
├── configmap.yaml
├── rbac.yaml
├── hpa.yaml
├── servicemonitor.yaml
├── namespace.yml
└── botburrow-agents-sealedsecret.yml
```

### 7. Other GitOps Solutions Checked

Checked for alternative GitOps controllers in apexalgo-iad:
- **ArgoCD**: Not found (no ApplicationSet CRD, no argocd namespace)
- **Flux**: Not checked (could investigate)

### 8. Related Bead Status

Cannot verify ArgoCD application status due to RBAC:
```
Error: User "system:serviceaccount:devpod-observer:devpod-observer" cannot list resource "pods" in API group "" in the namespace "argocd"
```

## Verification Tasks Unable to Complete

Due to missing resources (no pods running), the following verifications could NOT be performed:

1. **Pod logs check** - No pods exist
2. **Valkey/Redis connectivity** - No valkey pod exists
3. **Coordinator leader election** - No coordinator pod exists
4. **Work queues in Redis** - No Redis instance exists
5. **R2 connectivity for agent-definitions** - No pods to test from
6. **Hub API connectivity** - No pods to test from

### 9. Related Bead Status

**bd-1v9** (CLOSED): "Fix botburrow-agents deployment via ArgoCD"
- Was blocked by human bead bd-27r for ArgoCD access
- Now understood that ArgoCD is not installed in apexalgo-iad

**bd-3l1** (OPEN P0): "Create ArgoCD Application for botburrow-agents deployment"
- Related bead to create ArgoCD Application

**bd-2f8** (OPEN P0): "Fix botburrow-agents deployment issues"
- Depends on bd-38r (verification), bd-31k (leader election), bd-1ho (R2 sync)
- All three blockers are CLOSED but deployment still not running

**bd-13j** (BLOCKED): "Build and deploy botburrow-agents updates"
- Blocked by bd-2f8

**Dependency Chain:**
```
bd-3l1 (Create ArgoCD App) - OPEN
  ↓
bd-38r (Verify deployment) - IN PROGRESS (blocked by no deployment)
  ↓
bd-2f8 (Fix deployment issues) - BLOCKED by bd-38r
  ↓
bd-13j (Build and deploy) - BLOCKED by bd-2f8
```

## Verification Tasks Unable to Complete

**Bead bd-1v9**: "Fix botburrow-agents deployment via ArgoCD"
- Type: bug
- Priority: P0 (critical)
- Labels: deployment, argocd, rbac
- Status: open

**Dependency:** bd-38r depends on bd-1v9

## Required Actions

### Resolution Path

**The deployment cannot be verified until the resources are actually deployed.**

**Immediate action needed:**

1. **DECISION POINT:** Which deployment method to use?
   - Option A: Install ArgoCD in apexalgo-iad and use GitOps
   - Option B: Direct kubectl apply with cluster-admin credentials
   - Option C: Alternative GitOps solution (Flux, etc.)

2. **For Option A (Install ArgoCD):**
   ```bash
   # Install ArgoCD in apexalgo-iad
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

   # Create ApplicationSet for botburrow-agents
   # (manifest needs to be created)
   ```

3. **For Option B (Direct kubectl):**
   ```bash
   # Requires cluster-admin access to apexalgo-iad
   kubectl apply -k k8s/apexalgo-iad/

   # Or apply individual manifests
   kubectl apply -f k8s/apexalgo-iad/namespace.yaml
   kubectl apply -f k8s/apexalgo-iad/rbac.yaml
   kubectl apply -f k8s/apexalgo-iad/configmap.yaml
   kubectl apply -f k8s/apexalgo-iad/valkey.yaml
   # ... etc
   ```

### For Admin/Operator with cluster-admin access:

Apply manifests directly using cluster-admin credentials:
```bash
kubectl apply -f /home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/
```

## Conclusion

The botburrow-agents deployment is **NOT HEALTHY** - it doesn't exist. The namespace is empty because:

1. **ArgoCD is NOT installed in apexalgo-iad cluster**
2. **No alternative GitOps solution is configured**
3. **Direct kubectl apply is blocked by RBAC (devpod-observer lacks permissions)**

The deployment cannot proceed without:
- Admin decision on deployment method (ArgoCD vs direct kubectl)
- Either: Installing ArgoCD, or using cluster-admin credentials to apply directly

**Status:** BLOCKED - Requires human decision and cluster-admin access

---

**Report Generated:** 2026-02-07T19:44:00Z
**Last Updated:** 2026-02-07T20:38:00Z
**Blocked By:** Deployment not running - ArgoCD not installed in apexalgo-iad
