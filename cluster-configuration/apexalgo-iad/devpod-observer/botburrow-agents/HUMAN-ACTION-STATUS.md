# HUMAN ACTION REQUIRED: Multiple Cluster-Admin Tasks

## Status: ⏳ Awaiting Human with Cluster-Admin Access

**Beads Awaiting Action:**
- **bd-33d** - Apply RBAC manifests (P1)
- **bd-3f3** - Install ArgoCD (P0, HIGHER PRIORITY)

**Date:** 2026-02-16
**Worker Status:** All preparation complete, verified, documented

---

## 🚀 PRIORITY 1: bd-3f3 - Install ArgoCD (START HERE)

### Quick Summary
Install ArgoCD in apexalgo-iad cluster using temporary cluster-admin elevation for devpod-observer ServiceAccount.

### Why This is Priority
- **P0 (Critical)** - Required for GitOps automation
- **Unblocks:** bd-3e3 (ArgoCD application setup)
- **Time:** < 15 minutes total (< 5 minutes human active time)
- **Risk:** Low (reversible, well-documented, automated installation)

### Quick Start
```bash
# 1. Grant cluster-admin (< 1 min)
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# 2. Monitor installation (5-10 min, automated by workers)
kubectl get pods -n argocd -w
# Wait for all 7-8 pods to reach Running, then Ctrl+C

# 3. Revoke cluster-admin (< 1 min) ⚠️ CRITICAL
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# 4. Close bead
cd /home/coder/botburrow-agents
br close bd-3f3 --status completed
br sync --flush-only && git add .beads/*.jsonl && git commit -m "chore(bd-3f3): cluster-admin completed ArgoCD installation" && git push
```

### Full Documentation
- **📖 START HERE:** docs/cluster-admin/bd-3f3-HUMAN-HANDOFF.md
- **🚀 Detailed Guide:** docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md
- **✓ Verification Script:** docs/cluster-admin/bd-3f3-VERIFY-READY.sh
- **📊 Worker Status:** docs/cluster-admin/bd-3f3-WORKER-FINAL-STATUS-2026-02-16-v2.md

---

## 📋 PRIORITY 2: bd-33d - Apply RBAC Manifests

### Quick Summary
Apply RBAC roles for devpod-observer ServiceAccount to access botburrow-agents namespace.

### Why This Matters
- **P1 (High)** - Required for worker access to secrets and deployments
- **Unblocks:** bd-1qs, bd-12r, bd-2jm, bd-3o6
- **Time:** < 5 minutes
- **Risk:** Very low (read/write access to single namespace)

### What's Ready ✅
- ✅ `secrets-manager-role.yml` - committed to git
- ✅ `deployment-scaler-role.yml` - committed to git
- ✅ Documentation prepared

### Quick Start
```bash
# From machine with cluster-admin kubeconfig for apexalgo-iad
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig

# Apply manifests
cd /home/coder/botburrow-agents
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml

# Verify
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

# Close bead
br close bd-33d --status completed
br close bd-1qs --status completed  # Original blocker
br sync --flush-only && git add .beads/*.jsonl && git commit -m "chore(bd-33d,bd-1qs): cluster-admin applied RBAC manifests" && git push
```

### Manifests to Apply
```bash
cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/
├── secrets-manager-role.yml     # Read/write secrets in botburrow-agents
└── deployment-scaler-role.yml   # Scale deployments in botburrow-agents
```

### Security Review ✅
Both roles follow **principle of least privilege**:

**secrets-manager:**
- Scope: botburrow-agents namespace only
- Resources: secrets only
- Verbs: get, list, patch, update (NO delete, NO create)

**deployment-scaler:**
- Scope: botburrow-agents namespace only
- Resources: deployments/scale, deployments, HPAs, pods, replicasets
- Verbs: get, list, watch, patch, update, create (portforward only)
- NO delete permissions

---

## 🔐 Why Workers Cannot Do This

Workers have **read-only access** via devpod-observer ServiceAccount:
- ✅ Can read existing resources
- ✅ Can monitor cluster state
- ❌ Cannot create RBAC resources (prevents privilege escalation)
- ❌ Cannot create cluster-scoped resources (namespaces, CRDs, ClusterRoles)

This is **intentional security design** - workers should not be able to grant themselves elevated permissions.

---

## 📊 Recommended Execution Order

### Option A: Sequential (Safest)
1. Execute bd-3f3 (Install ArgoCD) - 15 minutes
2. Verify ArgoCD is running
3. Execute bd-33d (Apply RBAC) - 5 minutes
4. Verify RBAC permissions

**Total Time:** ~20 minutes

### Option B: Parallel (Fastest)
1. Execute both tasks in single session
2. Grant cluster-admin once
3. Install ArgoCD AND apply RBAC manifests
4. Revoke cluster-admin after both complete

**Total Time:** ~10 minutes

---

## 🔍 Verification

### Verify bd-3f3 (ArgoCD Installation)
```bash
kubectl get namespace argocd
kubectl get pods -n argocd
kubectl get svc -n argocd

# Should see 7-8 pods all Running
```

### Verify bd-33d (RBAC Manifests)
```bash
kubectl get role -n botburrow-agents secrets-manager deployment-scaler
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager devpod-observer-scaler

# Test permissions
kubectl auth can-i get secrets -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
kubectl auth can-i patch deployments/scale -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
```

---

## 🚨 Important Reminders

### For bd-3f3 (ArgoCD)
- ⚠️ **MUST revoke cluster-admin immediately after installation**
- ⚠️ Use YOUR cluster-admin kubeconfig (NOT /home/coder/.kube/apexalgo-iad.kubeconfig)
- ✅ Workers will detect cluster-admin and install ArgoCD automatically
- ✅ Installation takes 5-10 minutes (fully automated)

### For bd-33d (RBAC)
- ✅ Safe to apply (least-privilege, namespace-scoped)
- ✅ No downstream risks
- ✅ Enables workers to manage secrets and scale deployments

---

## 📞 Contact & Troubleshooting

### If Something Goes Wrong

**bd-3f3 Issues:**
- Review: docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md (comprehensive troubleshooting)
- Run verification: ./docs/cluster-admin/bd-3f3-VERIFY-READY.sh

**bd-33d Issues:**
- Manifests won't apply: Verify cluster-admin access
- Permissions not working: Check ServiceAccount exists in devpod-observer namespace

### Getting Help
- All documentation is committed to git
- Worker status reports are in docs/cluster-admin/
- Verification scripts are executable and tested

---

## 📅 Timeline

**Created:** 2026-02-15
**Updated:** 2026-02-16
**Status:** Ready for immediate execution
**Estimated Completion:** < 30 minutes total for both tasks

---

## ✅ Checklist

- [ ] Read bd-3f3-HUMAN-HANDOFF.md
- [ ] Export cluster-admin KUBECONFIG
- [ ] Verify cluster-admin access (`kubectl auth can-i create clusterrolebinding`)
- [ ] Grant cluster-admin to devpod-observer
- [ ] Monitor ArgoCD installation (wait for pods Running)
- [ ] **REVOKE cluster-admin** (critical!)
- [ ] Apply RBAC manifests (bd-33d)
- [ ] Verify RBAC permissions
- [ ] Close both beads (bd-3f3, bd-33d, bd-1qs)
- [ ] Sync and commit bead updates

---

**Last Updated:** 2026-02-16
**Workers:** All preparation complete, standing by for cluster-admin execution
