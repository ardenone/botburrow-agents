# ✅ READY FOR HUMAN: Apply secrets-manager RBAC

**Bead:** bd-2bw (CLUSTER-ADMIN: Apply secrets-manager RBAC to apexalgo-iad)
**Status:** ✅ All preparation complete - waiting for cluster-admin to apply
**Date Verified:** 2026-02-15
**Verified By:** claude-code worker

---

## Pre-Application Verification Complete ✅

### Manifest Status
- ✅ YAML syntax valid
- ✅ Role definition correct (secrets: get, list, patch, update)
- ✅ RoleBinding correct (devpod-observer SA → secrets-manager role)
- ✅ Namespace-scoped (botburrow-agents only)
- ✅ No destructive permissions (no create, no delete)

### Prerequisites Verified
- ✅ Namespace exists: `botburrow-agents` (Active, 14d)
- ✅ ServiceAccount exists: `devpod-observer` in `devpod-observer` namespace (32d)
- ✅ Target cluster: apexalgo-iad
- ✅ Worker confirmed: **NO cluster-admin permissions** (kubectl auth can-i create role → no)

---

## Quick Application Guide

### Step 1: Access Cluster-Admin Context

SSH to a machine with cluster-admin access to **apexalgo-iad** cluster.

```bash
# Verify you have admin access
kubectl auth can-i create role -n botburrow-agents
# Should return: yes
```

### Step 2: Clone/Pull Repository

```bash
# If not already cloned
git clone <botburrow-agents-repo-url>
cd botburrow-agents

# If already cloned
cd /path/to/botburrow-agents
git pull origin main
```

### Step 3: Apply Manifest

```bash
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

**Expected Output:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
```

### Step 4: Verify Application

```bash
# Check role exists
kubectl get role -n botburrow-agents secrets-manager

# Check rolebinding exists
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager

# Verify permissions (optional)
kubectl auth can-i get secrets --as=system:serviceaccount:devpod-observer:devpod-observer -n botburrow-agents
# Should return: yes
```

---

## Post-Application: Worker Verification

After you apply the manifest, workers will automatically verify access:

```bash
# From devpod (worker will run this)
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get secret -n botburrow-agents botburrow-agents-secrets

# Expected output:
# NAME                       TYPE     DATA   AGE
# botburrow-agents-secrets   Opaque   4      14d
```

---

## What This Enables

Once applied, the devpod-observer ServiceAccount can:
- ✅ Read secrets in botburrow-agents namespace
- ✅ Update secrets in botburrow-agents namespace (for configuration management)
- ❌ Cannot create new secrets
- ❌ Cannot delete secrets
- ❌ No access to other namespaces

**Use Case:** Apply Hub API authentication fix (bd-2jm) by updating botburrow-agents-secrets

---

## Security Review Summary

| Aspect | Status |
|--------|--------|
| Scope | ✅ Namespace-scoped (botburrow-agents only) |
| Destructive Ops | ✅ No create/delete permissions |
| Blast Radius | ✅ Limited to botburrow-agents secrets |
| Reversibility | ✅ Can be removed with `kubectl delete -f ...` |
| Risk Level | ⚠️ Medium (secrets access) |
| Precedent | ✅ Similar to deployment-scaler RBAC (bd-3o6) |
| Justification | ✅ Required for Hub API authentication fix |

**Recommendation:** ✅ APPROVE - Minimal scope, necessary for bd-2jm, no destructive permissions

---

## Files Ready for Review

1. **Manifest:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`
2. **Documentation:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/HUMAN-ACTION-SECRETS-RBAC.md`
3. **README:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/README.md`

---

## Rollback (if needed)

```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

---

## Blocked Beads

This RBAC application unblocks:
- **bd-12r** - Grant devpod-observer RBAC access to botburrow namespace (technical bead)
- **bd-2jm** - Hub API authentication fix (depends on bd-12r)

---

**Status:** ⏳ Waiting for cluster-admin to apply
**Last Worker Check:** 2026-02-15T16:57:00Z (RBAC still not applied)
**Next Action:** Human applies manifest, then workers verify and proceed with bd-2jm
