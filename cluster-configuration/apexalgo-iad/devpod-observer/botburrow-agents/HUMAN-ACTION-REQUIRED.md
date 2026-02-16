# 🚨 HUMAN ACTION REQUIRED - Apply RBAC Manifests to apexalgo-iad Cluster

**Bead:** bd-1qs
**Priority:** P0 CRITICAL (blocks bd-12r, bd-2jm, bd-3o6)
**Required Role:** cluster-admin access to apexalgo-iad cluster
**Estimated Time:** < 2 minutes
**Last Verified:** 2026-02-16 01:33 UTC

## TL;DR - What You Need to Do

Apply two RBAC manifest files to apexalgo-iad cluster using cluster-admin kubeconfig. These grant minimal permissions to devpod-observer ServiceAccount for secrets management and deployment scaling.

## Quick Start (Copy-Paste)

**⚠️ CRITICAL:** Do NOT use `/home/coder/.kube/apexalgo-iad.kubeconfig` (read-only devpod kubeconfig)
**✅ USE:** Your personal cluster-admin kubeconfig for apexalgo-iad cluster

```bash
# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig

# Verify you have permission to create roles
kubectl auth can-i create roles -n botburrow-agents
# Expected: yes

# Navigate to manifest directory (adjust path as needed)
cd /path/to/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# Apply RBAC manifests
kubectl apply -f secrets-manager-role.yml
kubectl apply -f deployment-scaler-role.yml

# Verify permissions granted
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes
```

## Why This Is Needed

Workers cannot create RBAC resources because the devpod-observer ServiceAccount intentionally lacks this permission as a security boundary. This prevents workers from escalating privileges.

**Error encountered:**
```
Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

**What This Unblocks:**
- ✅ bd-12r - CLUSTER-ADMIN: Grant devpod-observer RBAC access to botburrow-agents namespace
- ✅ bd-2jm - Hub API authentication fix (requires secret write access)
- ✅ bd-3o6 - Runner scaling tests (requires deployment scaling access)

## Current Status

✅ **Worker verification complete** (2026-02-15)
- Manifests validated and committed
- Prerequisites verified (namespace exists, ServiceAccount exists)
- Documentation complete
- Stale dependency removed (bd-33d no longer exists)

❌ **RBAC resources NOT applied yet** (verified 2026-02-16 01:33 UTC)
- `kubectl get role -n botburrow-agents secrets-manager` → NotFound
- `kubectl get role -n botburrow-agents deployment-scaler` → NotFound

🔒 **Permissions verified correct** (2026-02-16 01:33 UTC)
- Current kubeconfig: `/home/coder/.kube/apexalgo-iad.kubeconfig`
- Identity: `system:serviceaccount:devpod-observer:devpod-observer`
- Can create roles: **NO** (intentional security boundary)

## Manifests to Apply

### 1. secrets-manager-role.yml (49 lines)

**Purpose:** Grant devpod-observer permission to read and update secrets in botburrow-agents namespace

**Permissions:**
- **Resources:** secrets
- **Verbs:** get, list, patch, update
- **Scope:** botburrow-agents namespace only
- **NO permission to:** create or delete secrets

**Required for:** bd-2jm (Hub API authentication fix)

### 2. deployment-scaler-role.yml (74 lines)

**Purpose:** Grant devpod-observer permission to scale deployments and manage HPAs for testing

**Permissions:**
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets, pods/portforward
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **Scope:** botburrow-agents namespace only
- **NO permission to:** delete deployments or modify other resources

**Required for:** bd-3o6 (Runner scaling tests)

## Security Review

**Is this safe?** ✅ YES (minimal permissions)

- ✅ **Namespace-scoped:** Both roles only affect botburrow-agents namespace
- ✅ **Resource-scoped:** Limited to specific resources (secrets, deployments)
- ✅ **Minimal verbs:** No delete or create permissions for most resources
- ✅ **No privilege escalation:** Cannot create/modify RBAC resources
- ✅ **Auditable:** All actions logged in Kubernetes audit logs
- ✅ **Principle of least privilege:** Only permissions needed for specific tasks

## Expected Output

**Phase 1 - Grant Permissions:**
```
clusterrolebinding.rbac.authorization.k8s.io/devpod-observer-cluster-admin created
yes
```

**Phase 2 - Monitor Installation:**
```
# After 1-2 minutes:
namespace/argocd created

# After 5-7 minutes:
NAME                                               READY   STATUS    AGE
argocd-application-controller-0                    1/1     Running   2m
argocd-applicationset-controller-xxx               1/1     Running   2m
argocd-dex-server-xxx                              1/1     Running   2m
argocd-notifications-controller-xxx                1/1     Running   2m
argocd-redis-xxx                                   1/1     Running   2m
argocd-repo-server-xxx                             1/1     Running   2m
argocd-server-xxx                                  1/1     Running   2m
```

**Phase 3 - Revoke Permissions:**
```
clusterrolebinding.rbac.authorization.k8s.io "devpod-observer-cluster-admin" deleted
Error from server (NotFound): clusterrolebindings.rbac.authorization.k8s.io "devpod-observer-cluster-admin" not found
no
```

## Verification Commands

```bash
# Verify ArgoCD is installed
kubectl get namespace argocd
kubectl get pods -n argocd
# All pods should be Running

# Verify ArgoCD Application exists
kubectl get application botburrow-agents -n argocd
# Should show: Synced / Healthy

# Verify permissions were revoked
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Should return: no

# Optional: Get ArgoCD admin password for UI access
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

## After You Complete All Phases

Close the bead to mark this work complete:

```bash
# From botburrow-agents repository
cd /home/coder/botburrow-agents

# Close bead
br close bd-3f3 --status completed

# Sync and commit
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-3f3): cluster-admin completed ArgoCD installation

Phases completed:
1. Granted temporary cluster-admin to devpod-observer ServiceAccount
2. Workers installed ArgoCD (7 pods Running, Healthy)
3. Revoked cluster-admin permissions
4. Verified GitOps deployment (botburrow-agents Synced/Healthy)

Unblocks: bd-3e3 (GitOps deployment)

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

This will automatically unblock bead **bd-3e3** (Create ArgoCD GitOps deployment for botburrow-agents).

## Need Help?

**📋 Full Execution Guide:** `/home/coder/botburrow-agents/docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md`
**✓ Verification Script:** `/home/coder/botburrow-agents/docs/cluster-admin/bd-3f3-VERIFY-READY.sh`
**📊 Worker Status:** `/home/coder/botburrow-agents/docs/cluster-admin/bd-3f3-WORKER-VERIFICATION-2026-02-16.md`
