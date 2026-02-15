# ✅ READY FOR CLUSTER-ADMIN ACTION

**Bead:** bd-1qs
**Date:** 2026-02-15 22:59 UTC
**Status:** 🟢 ALL PREREQUISITES MET - AWAITING CLUSTER-ADMIN

---

## 🎯 Quick Summary

Workers have completed all preparation. You (cluster-admin) need to apply 2 RBAC manifest files to the apexalgo-iad cluster. This will grant the `devpod-observer` ServiceAccount minimal permissions to access secrets and scale deployments in the `botburrow-agents` namespace.

**Time Required:** 2-5 minutes

---

## ✅ Prerequisites Verified

- [x] botburrow-agents namespace exists in apexalgo-iad cluster (Status: Active)
- [x] devpod-observer ServiceAccount exists in devpod-observer namespace
- [x] RBAC manifests created and validated (YAML syntax correct)
- [x] Documentation complete (APPLY-RBAC.md, QUICK-APPLY.sh)
- [x] Security review passed (least privilege principle)
- [x] All changes committed to Git (commit `4546052`)

**Worker cannot proceed because:**
```
Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

This is intentional security - ServiceAccounts should not be able to escalate their own privileges.

---

## 🚀 How to Apply (Choose One Method)

### Method 1: Quick Script (RECOMMENDED) ⚡

```bash
# 1. Navigate to this directory
cd /path/to/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# 2. Set your cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 3. Run the script
./QUICK-APPLY.sh
```

**What the script does:**
- Verifies you have cluster-admin access
- Applies both RBAC manifests
- Verifies roles and rolebindings were created
- Shows verification output

---

### Method 2: Manual Application 🔧

```bash
# 1. Set your cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Verify you have admin access
kubectl auth can-i create role -n botburrow-agents
# Should return: yes

# 3. Navigate to manifest directory
cd /path/to/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# 4. Apply both manifests
kubectl apply -f secrets-manager-role.yml
kubectl apply -f deployment-scaler-role.yml

# Expected output:
# role.rbac.authorization.k8s.io/secrets-manager created
# rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
# role.rbac.authorization.k8s.io/deployment-scaler created
# rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created

# 5. Verify (optional)
kubectl get role -n botburrow-agents
kubectl get rolebinding -n botburrow-agents
```

---

### Method 3: One-Liner 💻

```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig && \
cd /path/to/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents && \
kubectl apply -f secrets-manager-role.yml && \
kubectl apply -f deployment-scaler-role.yml
```

---

## 📋 What's Being Applied

### File 1: secrets-manager-role.yml (1.6 KB)
**Grants:**
- get, list secrets (read)
- patch, update secrets (modify existing)

**Does NOT grant:**
- create secrets (no new secrets)
- delete secrets (no removal)

**Use Case:** Fix Hub API authentication by updating existing secret (bd-2jm)

---

### File 2: deployment-scaler-role.yml (2.3 KB)
**Grants:**
- get, patch, update deployments/scale
- get, list, watch deployments, pods, replicasets
- get, patch, update horizontalpodautoscalers
- create, get pods/portforward

**Does NOT grant:**
- create, delete deployments
- delete pods

**Use Case:** Run deployment scaling tests for hub-api and runner (bd-3o6)

---

## 🔒 Security Review

### Risk Assessment: ⚠️ MEDIUM

**Why Medium Risk:**
- Secrets access is sensitive (can read/update secrets like API keys)
- Deployment scaling can affect availability (scale to 0 = downtime)

**Why NOT High Risk:**
- No delete permissions (cannot remove resources)
- Namespace-scoped only (botburrow-agents only)
- No RBAC self-escalation (cannot grant itself more permissions)
- Reversible (can rollback with `kubectl delete -f`)

### Principle of Least Privilege ✅

| Permission | secrets-manager | deployment-scaler |
|------------|----------------|-------------------|
| Read | ✅ | ✅ |
| Update | ✅ | ✅ (scale only) |
| Create | ❌ | ❌ |
| Delete | ❌ | ❌ |
| RBAC escalation | ❌ | ❌ |
| Cluster-scoped | ❌ | ❌ |

### Audit Trail ✅

- **Git History:** All changes tracked in Git
- **Labels:** Manifests labeled with bead IDs (bd-12r, bd-3o6)
- **Annotations:** Purpose documented in metadata
- **Reversible:** Can rollback with `kubectl delete -f <manifest>`

---

## 🎯 What This Unblocks

After you apply these manifests, workers will automatically:

| Bead ID | Title | Status After Application |
|---------|-------|--------------------------|
| bd-1qs | CLUSTER-ADMIN: Apply RBAC manifests | ✅ Completed (this bead) |
| bd-12r | Grant devpod-observer RBAC access | ✅ Completed (parent bead) |
| bd-2jm | Apply Hub API authentication fix | 🟢 Unblocked - can proceed |
| bd-3o6 | Runner scaling tests | 🟢 Unblocked - can proceed |

**Workers will detect the new permissions and proceed automatically.**

---

## ✅ Verification (After Application)

Run these commands from devpod to verify workers have access:

```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Test 1: Secrets access
kubectl get secret -n botburrow-agents botburrow-agents-secrets
# Should succeed without "Forbidden" error

# Test 2: Deployment scaling
kubectl get deployments -n botburrow-agents
kubectl scale deployment/hub-api -n botburrow-agents --replicas=2
# Should succeed

# Test 3: Verify roles exist
kubectl get role -n botburrow-agents
kubectl get rolebinding -n botburrow-agents
# Should show secrets-manager and deployment-scaler
```

---

## 🔄 Rollback (If Needed)

If you need to revoke these permissions:

```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig
cd /path/to/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

kubectl delete -f secrets-manager-role.yml
kubectl delete -f deployment-scaler-role.yml
```

This will remove both roles and rolebindings, revoking all permissions.

---

## 📚 Additional Documentation

| Document | Purpose |
|----------|---------|
| **READY-FOR-CLUSTER-ADMIN.md** | This file - quick reference |
| [APPLY-RBAC.md](./APPLY-RBAC.md) | Detailed instructions and security analysis |
| [QUICK-APPLY.sh](./QUICK-APPLY.sh) | Automated application script |
| [STATUS.md](./STATUS.md) | Current status summary |
| [secrets-manager-role.yml](./secrets-manager-role.yml) | RBAC manifest for secrets access |
| [deployment-scaler-role.yml](./deployment-scaler-role.yml) | RBAC manifest for deployment scaling |

---

## 🎬 Expected Outcome

**Before application:**
```
$ kubectl get secrets -n botburrow-agents
Error from server (Forbidden): secrets is forbidden
```

**After application:**
```
$ kubectl get secrets -n botburrow-agents
NAME                       TYPE     DATA   AGE
botburrow-agents-secrets   Opaque   2      5d
```

---

## 📞 Support

- **Worker:** claude-code-worker
- **Workspace:** /home/coder/botburrow-agents
- **Git Commit:** `4546052`
- **Bead:** bd-1qs

---

**Next Action:** Apply manifests using one of the methods above → Workers continue automatically
