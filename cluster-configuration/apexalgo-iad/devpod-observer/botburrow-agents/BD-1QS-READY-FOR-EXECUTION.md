# BD-1QS: READY FOR CLUSTER-ADMIN EXECUTION

## Status: ✅ ALL WORKER TASKS COMPLETE - AWAITING HUMAN EXECUTION

**Date:** 2026-02-16
**Bead:** bd-1qs
**Type:** CLUSTER-ADMIN ACTION REQUIRED
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents

---

## Executive Summary

All manifests are prepared, validated, and ready for application. This bead requires a **human with cluster-admin credentials** for the apexalgo-iad cluster to apply RBAC manifests.

**Why Manual:** The devpod-observer ServiceAccount (used by automated workers) does NOT have permission to create RBAC resources. This is correct security posture - RBAC changes require elevated privileges.

---

## Quick Execute (Recommended)

If you have cluster-admin kubeconfig for apexalgo-iad:

```bash
# 1. Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-cluster-admin.kubeconfig

# 2. Navigate to manifest directory
cd /home/coder/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# 3. Run quick apply script
bash QUICK-APPLY.sh

# 4. Close bead
cd /home/coder/botburrow-agents
br close bd-1qs --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

---

## What Gets Applied

### 1. secrets-manager Role + RoleBinding
**File:** `secrets-manager-role.yml`
**Grants:** devpod-observer ServiceAccount can get/list/patch/update secrets in botburrow-agents namespace
**Purpose:** Enable Hub API authentication fix (bd-2jm)
**Security:** Read-only + update, NO create or delete permissions

### 2. deployment-scaler Role + RoleBinding
**File:** `deployment-scaler-role.yml`
**Grants:** devpod-observer ServiceAccount can scale deployments and manage HPAs in botburrow-agents namespace
**Purpose:** Enable runner scaling tests (bd-3o6)
**Security:** Read + scale operations only, NO delete permissions

---

## Verification Steps (After Apply)

```bash
# Should show both roles exist
kubectl get role -n botburrow-agents secrets-manager deployment-scaler

# Should show both bindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager devpod-observer-scaler

# Should return "yes" for both
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

---

## What This Unblocks

- ✅ **bd-12r** - Parent bead requesting RBAC access
- ✅ **bd-2jm** - Hub API authentication fix (needs secret write access)
- ✅ **bd-3o6** - Runner scaling tests (needs deployment scaling access)

---

## Security Review ✅

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update
- **Denied:** create, delete, deletecollection

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **Denied:** delete, deletecollection

**Risk Assessment:** LOW - Minimal permissions, namespace-scoped, no destructive operations

---

## Manual Application (If Script Fails)

```bash
# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-cluster-admin.kubeconfig

# Navigate to directory
cd /home/coder/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# Apply manifests
kubectl apply -f secrets-manager-role.yml
kubectl apply -f deployment-scaler-role.yml

# Verify
kubectl get role -n botburrow-agents secrets-manager deployment-scaler
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager devpod-observer-scaler

# Test permissions
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

---

## Troubleshooting

### Error: "You do not have cluster-admin access"
**Cause:** KUBECONFIG not set to cluster-admin credentials
**Fix:** Export cluster-admin kubeconfig for apexalgo-iad

### Error: "roles.rbac.authorization.k8s.io already exists"
**Cause:** Roles already applied
**Fix:** Verify with `kubectl get role -n botburrow-agents` - if they exist, close bead as completed

### Error: "namespace botburrow-agents not found"
**Cause:** Namespace doesn't exist
**Fix:** Create namespace first: `kubectl create namespace botburrow-agents`

---

## Related Documentation

- 📄 **CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md** - Detailed step-by-step guide
- 📄 **WORKER-STATUS.md** - Worker verification log
- 📄 **BD-33D-COMPLETION-GUIDE.md** - Alternative guide (duplicate bead)
- 🔧 **QUICK-APPLY.sh** - Automated application script

---

## Worker Completion Status

✅ Manifests created and validated
✅ Documentation complete
✅ Verification performed (roles don't exist yet)
✅ Security review passed
✅ Dependencies documented
✅ Quick execution script provided
❌ **BLOCKED:** Awaiting human with cluster-admin credentials

**Next Action:** Human execution required
