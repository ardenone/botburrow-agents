# 🚀 ArgoCD Installation - Ready for Human Action

**Bead ID:** bd-fvs
**Status:** ✅ ALL PREP COMPLETE - READY FOR HUMAN CLUSTER-ADMIN
**Date:** 2026-02-15
**Estimated Time:** < 15 minutes total (< 5 minutes human time)

---

## Quick Start

Execute these commands on a machine with cluster-admin access to **apexalgo-iad**:

### PHASE 1: Grant Temporary Permissions (< 1 minute)

```bash
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer
```

### PHASE 2: Wait for Workers to Install ArgoCD (5-10 minutes, automated)

```bash
# Monitor ArgoCD namespace creation
kubectl get namespace argocd -w

# Once namespace exists, monitor pods
kubectl get pods -n argocd -w
```

Wait until all ArgoCD pods are Running (7-8 pods).

### PHASE 3: Revoke Permissions (< 1 minute)

```bash
# Verify ArgoCD is installed
kubectl get pods -n argocd

# Revoke cluster-admin
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Verify revocation
kubectl get clusterrolebinding devpod-observer-cluster-admin
# Expected: Error from server (NotFound)
```

---

## Current State (Verified 2026-02-15)

✅ **Ready:**
- botburrow-agents namespace: Active (14 days)
- botburrow-agents pods: 9+ Running
- All ArgoCD manifests prepared
- All documentation complete

❌ **Waiting for Human Action:**
- ArgoCD namespace: NotFound (to be created)
- devpod-observer-cluster-admin binding: NotFound (to be granted)

---

## Complete Documentation

📋 **PRIMARY REFERENCE:**
- `docs/cluster-admin/bd-fvs-permission-grant-checklist.md` (12KB)
  - Step-by-step instructions
  - Pre-flight verification
  - Troubleshooting guide
  - Security model

📊 **BACKGROUND:**
- `docs/cluster-admin/bd-fvs-worker-final-status.md` (10KB)
  - Current state details
  - Automated workflow explanation
  - Success criteria

🚀 **WORKER REFERENCE:**
- `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
  - ArgoCD installation steps
  - Worker automation reference

---

## Why This Approach?

- ✅ **Fast:** < 5 minutes human time (2 commands + monitoring)
- ✅ **Secure:** Time-boxed elevation (< 30 minutes), revoked immediately
- ✅ **Autonomous:** Workers handle installation without ongoing intervention
- ✅ **Simple:** 2 kubectl commands, easy rollback
- ✅ **Low Risk:** devpod-observer already has extensive read permissions

---

## What Happens After Permissions Granted?

Workers will **automatically**:
1. Create ArgoCD namespace
2. Install ArgoCD components
3. Wait for pods to be Running
4. Apply ArgoCD Application for botburrow-agents
5. Verify sync status
6. Update beads with completion

**No additional human action required until Phase 3 (revocation).**

---

## Success Verification

After Phase 3, verify:

```bash
# ArgoCD should be installed and working
kubectl get pods -n argocd
# All pods Running

# ArgoCD Application should be synced
kubectl get application botburrow-agents -n argocd
# STATUS: Synced, Healthy

# Permissions should be revoked
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no
```

---

## Next Steps

1. **Human cluster-admin:** Execute Quick Start above
2. **Workers (automatic):** Install ArgoCD when permissions detected
3. **Human cluster-admin:** Revoke permissions after installation completes
4. **Workers (automatic):** Verify and close bead bd-fvs

---

**Questions?** See comprehensive documentation in `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`
