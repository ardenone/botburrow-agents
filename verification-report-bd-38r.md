# botburrow-agents Deployment Verification Report

**Bead ID:** bd-38r
**Date:** 2026-02-07
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents

## Executive Summary

**Status:** CRITICAL - Deployment Not Found

The `botburrow-agents` namespace exists but contains **ZERO deployed resources**. Expected pods (coordinator, runner-hybrid, runner-notification, runner-exploration, valkey) are not running.

## Findings

### 1. Namespace Status
- Namespace `botburrow-agents` exists (age: 5d23h)
- Status: Active
- Resources: **NONE** (0 pods, 0 deployments, 0 services)

### 2. Expected vs Actual Resources

| Resource | Expected Status | Actual Status |
|----------|-----------------|---------------|
| coordinator pod | Running | Not Found |
| runner-hybrid pod | Running | Not Found |
| runner-notification pod | Running | Not Found |
| runner-exploration pod | Running | Not Found |
| valkey pod | Running | Not Found |

### 3. Root Cause: RBAC Blocking Deployment

**Attempted deployment via kubectl failed with Forbidden errors:**

```
Error: User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "deployments" in API group "apps" in the namespace "botburrow-agents"
Error: User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "sealedsecrets" in API group "bitnami.com" in the namespace "botburrow-agents"
Error: User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "configmaps" in the namespace "botburrow-agents"
```

The `devpod-observer` ServiceAccount used by the kubectl-proxy has **no permissions** to create resources in the `botburrow-agents` namespace.

### 4. Manifest Files Exist

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

### 5. ArgoCD Status Unknown

Cannot verify ArgoCD application status due to RBAC:
```
Error: User "system:serviceaccount:devpod-observer:devpod-observer" cannot list resource "pods" in API group "" in the namespace "argocd"
```

## Verification Tasks Unable to Complete

Due to missing resources, the following verifications could NOT be performed:

1. **Pod logs check** - No pods exist
2. **Valkey/Redis connectivity** - No valkey pod exists
3. **Coordinator leader election** - No coordinator pod exists
4. **Work queues in Redis** - No Redis instance exists
5. **R2 connectivity for agent-definitions** - No pods to test from
6. **Hub API connectivity** - No pods to test from

## Blocker Created

**Bead bd-1v9**: "Fix botburrow-agents deployment via ArgoCD"
- Type: bug
- Priority: P0 (critical)
- Labels: deployment, argocd, rbac
- Status: open

**Dependency:** bd-38r depends on bd-1v9

## Required Actions

### For Admin/Operator with cluster-admin access:

1. **Verify ArgoCD Application:**
   ```bash
   kubectl get applications.argoproj.io -A | grep botburrow
   kubectl get application botburrow-agents -n argocd -o yaml
   ```

2. **Check ArgoCD Sync Status:**
   ```bash
   kubectl get application botburrow-agents -n argocd -o jsonpath='{.status.sync.status}'
   ```

3. **If no ArgoCD app exists, create one** referencing:
   - Repo: git repo containing the manifests
   - Path: `cluster-configuration/apexalgo-iad/botburrow-agents/`
   - Destination: `https://kubernetes.default.svc` (apexalgo-iad)
   - Namespace: `botburrow-agents`

4. **Verify ArgoCD has permissions** to deploy to botburrow-agents namespace

### Temporary Workaround (if needed):

Apply manifests directly using cluster-admin credentials:
```bash
kubectl apply -f /home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/
```

## Conclusion

The botburrow-agents deployment is **NOT HEALTHY** - it doesn't exist. The namespace is empty due to what appears to be a missing or failed ArgoCD deployment. This requires admin intervention to resolve the ArgoCD configuration or apply manifests with appropriate permissions.

---

**Report Generated:** 2026-02-07T19:44:00Z
**Blocked By:** bd-1v9
