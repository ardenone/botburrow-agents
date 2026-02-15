# 🚀 BD-2BW: Apply secrets-manager RBAC to apexalgo-iad

**Status:** ✅ READY FOR IMMEDIATE APPLICATION
**Date Prepared:** 2026-02-15
**Worker:** claude-code worker
**Bead:** bd-2bw (human type)

---

## ⚡ Quick Apply (1 Minute)

From a machine with **cluster-admin access** to **apexalgo-iad**:

```bash
# 1. Navigate to botburrow-agents repo
cd /path/to/botburrow-agents
git pull origin main

# 2. Apply RBAC manifest
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# 3. Verify application
kubectl get role -n botburrow-agents secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
```

**Expected output:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
```

---

## 📋 What This RBAC Does

Grants the `devpod-observer` ServiceAccount (in `devpod-observer` namespace) permissions to:

- ✅ **Read** secrets in `botburrow-agents` namespace (`get`, `list`)
- ✅ **Update** secrets in `botburrow-agents` namespace (`patch`, `update`)
- ❌ **NO** create permissions
- ❌ **NO** delete permissions
- ❌ **NO** access to other namespaces

**Use Case:** Required for workers to apply Hub API authentication fix (bd-2jm)

---

## 🔒 Security Review

| Aspect | Status |
|--------|--------|
| Scope | ✅ Namespace-scoped (`botburrow-agents` only) |
| Destructive Operations | ✅ None (no create/delete) |
| Blast Radius | ✅ Limited to `botburrow-agents` secrets |
| Reversibility | ✅ Fully reversible (`kubectl delete -f ...`) |
| Risk Level | ⚠️ Medium (secrets read/write access) |
| Precedent | ✅ Similar to deployment-scaler RBAC (bd-3o6) |
| Justification | ✅ Required for Hub API configuration management |

**Recommendation:** ✅ **APPROVE AND APPLY**

---

## ✅ Verification

All prerequisites have been verified by workers:

- ✅ Namespace `botburrow-agents` exists (Active, 14d)
- ✅ ServiceAccount `devpod-observer` exists in `devpod-observer` namespace (32d)
- ✅ Manifest syntax is valid
- ✅ YAML structure is correct
- ❌ RBAC NOT yet applied (awaiting cluster-admin)

**Post-Application Verification (automatic):**

Workers will automatically verify access after application:

```bash
# Workers run this from devpod
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get secret -n botburrow-agents botburrow-agents-secrets
# Should succeed and show secret metadata
```

---

## 🚧 Unblocks These Beads

- **bd-12r** - Grant devpod-observer RBAC access to botburrow-agents namespace (technical bead)
- **bd-2jm** - Hub API authentication fix (depends on bd-12r)

---

## 🔄 Rollback (if needed)

```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

This will:
- Remove the `secrets-manager` Role
- Remove the `devpod-observer-secrets-manager` RoleBinding
- Revoke all secrets access for `devpod-observer` in `botburrow-agents` namespace

---

## 📚 Full Documentation

For detailed context and technical details, see:

- **This Guide:** `docs/cluster-admin/BD-2BW-QUICK-START.md`
- **Application Guide:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/READY-FOR-HUMAN-APPLICATION.md`
- **Full Documentation:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/HUMAN-ACTION-SECRETS-RBAC.md`
- **Manifest:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`
- **Worker Verification:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/WORKER-VERIFICATION-2026-02-15.md`

---

## 🎯 Post-Application Steps

**Nothing required!** Workers will:
1. Automatically detect the RBAC is applied
2. Verify access by reading secrets
3. Proceed with bd-2jm (Hub API authentication fix)
4. Update bead status automatically

---

**Last Worker Check:** 2026-02-15 21:30 UTC
**Verification Status:** ✅ All prep complete
**Next Action:** Human cluster-admin applies manifest
