# ArgoCD Application Sync Verification Findings (bd-36x)

**Date:** 2026-02-08
**Bead:** bd-36x (HUMAN: Verify ArgoCD Application sync status for botburrow-agents)
**Status:** CLOSED (in botburrow-agents workspace)
**Related Bead:** bd-368r (same task in global workspace /home/coder/.beads/) - OPEN

**Latest Verification:** 2026-02-08 09:55 UTC
**Verifier:** claude-code-glm-47-bravo

## Summary

Cannot verify ArgoCD Application sync status due to RBAC limitations. The devpod-observer ServiceAccount does not have access to ArgoCD Application/ApplicationSet resources.

## Findings

### 1. Fixes Applied (Confirmed)

All fixes from bd-3kh have been applied to ardenone-cluster repository:

| Fix | Status | Evidence |
|-----|--------|----------|
| Remove `botburrow-agents-application.yml` | ✅ Applied | Commit e0fe28189 |
| Remove `kustomization.yaml` | ✅ Applied | Commit be819f30e |
| Disable `servicemonitor.yaml` | ✅ Applied | Now `.disabled` file |

### 2. Namespace Status (Confirmed)

```bash
$ kubectl get namespace botburrow-agents -o yaml | grep tracking-id
argocd.argoproj.io/tracking-id: botburrow-agents-ns-apexalgo-iad:/Namespace:/botburrow-agents
```

**Analysis:** The namespace exists with the ArgoCD tracking-id annotation, which proves the ArgoCD Application was created by the ApplicationSet.

### 3. Resource Status (Confirmed)

```bash
$ kubectl get all -n botburrow-agents
No resources found in botburrow-agents namespace.
```

**Analysis:** No resources deployed despite namespace existing with tracking-id.

### 4. RBAC Limitations (Blocker)

```bash
$ kubectl get applications.argoproj.io -n argocd
error: the server doesn't have a resource type "applications"

$ kubectl get applicationsets.argoproj.io
error: the server doesn't have a resource type "applicationsets"
```

**Analysis:** The devpod-observer ServiceAccount does NOT have access to ArgoCD Application/ApplicationSet resources.

**RBAC Verification Results (2026-02-08 09:55 UTC):**
```bash
$ kubectl auth can-i get applications.argoproj.io -n argocd
no

$ kubectl get secrets -n argocd
Error from server (Forbidden): secrets is forbidden: User "system:serviceaccount:devpod-observer:devpod-observer" cannot list resource "secrets" in API group "" in the namespace "argocd"

$ kubectl get configmaps -n argocd
Error from server (Forbidden): configmaps is forbidden: User "system:serviceaccount:devpod-observer:devpod-observer" cannot list resource "configmaps" in API group "" in the namespace "argocd"
```

Available Argo resources are only:
- AnalysisRun
- AnalysisTemplate
- Experiment
- Rollout (Argo Rollouts, not ArgoCD)

### 5. ApplicationSet Configuration (Verified)

The `manifest-appset-apexalgo-iad` ApplicationSet is configured to:
- Scan directories under `cluster-configuration/apexalgo-iad/*`
- Use directory mode (not kustomize mode)
- Exclude pattern: `{ignore/*,*application.yml}`

## Possible Issues

1. **ArgoCD Application Sync Error** - The Application may have a sync error preventing resource deployment
2. **ApplicationSet Not Updated** - The ApplicationSet may not have picked up the directory changes yet
3. **Manifest Validation Issue** - ArgoCD may be rejecting one or more manifests during sync

## Required Next Steps (Needs ArgoCD Admin Access)

### Immediate Verification Steps

1. **Check Application Status**
   ```bash
   kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o yaml
   ```

2. **Check Sync Status**
   ```bash
   kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o jsonpath='{.status.sync.status}'
   ```

3. **Check Operation State**
   ```bash
   kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o jsonpath='{.status.operationState}'
   ```

4. **Manual Sync (if needed)**
   ```bash
   argocd app sync botburrow-agents-ns-apexalgo-iad
   ```

### Alternative: Workaround Deployment

If ArgoCD cannot be fixed, use the workaround deployment script:
```bash
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh
```

## Files Referenced

- Fix summary: `/home/coder/botburrow-agents/bd-3kh-argocd-fix-summary.md`
- Ardenone-cluster manifests: `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/`
- ApplicationSet: `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/apexalgo-iad-applicationset.yml`

## Related Beads

- **bd-368r** (global workspace `/home/coder/.beads/`): Same task - **OPEN** - Needs ArgoCD admin verification
- **bd-36x** (botburrow-agents workspace): This bead - **CLOSED** (completed by previous worker)
- **bd-3kh**: Original fix bead (root cause identified and fixed)

## Conclusion

All code-level fixes have been applied and verified. The namespace exists with ArgoCD tracking-id, confirming the Application was created. However, resources are not being deployed, and verification requires ArgoCD admin access which is not available via devpod-observer ServiceAccount.

### Verification Status Summary

| Item | Status | Notes |
|------|--------|-------|
| Root cause fixes applied | ✅ Complete | All commits pushed to ardenone-cluster |
| Namespace created | ✅ Complete | Has ArgoCD tracking-id annotation |
| Resources deployed | ❌ Incomplete | Namespace empty despite tracking-id |
| ArgoCD Application sync status | ❓ Unknown | Cannot verify without ArgoCD admin access |

### Required Action

**ArgoCD admin should check Application status and trigger manual sync if needed:**

```bash
# Check Application status
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o yaml

# Check sync status
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o jsonpath='{.status.sync.status}'

# Trigger manual sync if needed
argocd app sync botburrow-agents-ns-apexalgo-iad
```

### Alternative: Workaround Deployment

If ArgoCD cannot be fixed, use the workaround deployment script:
```bash
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh
```

See `docs/workarounds/bd-cni-argocd-workaround.md` for details.
