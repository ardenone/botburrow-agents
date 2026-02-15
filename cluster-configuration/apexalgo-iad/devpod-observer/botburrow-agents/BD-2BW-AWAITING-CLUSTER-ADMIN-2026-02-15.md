# BD-2BW: Awaiting True Cluster-Admin Application

**Status:** ⏳ Awaiting human cluster-admin with elevated privileges
**Date:** 2026-02-15 22:10 UTC
**Bead:** bd-2bw

---

## 🔒 Permission Check Results

**Attempted Application:** 2026-02-15 22:10 UTC
**User:** `system:serviceaccount:devpod-observer:devpod-observer`
**Result:** ❌ Forbidden (Expected - correct security posture)

```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"

Error from server (Forbidden): rolebindings.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "rolebindings"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

**Permission Verification:**
```bash
$ kubectl auth can-i create roles -n botburrow-agents
no

$ kubectl auth can-i create rolebindings -n botburrow-agents
no
```

---

## ✅ This is Correct Security Design

The `devpod-observer` ServiceAccount **should NOT** have permissions to create RBAC resources. This is proper least-privilege security:

1. **RBAC creation requires cluster-admin** - prevents privilege escalation
2. **Read-only ServiceAccount** - devpod-observer is intentionally limited
3. **Human approval required** - RBAC changes need oversight

---

## 🎯 Required Action: True Cluster-Admin

A human administrator with **cluster-admin privileges** must apply this manifest from a machine with direct cluster access:

### Prerequisites
- Direct access to apexalgo-iad Kubernetes API
- cluster-admin credentials (NOT devpod-observer)
- kubectl configured for apexalgo-iad

### Commands (1 minute)

```bash
# 1. Pull latest changes
cd /path/to/botburrow-agents
git pull origin main

# 2. Apply RBAC (requires cluster-admin)
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

## 📋 What Gets Applied

**Manifest:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`

**Resources:**
1. **Role:** `secrets-manager` (namespace: botburrow-agents)
   - Verbs: get, list, patch, update
   - Resources: secrets
   - ❌ NO create/delete

2. **RoleBinding:** `devpod-observer-secrets-manager` (namespace: botburrow-agents)
   - Subject: ServiceAccount devpod-observer (devpod-observer namespace)
   - RoleRef: Role secrets-manager

---

## 🔓 Unblocks After Application

**Immediate:**
- bd-12r - Grant devpod-observer RBAC access to botburrow-agents namespace

**Downstream:**
- bd-2jm - Hub API authentication fix (add JWT_SECRET to deployment env)

---

## 🔄 Post-Application

Once applied, workers will automatically:
1. Detect role and rolebinding exist
2. Verify secret access works (`kubectl get secret -n botburrow-agents`)
3. Close bd-12r as completed
4. Proceed with bd-2jm
5. Update bead statuses

**No manual verification needed.**

---

## 📚 Documentation

- **Quick Guide:** `docs/cluster-admin/BD-2BW-APPLY-SECRETS-RBAC.md`
- **Full Status:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/FINAL-WORKER-STATUS-BD-2BW-2026-02-15.md`
- **Manifest:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`

---

## 🎯 Recommendation

✅ **APPROVE AND APPLY** (when cluster-admin available)

**Rationale:**
1. Namespace-scoped (botburrow-agents only)
2. No destructive operations (no create/delete)
3. Minimal permissions (read + update secrets only)
4. Reversible (`kubectl delete -f ...`)
5. Follows precedent (similar to deployment-scaler-role.yml)
6. Required for Hub API fix

**Risk:** ⚠️ Medium (secrets access) - Acceptable given limited scope

---

**Worker Status:** ✅ All preparation complete, waiting for human cluster-admin
**Last Attempt:** 2026-02-15 22:10 UTC (Correctly rejected - no RBAC permissions)
**Next Action:** Human cluster-admin applies manifest with elevated privileges
