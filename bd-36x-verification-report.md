# ArgoCD Application Sync Verification Report (bd-36x)

**Date:** 2026-02-08
**Status:** BLOCKED - Requires human admin action
**Workspace:** /home/coder/botburrow-agents

## Summary

The ArgoCD ApplicationSet sync fix for botburrow-agents (bd-3kh) has been implemented with all root cause fixes committed to the ardenone-cluster repository. However, **verification is blocked** because the devpod-observer ServiceAccount lacks permissions to access the ArgoCD namespace to check Application sync status.

## What Was Fixed (bd-3kh)

All root cause fixes have been applied and pushed:

1. **botburrow-agents-application.yml removed** (commit e0fe28189)
   - Was being excluded by ApplicationSet pattern `*application.yml`
   - Prevented ApplicationSet from discovering the botburrow-agents directory

2. **kustomization.yaml removed** (commit be819f30e)
   - Incompatible with directory mode (Kustomization is not a K8s resource)

3. **ServiceMonitor disabled** (commit be819f30e)
   - ServiceMonitor CRD not installed in apexalgo-iad cluster

## Current State

### Git Repository
All changes committed and pushed to `ardenone-cluster` repository.

### Namespace Status (from bd-3kh summary)
- Namespace `botburrow-agents` exists
- Has ArgoCD tracking-id label: `botburrow-agents-ns-apexalgo-iad:/Namespace:/botburrow-agents`
- Namespace is empty (no resources deployed)

**Analysis:** The Application was created by ArgoCD but resources are not syncing.

## Why Verification is Blocked

### Access Attempt Results
The devpod-observer ServiceAccount has **NO access to check ArgoCD Application status** because:

1. **No argocd namespace RoleBinding** - devpod-observer only has bindings to:
   - devpod-observer namespace (self)
   - monitoring namespace (VictoriaLogs)

2. **Cannot check Application sync status** - Required commands are blocked by RBAC

## Related Human Beads

### bd-3cpp: Grant devpod-observer RBAC for botburrow-agents namespace
**Status:** OPEN (P0)
**Scope:** kubectl deployment access to `botburrow-agents` namespace
**Requested:** RoleBinding with admin role in `botburrow-agents` namespace

**Relationship to bd-36x:**
- **Different access requirements** - bd-3cpp is for kubectl deployment, bd-36x needs ArgoCD namespace access
- **Complementary** - Solving bd-3cpp enables workaround deployment, but ArgoCD verification still needs separate access

## Required Human Action

### Option 1: Grant devpod-observer ArgoCD read-only access (RECOMMENDED)
Create RoleBinding to allow Application status verification:

```bash
kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: devpod-observer-argocd-readonly
  namespace: argocd
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: view
subjects:
- kind: ServiceAccount
  name: devpod-observer
  namespace: devpod-observer
EOF
```

This enables:
- `kubectl get applications -n argocd` (verify Application exists)
- `kubectl get application <name> -n argocd` (check sync status)
- `argocd app get <name>` (view Application details)

### Option 2: Human admin verifies ArgoCD Application directly
As cluster-admin with full ArgoCD access:

```bash
# Check Application status
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o yaml

# Check sync status
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o jsonpath='{.status.sync.status}'

# Manual sync if needed
argocd app sync botburrow-agents-ns-apexalgo-iad

# Verify resources deployed
kubectl get all -n botburrow-agents
```

Report back the findings to update bead bd-36x.

### Option 3: Use workaround deployment (if ArgoCD cannot be fixed)
If ArgoCD has deeper issues:

```bash
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh
```

See `docs/workarounds/bd-cni-argocd-workaround.md` for details.

## Verification Steps (Once Access is Granted)

```bash
# 1. Check Application exists
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd

# 2. Check sync status
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o jsonpath='{.status.sync.status}'
# Expected: "Synced"

# 3. Check operation state
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o jsonpath='{.status.operationState.phase}'
# Expected: "Succeeded"

# 4. Verify resources deployed
kubectl get all -n botburrow-agents
# Expected: Deployments, Services, etc.

# 5. If OutOfSync, trigger manual sync
argocd app sync botburrow-agents-ns-apexalgo-iad
```

## Success Criteria

- [ ] ArgoCD Application status verified
- [ ] Sync status is "Synced" (or manual sync triggered if OutOfSync)
- [ ] Resources deployed to botburrow-agents namespace
- [ ] All pods running and healthy

## References

- bd-3kh fix summary: `/home/coder/botburrow-agents/bd-3kh-argocd-fix-summary.md`
- bd-3cpp (kubectl RBAC): Existing human bead for deployment access
- ApplicationSet: `ardenone-cluster/cluster-configuration/apexalgo-iad/apexalgo-iad-applicationset.yml`
- Manifests: `ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/`
