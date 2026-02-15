# BD-2BW: Apply secrets-manager RBAC to apexalgo-iad

**Status:** ⏳ Awaiting TRUE cluster-admin with elevated privileges
**Date:** 2026-02-15
**Bead:** bd-2bw (human-type)
**Last Attempt:** 2026-02-15 22:10 UTC (correctly rejected - devpod-observer lacks RBAC permissions)

---

## ⚠️ IMPORTANT: Requires True Cluster-Admin Privileges

**The devpod-observer ServiceAccount CANNOT apply RBAC resources** (correct security design).

This task requires a **human administrator** with:
- Direct access to apexalgo-iad Kubernetes API
- **cluster-admin credentials** (NOT devpod-observer proxy)
- kubectl configured with elevated privileges

---

## Quick Apply (1 minute)

From a machine with **TRUE cluster-admin access** to **apexalgo-iad**:

```bash
# 1. Pull latest changes
cd /path/to/botburrow-agents
git pull origin main

# 2. Apply RBAC
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# 3. Verify
kubectl get role -n botburrow-agents secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
```

**Expected output:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
```

---

## What This Does

Grants `devpod-observer` ServiceAccount limited access to secrets in `botburrow-agents` namespace:

- ✅ Read access: `get`, `list`
- ✅ Update access: `patch`, `update`
- ❌ NO `create` or `delete` permissions
- ✅ Namespace-scoped (botburrow-agents only)

**Purpose:** Required for workers to apply Hub API authentication fix (bd-2jm)

---

## Security Review

| Aspect | Assessment |
|--------|------------|
| **Scope** | ✅ Namespace-scoped only |
| **Destructive Operations** | ✅ None (no create/delete) |
| **Blast Radius** | ✅ Limited to botburrow-agents secrets |
| **Reversibility** | ✅ Fully reversible |
| **Risk Level** | ⚠️ Medium (secrets read/write) |
| **Precedent** | ✅ Similar to deployment-scaler (bd-3o6) |

**Recommendation:** ✅ **APPROVE AND APPLY**

---

## Unblocks

- **bd-12r** - Grant devpod-observer RBAC access to botburrow-agents namespace
- **bd-2jm** - Hub API authentication fix

---

## Rollback (if needed)

```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

---

## Post-Application

**Nothing required!** Workers will automatically:
1. Detect RBAC is applied
2. Verify access
3. Proceed with Hub API fix (bd-2jm)
4. Update bead statuses

---

**Manifest:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`
**Full Details:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/HUMAN-ACTION-SECRETS-RBAC.md`
