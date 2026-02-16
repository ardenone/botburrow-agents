# bd-3f3 Worker Assessment - ArgoCD Installation

**Bead ID:** bd-3f3
**Type:** HUMAN bead
**Status:** WAITING FOR HUMAN CLUSTER-ADMIN ACTION
**Worker:** claude-code-glm-47-lima (current assessment)
**Date:** 2026-02-16

---

## Executive Summary

**This bead cannot be completed by workers** because it requires **cluster-admin credentials** that workers do not have access to. All preparation work has been completed by previous workers (bd-fvs), and the task is now ready for a **human cluster-administrator** to execute.

**Action Required:** Human cluster-admin with apexalgo-iad access needs to execute 2 simple kubectl commands.

---

## Current State Verification (2026-02-16)

### ✅ Prerequisites Complete

```
✅ botburrow-agents namespace: Active (14 days old)
✅ botburrow-agents pods: 13/13 Running
   - coordinator: 2/2 Running
   - coordinator-git-sync: 2/2 Running
   - runner-exploration: 1/1 Running
   - runner-git-sync: 2/2 Running
   - runner-hybrid: 3/3 Running
   - runner-notification: 2/2 Running
   - valkey: 1/1 Running

✅ devpod-observer ServiceAccount: Exists (32 days old)
✅ ArgoCD manifests: Prepared in k8s/apexalgo-iad/argocd/
✅ Documentation: Complete and comprehensive
```

### ❌ Blocked by RBAC

```
❌ ArgoCD namespace: NotFound (needs to be created)
❌ devpod-observer cluster-admin binding: NotFound (needs to be created)
❌ Workers cannot create namespaces: Permission denied
❌ Workers lack cluster-admin access: Confirmed
```

### RBAC Permissions Check

```bash
$ kubectl auth can-i create namespace
Warning: resource 'namespaces' is not namespace scoped
no

$ kubectl auth can-i '*' '*' --all-namespaces
no

$ kubectl get clusterrolebinding devpod-observer-cluster-admin
Error from server (NotFound): clusterrolebindings.rbac.authorization.k8s.io "devpod-observer-cluster-admin" not found
```

**Conclusion:** Workers are correctly blocked by RBAC. This is functioning as designed.

---

## Why Workers Cannot Proceed

### Security Model
- **devpod-observer ServiceAccount** has **read-only access** cluster-wide
- **Creating namespaces** requires cluster-admin privileges
- **Installing ArgoCD** requires creating CRDs, namespaces, and cluster-scoped resources
- **Workers intentionally lack** these elevated permissions for security

### Design Intent
This is a **human bead** (type: human) specifically because it requires privileges that workers should not have. The bead type correctly reflects the requirement for human intervention.

---

## What Has Been Completed

### ✅ Preparation Work (bd-fvs - CLOSED)

1. **ArgoCD Manifests Created:**
   - `k8s/apexalgo-iad/argocd/namespace.yaml`
   - `k8s/apexalgo-iad/argocd/applicationset.yaml`
   - `k8s/apexalgo-iad/argocd/ingress.yaml`
   - `k8s/apexalgo-iad/argocd/install.yaml`
   - `k8s/apexalgo-iad/argocd/kustomization.yaml`
   - `k8s/apexalgo-iad/argocd/install.sh` (automated script)

2. **Documentation Created:**
   - **Primary:** `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`
   - **Worker Guide:** `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
   - **Status Report:** `docs/cluster-admin/bd-fvs-worker-final-status.md`

3. **Verification Completed:**
   - botburrow-agents namespace health confirmed
   - devpod-observer ServiceAccount verified
   - RBAC permissions validated (correctly restrictive)
   - kubectl-proxy connectivity tested

### ✅ Dependencies Cleaned Up (2026-02-16)

- **Removed:** bd-fvs dependency (already closed)
- **Removed:** bd-13z dependency (already closed, duplicate)
- **Current:** No blockers - ready for human action

---

## What Needs to Happen Next

### Human Cluster-Admin Actions

**Reference Document:** `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`

**Time Required:** < 5 minutes human time, 15 minutes total

#### Phase 1: Grant Temporary Cluster-Admin (< 1 minute)

```bash
# Connect to apexalgo-iad with your cluster-admin kubeconfig
# (NOT the devpod kubeconfig - use your personal cluster-admin access)

kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# Verify
kubectl get clusterrolebinding devpod-observer-cluster-admin
```

#### Phase 2: Monitor Worker Installation (5-10 minutes, automated)

```bash
# Workers will automatically detect the permissions and install ArgoCD
# Monitor progress:
kubectl get namespace argocd -w

# Once namespace exists:
kubectl get pods -n argocd -w

# Expected: 7-8 ArgoCD pods will start and reach Running state
```

#### Phase 3: Revoke Cluster-Admin (< 1 minute)

```bash
# After all ArgoCD pods are Running:
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Verify revocation:
kubectl get clusterrolebinding devpod-observer-cluster-admin
# Expected: Error from server (NotFound)

kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no
```

#### Phase 4: Verify GitOps Deployment (< 2 minutes)

```bash
# Check ArgoCD Application status
kubectl get application botburrow-agents -n argocd

# Should show:
# NAME               SYNC STATUS   HEALTH STATUS
# botburrow-agents   Synced        Healthy
```

---

## Alternative: Manual Installation by Human

If you prefer not to grant temporary cluster-admin to devpod-observer, you can manually install ArgoCD yourself:

**Reference:** `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`

**Time Required:** 15-20 minutes

This approach:
- ✅ No permission elevation needed
- ❌ More manual steps (more prone to errors)
- ❌ Blocks autonomous worker workflow

---

## Security Justification for Temporary Elevation

### Why This Is Safe

1. **Time-Boxed:** Permissions exist for < 30 minutes only
2. **Single-Purpose:** Only used for ArgoCD installation
3. **Already Trusted:** devpod-observer has extensive read permissions cluster-wide
4. **Auditable:** All actions logged in Kubernetes audit logs
5. **Reversible:** Binding can be deleted instantly
6. **Monitored:** Human watches installation progress

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Unauthorized namespace creation | Low | Medium | Time-boxed, monitored, revoked immediately |
| Installation failure | Low | Low | Rollback procedures documented |
| Permission not revoked | Low | Medium | Explicit checklist step, verification command |
| Compromise during window | Very Low | Medium | < 30 minute exposure, audit logs |

**Overall Risk Level:** ⚠️ ACCEPTABLE (low likelihood, medium impact, strong mitigations)

---

## Worker Recommendation

**This bead should remain open** with status **WAITING FOR HUMAN ACTION**.

### Options for Human:

1. **Recommended:** Follow the 3-phase quick start (< 5 min human time)
2. **Alternative:** Manually install ArgoCD yourself (15-20 min)
3. **Delegate:** Assign to another cluster-admin if you don't have access

### After Human Completes Installation:

1. **Close this bead** (bd-3f3) as completed
2. **Verify ArgoCD Application** is syncing botburrow-agents
3. **Unblock bd-3e3** (original GitOps deployment request)

---

## Files to Reference

### For Human Cluster-Admin
1. **PRIMARY:** `docs/cluster-admin/bd-fvs-permission-grant-checklist.md` - Step-by-step guide
2. **Alternative:** `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md` - Manual installation

### For Workers (After Human Grants Permissions)
1. **Installation Script:** `k8s/apexalgo-iad/argocd/install.sh` - Automated deployment
2. **Manifests:** `k8s/apexalgo-iad/argocd/*.yaml` - All ArgoCD resources

---

## Related Beads

- **bd-fvs** - CLOSED (preparation work complete)
- **bd-13z** - CLOSED (duplicate, consolidated into bd-3f3)
- **bd-3e3** - BLOCKED (original GitOps deployment request, waiting for bd-3f3)

---

## Worker Notes

This assessment confirms that:

1. ✅ All worker preparation tasks are complete
2. ✅ All documentation is comprehensive and accurate
3. ✅ The cluster is in expected state (healthy, but no ArgoCD)
4. ❌ Workers cannot proceed due to correct RBAC restrictions
5. ⏳ Human cluster-admin action is required to unblock

**Status:** Ready for human action. No further worker tasks possible until permissions are granted.

---

**Document Version:** 1.0
**Created:** 2026-02-16
**Author:** Claude Worker (claude-code-glm-47-lima)
**Bead:** bd-3f3
**Assessment Type:** Worker Capability Check
