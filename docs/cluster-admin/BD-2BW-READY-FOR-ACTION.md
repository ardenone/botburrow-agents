# 🚀 QUICK START: Apply secrets-manager RBAC (bd-2bw)

**Status:** ✅ READY FOR IMMEDIATE APPLICATION
**Required Role:** cluster-admin on apexalgo-iad
**Time Estimate:** 1 minute
**Risk Level:** ⚠️ Medium (secrets access, namespace-scoped, no destructive ops)

---

## ⚡ Quick Apply (Copy & Paste)

From a machine with cluster-admin access to **apexalgo-iad**:

```bash
# Navigate to repo
cd /path/to/botburrow-agents

# Apply RBAC
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# Verify (should show the role and rolebinding)
kubectl get role -n botburrow-agents secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
```

**Expected output:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
```

---

## 📋 What This Does

Grants the `devpod-observer` ServiceAccount permissions to:
- ✅ Read secrets in `botburrow-agents` namespace
- ✅ Update secrets in `botburrow-agents` namespace (for configuration management)
- ❌ NO create/delete permissions
- ❌ NO access to other namespaces

**Use Case:** Apply Hub API authentication fix (bd-2jm)

---

## 🔒 Security Review

| Aspect | Status |
|--------|--------|
| Scope | ✅ Namespace-scoped (botburrow-agents only) |
| Destructive Ops | ✅ No create/delete permissions |
| Blast Radius | ✅ Limited to botburrow-agents secrets |
| Reversibility | ✅ Removable with `kubectl delete -f ...` |
| Risk Level | ⚠️ Medium (secrets access) |
| Precedent | ✅ Similar to deployment-scaler RBAC (bd-3o6) |

**Recommendation:** ✅ APPROVE

---

## 📚 Full Documentation

For detailed context and security review, see:
- **Application Guide:** [READY-FOR-HUMAN-APPLICATION.md](../../cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/READY-FOR-HUMAN-APPLICATION.md)
- **Full Documentation:** [HUMAN-ACTION-SECRETS-RBAC.md](../../cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/HUMAN-ACTION-SECRETS-RBAC.md)
- **Manifest:** [secrets-manager-role.yml](../../cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml)

---

## 🔄 Rollback (if needed)

```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

---

## 🚧 Unblocks These Beads

- **bd-12r** - Grant devpod-observer RBAC access to botburrow-agents namespace
- **bd-2jm** - Hub API authentication fix

---

**Last Worker Verification:** 2026-02-15 21:13 UTC
**Worker Status:** ✅ All preparation complete
**RBAC Status:** ❌ Not yet applied
**Next Action:** Human applies manifest
