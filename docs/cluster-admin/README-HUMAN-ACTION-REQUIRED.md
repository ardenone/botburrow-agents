# 🚨 HUMAN ACTION REQUIRED: bd-3f3

**Status:** ✅ READY FOR IMMEDIATE EXECUTION
**Type:** Cluster Administrator Action
**Time Required:** < 15 minutes (< 5 minutes active)
**Urgency:** HIGH - Blocking bd-3e3 (GitOps deployment)

---

## Quick Summary

**What's Needed:** Install ArgoCD in apexalgo-iad cluster

**Why:** Workers cannot create cluster-scoped resources (namespaces, CRDs, ClusterRoles) - requires cluster-admin privileges

**What's Ready:**
- ✅ All ArgoCD manifests in `k8s/apexalgo-iad/argocd/`
- ✅ Complete documentation (29 files)
- ✅ Verification script (`bd-3f3-VERIFY-READY.sh`)
- ✅ Copy-paste ready commands

---

## Execute These 3 Phases

### Phase 1: Grant Permissions (< 1 minute)
```bash
# Use YOUR cluster-admin kubeconfig (NOT /home/coder/.kube/apexalgo-iad.kubeconfig)
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig

# Verify you have cluster-admin
kubectl auth can-i create clusterrolebinding
# Expected: yes

# Grant temporary cluster-admin to devpod-observer ServiceAccount
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer
```

### Phase 2: Monitor Workers Installing (5-10 minutes, automated)
```bash
# Watch ArgoCD namespace creation
kubectl get namespace argocd -w

# Once namespace exists, watch ArgoCD pods
kubectl get pods -n argocd -w

# Wait for 7-8 pods to reach Running state, then Ctrl+C
```

### Phase 3: Revoke Permissions (< 1 minute) ⚠️ CRITICAL
```bash
# Revoke cluster-admin immediately after installation completes
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Verify revocation
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no
```

### Phase 4: Close Bead
```bash
cd /home/coder/botburrow-agents
br close bd-3f3 --status completed
br sync --flush-only
git add .beads/*.jsonl && git commit -m "chore(bd-3f3): cluster-admin installed ArgoCD" && git push
```

---

## Full Documentation

- **⚡ Quick Start:** `bd-3f3-EXEC-NOW.md` (this guide, expanded)
- **📖 Full Guide:** `bd-3f3-READY-FOR-EXECUTION.md` (comprehensive 460-line guide)
- **✓ Verification:** `bd-3f3-VERIFY-READY.sh` (pre-flight checks)
- **📊 Worker Status:** `bd-3f3-WORKER-FINAL-ACK-2026-02-16.md`

---

## What This Unblocks

- **bd-3e3** - Create ArgoCD GitOps deployment for botburrow-agents
- All downstream GitOps automation for botburrow-agents

---

## Security Notes

- ✅ **Time-boxed:** Permissions revoked immediately after installation (< 30 minutes)
- ✅ **Auditable:** All actions logged in Kubernetes audit logs
- ✅ **Reversible:** Can delete ClusterRoleBinding instantly
- ⚠️ **Risk Level:** MEDIUM (temporary cluster-admin access)
- ✅ **Mitigation:** Monitored, time-boxed, immediately revoked

---

**Bead:** bd-3f3
**Repository:** /home/coder/botburrow-agents
**Worker Prep Completed:** 2026-02-16
**Worker:** claude-code-glm-47-lima
**Ready For:** Human cluster administrator with cluster-admin access to apexalgo-iad
