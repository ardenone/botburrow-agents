# bd-2yb: Simplified Requirements Approach Summary

**Bead:** Alternative: Simplify requirements
**Original Bead:** bd-1v9 - Fix botburrow-agents deployment via ArgoCD
**Date:** 2026-02-08
**Approach:** simplified-scope

## Problem Statement

The original bead bd-1v9 was stuck because ArgoCD Application had synced the Namespace but no resources were being deployed. Workers were unable to proceed without understanding the root cause or having a clear path forward.

## Simplified Approach

The simplified-scope alternative focuses on **minimal viable deployment** that bypasses ArgoCD complexity:

### MVP Deployment Resources (Essential Only)

| Resource | Purpose | Why Essential |
|----------|---------|---------------|
| `rbac.yaml` | ServiceAccount, Role, RoleBinding | App permissions within namespace |
| `configmap.yaml` | Application configuration | Environment variables, feature flags |
| `valkey.yaml` | Redis/Valkey for coordination | Leader election for distributed runners |
| `runner-hybrid.yaml` | Single hybrid runner | Handles all work types (notification, exploration, execution) |

### Deferred Resources (Nice-to-Have)

| Resource | Purpose | Why Deferred |
|----------|---------|--------------|
| `coordinator.yaml` | Dedicated coordination service | Optional for simple deployments |
| `runner-notification.yaml` | Dedicated notification runner | Use single hybrid runner initially |
| `runner-exploration.yaml` | Dedicated exploration runner | Use single hybrid runner initially |
| `hpa.yaml` | Horizontal Pod Autoscaler | Manual scaling works fine initially |
| `servicemonitor.yaml` | Prometheus metrics | Observability only (can add later) |
| `skill-sync.yaml` | Background skill synchronization | Run on-demand or add later |

## Current Status

### BLOCKER: RBAC Permissions

The simplified deployment **cannot proceed** without write permissions. The `devpod-observer` ServiceAccount (used by devpods) has only **READ-ONLY** access:

```
Error from server (Forbidden): serviceaccounts is forbidden: User "system:serviceaccount:devpod-observer:devpod-observer"
cannot create resource "serviceaccounts" in API group "" in the namespace "botburrow-agents"
```

### Existing Human Bead for RBAC

**Bead ID:** `bd-3cpp` (in `/home/coder` workspace, not `/home/coder/botburrow-agents`)
**Title:** HUMAN: Grant devpod-observer RBAC for botburrow-agents namespace deployment

The human bead includes 4 options:
1. **Option 1 (Recommended):** Grant devpod-observer admin permissions via RoleBinding
2. **Option 2:** Create least-privilege Role with specific permissions
3. **Option 3:** Cluster-admin applies all resources directly
4. **Option 4:** Use ArgoCD ApplicationSet with cluster-admin secret

## Deployment Instructions (After RBAC is Granted)

```bash
# From devpod, after RBAC is granted:
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Verify permissions (should output "yes")
kubectl auth can-i create deployments -n botburrow-agents

# Apply simplified deployment
kubectl apply -k /home/coder/botburrow-agents/k8s/apexalgo-iad/

# Verify deployment
kubectl get all -n botburrow-agents
```

## Files Prepared for Simplified Deployment

1. **`k8s/apexalgo-iad/kustomization.yaml`** - Simplified resource list (already updated)
2. **`k8s/apexalgo-iad/DEPLOYMENT-SIMPLIFIED.md`** - Detailed deployment guide
3. **`k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md`** - Alternative minimal deployment guide
4. **`k8s/apexalgo-iad/kustomization-minimal.yaml`** - Minimal kustomization variant
5. **`k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml`** - RBAC grant manifest (for cluster-admin)

## Pros and Cons of Simplified Approach

### Pros
- Faster completion (fewer resources to deploy and validate)
- Easier to validate (smaller surface area for issues)
- Reduced complexity (single hybrid runner vs multiple specialized runners)
- Bypasses ArgoCD issues (direct kubectl deployment)
- Can scale up later (add deferred components as needed)

### Cons
- Limited functionality initially (no specialized runners)
- May need follow-up work (add components after validation)
- Requires cluster-admin intervention (RBAC grant)
- Bypasses GitOps temporarily (not managed by ArgoCD)

## Next Steps

1. **HUMAN ACTION REQUIRED:** Resolve bead bd-3cpp (RBAC grant)
2. **After RBAC:** Apply simplified deployment via kubectl
3. **Validate:** Check pods are running and logs show healthy state
4. **Scale:** Add deferred components as needed (coordinator, HPA, ServiceMonitor)
5. **Migrate to ArgoCD:** Once stable, create ArgoCD Application for GitOps management

## Related Documentation

- `argocd-investigation-findings.md` - Original ArgoCD investigation
- `k8s/apexalgo-iad/DEPLOYMENT-SIMPLIFIED.md` - Deployment guide
- `k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md` - Alternative minimal guide
- `k8s/apexalgo-iad/RESEARCH-deployment-options-bd-32a.md` - Research on deployment options
