# bd-1qs: RBAC Application - Quick Summary for Human Execution

## Status: Ready for Cluster-Admin Execution

**Last Verified:** 2026-02-16 03:25 UTC
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents

---

## Quick Execute (5 Minutes)

### Prerequisites
- **Cluster-admin kubeconfig** for apexalgo-iad cluster
- Access to this repository

### Step 1: Apply Manifests (2 minutes)

```bash
# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Navigate to repository
cd /path/to/botburrow-agents

# Apply RBAC manifests
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

**Expected Output:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
role.rbac.authorization.k8s.io/deployment-scaler created
rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created
```

### Step 2: Verify Permissions (1 minute)

```bash
# Verify roles exist
kubectl get role -n botburrow-agents secrets-manager deployment-scaler

# Verify devpod-observer has secret access (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

# Verify devpod-observer has scaling access (should return "yes")
kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

### Step 3: Close Bead (2 minutes)

```bash
# From devpod OR from your local machine with repository cloned
cd /path/to/botburrow-agents

# Close bead as completed
br close bd-1qs --status completed
br sync --flush-only

# Commit and push
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Applied secrets-manager and deployment-scaler roles to apexalgo-iad cluster.
Verified devpod-observer ServiceAccount has correct permissions.

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

---

## What This Unblocks

Once applied, these beads can proceed:
- **bd-12r** - Grant devpod-observer RBAC access to botburrow-agents namespace
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

---

## Security Review

✅ Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update (NO delete, NO create)

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **NO permission** to delete or modify other resources

---

## Troubleshooting

**Problem: "Error from server (Forbidden): ..."**
- **Cause:** Current kubeconfig lacks cluster-admin access
- **Fix:** Verify you're using cluster-admin kubeconfig for apexalgo-iad

**Problem: "Error from server (AlreadyExists): ..."**
- **Cause:** Roles already applied
- **Fix:** Skip to Step 2 (verification)

**Problem: br command not found**
- **Cause:** beads_rust (br) not installed
- **Fix:** Install from https://github.com/yourusername/beads_rust OR ask another admin to close the bead

---

## Complete Documentation

For detailed instructions, troubleshooting, and context:
- **Quick Reference:** CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md
- **Worker Status:** WORKER-STATUS.md
- **Manifests:** secrets-manager-role.yml, deployment-scaler-role.yml
