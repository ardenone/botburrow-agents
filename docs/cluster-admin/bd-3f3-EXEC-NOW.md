# bd-3f3: EXECUTE NOW - ArgoCD Installation

**Status:** ✅ READY FOR IMMEDIATE EXECUTION
**Date:** 2026-02-16
**Time Required:** < 15 minutes (< 5 minutes active)
**Type:** Human cluster-admin action required

---

## ⚡ Quick Execute (Copy-Paste)

```bash
# ========================================
# PHASE 1: Grant Permissions (< 1 min)
# ========================================

# CRITICAL: Use YOUR cluster-admin kubeconfig
# NOTE: /home/coding/.kube/apexalgo-iad.kubeconfig uses OIDC credentials that expire every ~3 days
# If you get "server has asked the client to provide credentials", regenerate from Rackspace Spot UI
export KUBECONFIG=/home/coding/.kube/apexalgo-iad.kubeconfig

# Verify you have cluster-admin
kubectl auth can-i create clusterrolebinding
# Expected: yes

# Grant temporary cluster-admin to devpod-observer
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# ========================================
# PHASE 2: Monitor Installation (5-10 min)
# ========================================

# Watch ArgoCD namespace creation
kubectl get namespace argocd -w
# Wait for namespace to appear, then Ctrl+C

# Watch ArgoCD pods come up
kubectl get pods -n argocd -w
# Wait for 7-8 pods to reach Running, then Ctrl+C

# ========================================
# PHASE 3: Revoke Permissions (< 1 min)
# ========================================

# Revoke cluster-admin (CRITICAL - DO NOT SKIP)
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Verify revocation
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no

# ========================================
# PHASE 4: Close Bead
# ========================================

cd /home/coding/botburrow-agents
bead close botburro-369f7a21 --reason "ArgoCD successfully installed in apexalgo-iad by cluster-admin"
bead sync flush-only
git add .beads/checkpoint/ && git commit -m "chore(botburro-369f7a21): cluster-admin completed ArgoCD installation in apexalgo-iad

- Granted temporary cluster-admin to devpod-observer ServiceAccount
- Workers installed ArgoCD (7-8 pods Running, Healthy)
- Revoked cluster-admin permissions
- Verified GitOps deployment (botburrow-agents Synced/Healthy)

Co-Authored-By: Claude <noreply@anthropic.com>" && git push
```

---

## 📋 What This Does

1. **Grants** temporary cluster-admin to `devpod-observer` ServiceAccount
2. **Workers automatically** detect elevated permissions and install ArgoCD
3. **Revokes** cluster-admin permissions immediately after installation
4. **Result:** ArgoCD running in apexalgo-iad cluster, managing botburrow-agents GitOps

---

## ✅ Success Verification

After Phase 3, verify:

```bash
# Check ArgoCD is installed
kubectl get pods -n argocd
# Expected: 7-8 pods all Running

# Check ArgoCD Application
kubectl get application botburrow-agents -n argocd
# Expected: Synced/Healthy

# Verify permissions revoked
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no
```

---

## 🚨 Critical Notes

1. **DO NOT** use `/home/coder/.kube/apexalgo-iad.kubeconfig` - it's read-only
2. **DO** use your personal cluster-admin kubeconfig for apexalgo-iad
3. **DO NOT** skip Phase 3 (revoking permissions)
4. **DO** monitor Phase 2 to ensure installation completes before revoking

---

## 📚 Full Documentation

- **Handoff Guide:** `docs/cluster-admin/bd-3f3-HUMAN-HANDOFF.md`
- **Detailed Guide:** `docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md`
- **Verification Script:** `docs/cluster-admin/bd-3f3-VERIFY-READY.sh`
- **Worker Status:** `docs/cluster-admin/bd-3f3-WORKER-FINAL-STATUS-2026-02-16-v2.md`

---

## 🔓 What This Unblocks

- **bd-3e3** - Create ArgoCD GitOps deployment for botburrow-agents
- All downstream GitOps automation for botburrow-agents

---

## ⏱️ Timeline

| Phase | Duration | Type |
|-------|----------|------|
| Grant permissions | < 1 min | Human |
| Install ArgoCD | 5-10 min | Automated |
| Revoke permissions | < 1 min | Human |
| **Total** | **< 15 min** | **Mixed** |

**Human active time:** < 5 minutes
**Automated time:** 5-10 minutes (just watch)

---

## 🛟 Troubleshooting

**Problem: Cannot create ClusterRoleBinding**
```bash
kubectl auth can-i create clusterrolebinding
# If "no", you don't have cluster-admin - use correct kubeconfig
```

**Problem: Workers not installing after 10+ minutes**
```bash
# Check if permissions granted correctly
kubectl get clusterrolebinding devpod-observer-cluster-admin

# May need to manually trigger or wait for next worker cycle
```

**Problem: Forgot to revoke permissions**
```bash
# Execute Phase 3 immediately
kubectl delete clusterrolebinding devpod-observer-cluster-admin
```

---

**Bead ID:** bd-3f3
**Repository:** /home/coder/botburrow-agents
**Worker Prep Complete:** 2026-02-16
**Ready For:** Human cluster administrator
