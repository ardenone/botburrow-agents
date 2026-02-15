# Apply RBAC Manifests for devpod-observer in botburrow-agents Namespace

**Bead:** bd-1qs
**Status:** ⚠️ REQUIRES CLUSTER-ADMIN ACCESS
**Cluster:** apexalgo-iad
**Date:** 2026-02-15

## Problem

The `devpod-observer` ServiceAccount in the apexalgo-iad cluster needs RBAC permissions to access secrets and scale deployments in the `botburrow-agents` namespace, but it does NOT have permission to create RBAC resources (Roles/RoleBindings). This requires cluster-admin level access.

## Current State

```bash
# ❌ devpod-observer CANNOT access secrets
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl get secret -n botburrow-agents
Error from server (Forbidden): secrets is forbidden: User "system:serviceaccount:devpod-observer:devpod-observer"
cannot list resource "secrets" in API group "" in the namespace "botburrow-agents"

# ❌ devpod-observer CANNOT create RBAC resources
$ kubectl apply -f secrets-manager-role.yml
Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

## Manifests to Apply

Two RBAC manifest files are ready for application:

### 1. secrets-manager-role.yml
- **Role:** `secrets-manager`
- **Permissions:** get, list, patch, update secrets
- **Purpose:** Allow devpod-observer to read and update secrets for configuration management
- **Required for:** bd-2jm (Hub API authentication fix)

### 2. deployment-scaler-role.yml
- **Role:** `deployment-scaler`
- **Permissions:**
  - Scale deployments and HPAs
  - Read deployment/pod status
  - Port-forward to pods
- **Purpose:** Enable devpod-observer to scale deployments and test scaling behavior
- **Required for:** bd-3o6 (Runner scaling tests)

## Application Instructions

### Prerequisites

1. **Cluster-admin kubeconfig** for apexalgo-iad cluster
2. **kubectl** installed on your local machine
3. **Network access** to apexalgo-iad API server

### Option A: Apply from Local Machine (RECOMMENDED)

```bash
# 1. Set kubeconfig to cluster-admin for apexalgo-iad
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Verify cluster-admin access
kubectl auth can-i create roles -n botburrow-agents
# Should return: yes

# 3. Clone repository or copy manifests
git clone https://github.com/ardenone/botburrow-agents.git
cd botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# 4. Apply manifests
kubectl apply -f secrets-manager-role.yml
kubectl apply -f deployment-scaler-role.yml

# 5. Verify application
kubectl get role -n botburrow-agents
kubectl get rolebinding -n botburrow-agents

# Expected output:
# NAME                  CREATED AT
# secrets-manager       2026-02-15T...
# deployment-scaler     2026-02-15T...
#
# NAME                               ROLE                       AGE
# devpod-observer-secrets-manager    Role/secrets-manager       Xs
# devpod-observer-scaler             Role/deployment-scaler     Xs
```

### Option B: Apply via kubectl with Direct URL

```bash
# 1. Set kubeconfig to cluster-admin for apexalgo-iad
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Apply directly from GitHub raw URLs
kubectl apply -f https://raw.githubusercontent.com/ardenone/botburrow-agents/main/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

kubectl apply -f https://raw.githubusercontent.com/ardenone/botburrow-agents/main/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

### Option C: Apply via ArgoCD (Future GitOps Workflow)

If ArgoCD is configured to manage `cluster-configuration/`:

1. Commit manifests to Git (already done ✅)
2. ArgoCD automatically syncs and applies
3. No manual application needed

**Status:** ⚠️ Not yet configured

## Verification Steps

After applying manifests, verify permissions from devpod context:

```bash
# From devpod terminal (worker context)
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# ✅ Should succeed: List secrets
kubectl get secret -n botburrow-agents

# ✅ Should succeed: Get specific secret
kubectl get secret -n botburrow-agents botburrow-agents-secrets

# ✅ Should succeed: Scale deployment
kubectl scale deployment/hub-api -n botburrow-agents --replicas=2

# ✅ Should succeed: List deployments
kubectl get deployments -n botburrow-agents

# ✅ Should succeed: Port-forward
kubectl port-forward -n botburrow-agents pod/valkey-0 6379:6379
```

Expected results: All commands should succeed without "Forbidden" errors.

## Security Considerations

### Principle of Least Privilege ✅

Both roles follow minimal permission grants:

**secrets-manager:**
- ✅ ONLY secrets in botburrow-agents namespace
- ✅ ONLY read/update operations (no delete)
- ✅ No access to other namespaces

**deployment-scaler:**
- ✅ ONLY deployment scaling in botburrow-agents namespace
- ✅ ONLY read operations on pods/replicasets
- ✅ No access to other resources (configmaps, services, etc.)

### What devpod-observer CANNOT Do

Even after applying these manifests, devpod-observer will still be FORBIDDEN from:
- ❌ Creating new RBAC resources (roles, rolebindings)
- ❌ Deleting secrets or deployments
- ❌ Accessing other namespaces (except monitoring, devpod-observer)
- ❌ Cluster-scoped operations (nodes, PVs, etc. - read-only only)
- ❌ Escalating its own privileges

### Audit Trail

All RBAC changes are:
- ✅ Tracked in Git with commit history
- ✅ Labeled with bead IDs for traceability
- ✅ Annotated with purpose and context
- ✅ Applied via declarative manifests (not imperative commands)

## Blocked Beads

The following beads are currently blocked awaiting RBAC application:

1. **bd-12r** - Grant devpod-observer RBAC access to botburrow-agents namespace (parent bead)
2. **bd-2jm** - Apply Hub API authentication fix (needs secrets access)
3. **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## Rollback Procedure

If these permissions need to be revoked:

```bash
# Remove RoleBindings (removes access immediately)
kubectl delete rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl delete rolebinding -n botburrow-agents devpod-observer-scaler

# Optional: Remove Roles (cleanup)
kubectl delete role -n botburrow-agents secrets-manager
kubectl delete role -n botburrow-agents deployment-scaler
```

## Contact

For questions or issues:
- **Bead ID:** bd-1qs
- **Worker:** claude-code-worker
- **Workspace:** /home/coder/botburrow-agents
- **Git Repo:** https://github.com/ardenone/botburrow-agents

---

**Action Required:** Cluster-admin must apply these manifests to unblock worker beads.
