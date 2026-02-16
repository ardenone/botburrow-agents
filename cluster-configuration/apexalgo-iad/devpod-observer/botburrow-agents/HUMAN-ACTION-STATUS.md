# HUMAN ACTION REQUIRED: Apply RBAC Manifests

## Status: ⏳ Awaiting Human with Cluster-Admin Access

**Bead:** bd-33d
**Created:** 2026-02-16
**Worker:** Claude Code (verified no cluster-admin access available)

---

## Summary

All RBAC manifests are **ready and committed to git**. However, applying them requires **cluster-admin credentials** for the apexalgo-iad cluster, which are **NOT available in the devpod environment**.

### What's Ready ✅
- ✅ `secrets-manager-role.yml` - committed to git
- ✅ `deployment-scaler-role.yml` - committed to git
- ✅ Quick reference guide (`CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md`)
- ✅ Worker status documentation (`WORKER-STATUS.md`)
- ✅ Security review completed (both roles follow least-privilege)

### What's Blocked ❌
- ❌ Applying manifests (requires cluster-admin)
- ❌ Verifying RBAC permissions
- ❌ Closing bead bd-1qs
- ❌ Unblocking downstream beads (bd-12r, bd-2jm, bd-3o6)

---

## Required Action

### Prerequisites
You need **cluster-admin access** to apexalgo-iad cluster. This typically means:
- Access to the Kubernetes master node, OR
- A kubeconfig with cluster-admin ClusterRoleBinding, OR
- Administrative credentials for the cluster

### Step 1: Apply RBAC Manifests

From a machine with cluster-admin kubeconfig for apexalgo-iad:

```bash
# Clone the repository if not already cloned
git clone <repo-url> botburrow-agents
cd botburrow-agents

# Apply the manifests
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

Expected output:
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
role.rbac.authorization.k8s.io/deployment-scaler created
rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created
```

### Step 2: Verify RBAC Was Applied

```bash
# Check Roles exist
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Check RoleBindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Verify permissions (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

All commands should succeed and `auth can-i` should return `yes`.

### Step 3: Close the Beads

From the devpod (or any environment with access to the repository):

```bash
cd /home/coder/botburrow-agents

# Close the original worker bead
br close bd-1qs --status completed

# Close the human action bead
br close bd-33d --status completed

# Sync and commit
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs,bd-33d): cluster-admin applied RBAC manifests

Applied secrets-manager and deployment-scaler roles to botburrow-agents namespace.
devpod-observer ServiceAccount now has read/write access to secrets and deployment scaling.

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

---

## What This Unblocks

Once applied, these downstream beads can proceed:

- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

---

## Security Review ✅

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update (NO delete, NO create)
- **Purpose:** Allow configuration updates for Hub API authentication

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **Purpose:** Enable scaling tests without granting destructive permissions
- **NO permission to:** delete resources, modify other namespaces

---

## Why Worker Cannot Do This

The devpod environment only has access to:
1. **ardenone-cluster** (in-cluster ServiceAccount) - local cluster
2. **apexalgo-iad** via `devpod-observer` ServiceAccount - **read-only + limited write**

The `devpod-observer` ServiceAccount **cannot create RBAC resources**:

```bash
$ kubectl auth can-i create roles -n botburrow-agents
no
```

This is **intentional security design** - granting RBAC creation permission to devpod-observer would enable privilege escalation attacks.

---

## Alternative Approaches Considered

### ❌ Option 2: Grant devpod-observer RBAC creation permission
**Why rejected:** Violates least privilege principle, enables privilege escalation

### ⚠️ Option 3: Use ArgoCD for manifest application
**Why not immediate:** Requires ArgoCD application setup for this directory, slower than manual application

### ✅ Option 1: Manual application with cluster-admin (RECOMMENDED)
**Why chosen:** Immediate resolution, minimal security risk, no architectural changes needed

---

## Contact

If you have questions or need clarification:
- Review the detailed instructions in `CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md`
- Check worker verification status in `WORKER-STATUS.md`
- Examine the manifest files to understand exactly what permissions are being granted

## Timestamp
Last updated: 2026-02-16T01:10:00Z
