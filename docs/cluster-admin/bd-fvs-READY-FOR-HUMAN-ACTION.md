# bd-fvs: READY FOR HUMAN CLUSTER-ADMIN ACTION

**Bead ID:** bd-fvs
**Title:** CLUSTER-ADMIN: Grant permissions to install ArgoCD in apexalgo-iad
**Status:** ✅ ALL PREP COMPLETE - AWAITING HUMAN ACTION
**Date:** 2026-02-15
**Worker:** claude-code-glm-47-foxtrot (final verification)
**Previous Worker:** claude-code-glm-47-lima (preparation)

---

## 🎯 ACTION REQUIRED

**You are a human cluster-administrator.** This bead is ready for you to execute.

**Time Required:** < 15 minutes total (< 5 minutes active time)

**Primary Reference:** `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`

---

## ⚡ Quick Start Commands

```bash
# Connect to apexalgo-iad with cluster-admin credentials

# PHASE 1: Grant cluster-admin (< 1 minute)
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# PHASE 2: Wait for workers to install ArgoCD (5-10 minutes, automated)
kubectl get pods -n argocd -w

# PHASE 3: Revoke cluster-admin (< 1 minute)
kubectl delete clusterrolebinding devpod-observer-cluster-admin
```

---

## ✅ Verification Complete

All preparation work has been completed and verified:

### Documentation Created
- ✅ **Cluster-admin checklist:** `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`
- ✅ **Worker status report:** `docs/cluster-admin/bd-fvs-worker-final-status.md`
- ✅ **Deployment guide (for workers):** `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
- ✅ **Installation plan:** `docs/resolutions/bd-3f3-argocd-installation-plan.md`

### Manifests Ready
- ✅ **ArgoCD namespace:** `k8s/apexalgo-iad/argocd/namespace.yaml`
- ✅ **ArgoCD installation:** `k8s/apexalgo-iad/argocd/install.yaml`
- ✅ **ApplicationSet:** `k8s/apexalgo-iad/argocd/applicationset.yaml`
- ✅ **Kustomization:** `k8s/apexalgo-iad/argocd/kustomization.yaml`
- ✅ **Installation script:** `k8s/apexalgo-iad/argocd/install.sh`

### Cluster State Verified
- ✅ **botburrow-agents namespace:** Active (13 days, 13 healthy pods)
- ✅ **kubectl-proxy connectivity:** Working (verified 2026-02-14)
- ✅ **devpod-observer ServiceAccount:** Exists (read-only permissions)
- ❌ **ArgoCD namespace:** NotFound (expected - to be created by workers)
- ❌ **cluster-admin binding:** NotFound (expected - to be created by human)

---

## 📋 What Happens Next

### Phase 1: Human Grants Permissions (< 1 minute)
You execute a single kubectl command to grant temporary cluster-admin permissions to the `devpod-observer` ServiceAccount.

### Phase 2: Workers Install ArgoCD (5-10 minutes, automated)
Workers automatically:
1. Create ArgoCD namespace
2. Install ArgoCD components (7-8 pods)
3. Apply ArgoCD Application for botburrow-agents
4. Verify sync status

### Phase 3: Human Revokes Permissions (< 1 minute)
You execute a single kubectl command to revoke the temporary cluster-admin permissions.

### Phase 4: GitOps Deployment Active (ongoing)
ArgoCD continuously syncs the botburrow-agents deployment from git repository to cluster.

---

## 🔒 Security Model

- **Duration:** < 30 minutes (only during ArgoCD installation)
- **Scope:** Limited to ArgoCD installation tasks
- **Audit:** All kubectl operations logged in cluster audit logs
- **Rollback:** Simple - delete ClusterRoleBinding
- **Risk Level:** ⚠️ ACCEPTABLE (low likelihood, medium impact, strong mitigations)

**Why this is safe:**
1. Time-boxed elevation (< 30 minutes)
2. devpod-observer already has extensive read permissions cluster-wide
3. Single-purpose use (ArgoCD installation only)
4. All actions are audited
5. Immediately revoked after installation

---

## 📚 References

### Primary Documents (Start Here)
1. **Cluster-Admin Checklist:** `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`
   - Pre-flight verification commands
   - Copy-paste ready kubectl commands
   - Monitoring instructions
   - Troubleshooting guide

2. **Worker Status Report:** `docs/cluster-admin/bd-fvs-worker-final-status.md`
   - Current cluster state verification
   - Automated workflow explanation
   - Success criteria checklist

### Supporting Documents
3. **Deployment Guide (for workers):** `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
4. **Installation Plan:** `docs/resolutions/bd-3f3-argocd-installation-plan.md`

### Related Beads
- **bd-3f3:** Parent human bead (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad for GitOps deployment)
- **bd-3e3:** Original GitOps deployment request (blocked by bd-3f3)
- **bd-13z:** Closed duplicate bead

---

## 🚦 Success Criteria

Before closing this bead, verify:

- [ ] Phase 1: Cluster-admin binding created
- [ ] Phase 2: ArgoCD installed and running (7-8 pods)
- [ ] Phase 3: Cluster-admin binding deleted
- [ ] Phase 4: GitOps deployment verified
- [ ] ArgoCD Application `botburrow-agents` is Synced/Healthy
- [ ] All botburrow-agents pods are Running
- [ ] devpod-observer permissions revoked (cannot create namespaces)

---

## 🎬 Ready to Begin?

**Start here:** Open `docs/cluster-admin/bd-fvs-permission-grant-checklist.md` and follow the step-by-step instructions.

**Estimated time:** < 15 minutes total, < 5 minutes of your active time.

---

**Status:** ✅ READY FOR HUMAN ACTION
**Next Action:** Human cluster-admin opens `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`
