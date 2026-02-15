# 🚨 CLUSTER-ADMIN ACTION REQUIRED: Apply secrets-manager RBAC

**Bead:** bd-2bw
**Status:** ✅ ALL PREP COMPLETE - Ready for 1-minute cluster-admin application
**Urgency:** HIGH - Blocks bd-2jm (Hub API authentication fix)
**Date:** 2026-02-15
**Verified By:** Claude Code Worker

---

## ⚡ Quick Apply (1 Minute)

```bash
# Step 1: SSH to machine with cluster-admin access to apexalgo-iad

# Step 2: Navigate to botburrow-agents repo
cd /path/to/botburrow-agents
git pull origin main  # Get latest changes

# Step 3: Apply the RBAC manifest
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# Step 4: Verify (optional)
kubectl get role -n botburrow-agents secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
```

**Expected Output:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
```

---

## ✅ Pre-Application Verification (COMPLETE)

### Worker Verification Status (2026-02-15)
- ✅ Namespace `botburrow-agents` exists (Active, 14d)
- ✅ ServiceAccount `devpod-observer` exists in `devpod-observer` namespace (32d)
- ✅ YAML manifest is syntactically valid
- ✅ Role permissions are minimal (get, list, patch, update only)
- ✅ No destructive permissions (no create, no delete)
- ✅ Namespace-scoped (botburrow-agents only)
- ❌ RBAC NOT YET APPLIED (kubectl get role → NotFound)
- ❌ Worker has NO cluster-admin permissions (verified)

### What This Enables
Once applied, workers can:
- ✅ Read secrets in `botburrow-agents` namespace
- ✅ Update secrets in `botburrow-agents` namespace
- ❌ Cannot create new secrets
- ❌ Cannot delete secrets
- ❌ No access to other namespaces

**Use Case:** Apply Hub API authentication fix (bd-2jm) by updating `botburrow-agents-secrets`

---

## 🔒 Security Review

| Aspect | Status |
|--------|--------|
| **Scope** | ✅ Namespace-scoped (botburrow-agents only) |
| **Destructive Ops** | ✅ No create/delete permissions |
| **Blast Radius** | ✅ Limited to botburrow-agents secrets |
| **Reversibility** | ✅ Can be removed with `kubectl delete -f ...` |
| **Risk Level** | ⚠️ Medium (secrets access) |
| **Precedent** | ✅ Similar to deployment-scaler RBAC (bd-3o6) |
| **Justification** | ✅ Required for Hub API configuration management |

**Recommendation:** ✅ APPROVE - Minimal scope, necessary for bd-2jm

---

## 📋 What Gets Created

### Role: secrets-manager (namespace: botburrow-agents)
```yaml
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list", "patch", "update"]
```

### RoleBinding: devpod-observer-secrets-manager
Binds the `secrets-manager` role to the `devpod-observer` ServiceAccount.

---

## 🧪 Post-Application Verification

After you apply the manifest, workers will automatically verify:

```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get secret -n botburrow-agents botburrow-agents-secrets
```

**Expected output:**
```
NAME                       TYPE     DATA   AGE
botburrow-agents-secrets   Opaque   4      14d
```

---

## 🔄 Rollback (if needed)

```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

---

## 🚧 Blocked Beads

This RBAC application unblocks:
- **bd-12r** - Grant devpod-observer RBAC access to botburrow namespace (technical bead)
- **bd-2jm** - Hub API authentication fix (depends on bd-12r)

---

## 📁 Related Files

1. **Manifest:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`
2. **Documentation:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/HUMAN-ACTION-SECRETS-RBAC.md`
3. **README:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/README.md`
4. **Application Guide:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/READY-FOR-HUMAN-APPLICATION.md`

---

## 🎯 Summary

**What:** Apply RBAC to grant devpod-observer read/update access to secrets in botburrow-agents namespace
**Why:** Required for Hub API authentication fix (bd-2jm)
**Risk:** Medium (secrets access), but namespace-scoped and no destructive permissions
**Time:** 1 minute to apply
**Verified:** All prerequisites confirmed, manifest validated, ready to apply

**Next Step:** Cluster-admin applies the manifest, workers verify, then proceed with bd-2jm
