# CLUSTER-ADMIN CHECKLIST: Grant Permissions for ArgoCD Installation

**Bead ID:** bd-fvs
**Status:** ⏳ AWAITING HUMAN ACTION
**Date:** 2026-02-15
**Estimated Time:** < 5 minutes

---

## Executive Summary

This checklist guides a **human cluster-administrator** through granting temporary cluster-admin permissions to the `devpod-observer` ServiceAccount in the **apexalgo-iad** cluster. This enables automated workers to install ArgoCD and complete GitOps deployment for botburrow-agents.

**Why this approach?**
- ✅ **Fast:** Installation completes in < 5 minutes after permissions granted
- ✅ **Secure:** Time-boxed elevation (< 30 minutes), revoked immediately after
- ✅ **Autonomous:** Workers handle installation without ongoing human intervention
- ✅ **Low Risk:** devpod-observer already has extensive read permissions cluster-wide

---

## Prerequisites

- [x] Cluster-admin access to **apexalgo-iad** Kubernetes cluster
- [x] kubectl configured with cluster-admin context
- [x] Familiarity with Kubernetes RBAC concepts

---

## Current State Verification

Before proceeding, verify the current state:

```bash
# 1. Verify botburrow-agents namespace exists
kubectl get namespace botburrow-agents
# Expected: Active for 13 days

# 2. Verify ArgoCD namespace does NOT exist
kubectl get namespace argocd
# Expected: Error from server (NotFound)

# 3. Verify devpod-observer ServiceAccount exists
kubectl get serviceaccount devpod-observer -n devpod-observer
# Expected: devpod-observer exists

# 4. Verify devpod-observer LACKS cluster-admin permissions
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no

# 5. Verify cluster-admin binding does NOT exist
kubectl get clusterrolebinding devpod-observer-cluster-admin
# Expected: Error from server (NotFound)
```

**Expected Results:**
- ✅ botburrow-agents namespace: **Active** (13 days old, 13 healthy pods)
- ❌ argocd namespace: **NotFound**
- ✅ devpod-observer ServiceAccount: **Exists**
- ❌ devpod-observer permissions: **Cannot create namespaces**
- ❌ cluster-admin binding: **NotFound**

---

## Phase 1: Grant Temporary Cluster-Admin ⚡ CRITICAL

**⏱ Duration:** < 1 minute

```bash
# Connect to apexalgo-iad with cluster-admin credentials
# (Use your preferred method: kubectl config, kubeconfig file, etc.)

# Grant cluster-admin to devpod-observer ServiceAccount
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# Verify binding was created
kubectl get clusterrolebinding devpod-observer-cluster-admin

# Verify permissions are now granted
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes
```

**Success Criteria:**
- ✅ ClusterRoleBinding `devpod-observer-cluster-admin` exists
- ✅ `kubectl auth can-i create namespace` returns **yes** for devpod-observer

---

## Phase 2: Monitor Worker Installation 👀

**⏱ Duration:** 5-10 minutes (automated by workers)

Workers with access to apexalgo-iad kubectl will automatically:
1. Create ArgoCD namespace
2. Install ArgoCD CRDs and components
3. Apply ArgoCD Application for botburrow-agents
4. Verify sync status

**Monitoring Commands:**

```bash
# Watch for ArgoCD namespace creation
kubectl get namespace argocd -w

# Once namespace exists, monitor ArgoCD pods
kubectl get pods -n argocd -w

# Check ArgoCD Application creation
kubectl get applications.argoproj.io -n argocd

# Monitor botburrow-agents sync status
kubectl get application botburrow-agents -n argocd -o yaml
```

**Expected Timeline:**
- **T+0 min:** ArgoCD namespace created
- **T+2 min:** ArgoCD pods starting (7-8 pods)
- **T+5 min:** All ArgoCD pods Running
- **T+7 min:** ArgoCD Application created
- **T+10 min:** botburrow-agents synced

**Success Indicators:**
- ✅ ArgoCD namespace exists
- ✅ 7-8 ArgoCD pods in Running state
- ✅ ArgoCD Application `botburrow-agents` in Synced/Healthy state

---

## Phase 3: Revoke Cluster-Admin 🔒 CRITICAL

**⏱ Duration:** < 1 minute
**⚠️ IMPORTANT:** Execute this step immediately after ArgoCD installation completes!

```bash
# Verify ArgoCD is fully installed before revoking
kubectl get pods -n argocd
# All pods should be Running

kubectl get application botburrow-agents -n argocd
# Should show Synced/Healthy

# Revoke cluster-admin binding
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Verify deletion
kubectl get clusterrolebinding devpod-observer-cluster-admin
# Expected: Error from server (NotFound)

# Verify permissions are revoked
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no
```

**Success Criteria:**
- ✅ ClusterRoleBinding `devpod-observer-cluster-admin` deleted
- ✅ `kubectl auth can-i create namespace` returns **no** for devpod-observer
- ✅ ArgoCD remains functional (pods still Running)

---

## Phase 4: Verify GitOps Deployment ✅

**⏱ Duration:** < 2 minutes

```bash
# Check ArgoCD Application status
kubectl get application botburrow-agents -n argocd

# Verify all resources are synced
kubectl get all -n botburrow-agents

# Check ArgoCD UI (optional)
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open https://localhost:8080
# Login: admin / (get password with next command)

# Get ArgoCD admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

**Expected Results:**
- ✅ Application `botburrow-agents` shows **Synced** and **Healthy**
- ✅ All resources in `botburrow-agents` namespace are managed by ArgoCD
- ✅ ArgoCD UI accessible and shows Application

---

## Security Model

### Permission Elevation Details
- **ServiceAccount:** `devpod-observer` in `devpod-observer` namespace
- **ClusterRole:** `cluster-admin` (full cluster privileges)
- **Duration:** < 30 minutes (only during ArgoCD installation)
- **Audit:** All kubectl operations logged in Kubernetes audit logs
- **Rollback:** Simple - delete ClusterRoleBinding

### Why This Is Safe
1. **devpod-observer already has extensive read permissions** across the entire cluster
2. **Time-boxed elevation:** Permissions revoked immediately after installation
3. **Single-purpose:** Only used for ArgoCD installation, no other operations
4. **Auditable:** All actions logged in cluster audit logs
5. **Reversible:** ClusterRoleBinding can be deleted instantly

### Risk Assessment
- **Risk Level:** ⚠️ MEDIUM (temporary cluster-admin access)
- **Mitigation:** Time-boxed (< 30 minutes), monitored, immediately revoked
- **Impact if compromised:** Limited to ArgoCD installation window
- **Recovery:** Delete ClusterRoleBinding, rollback ArgoCD if needed

---

## Troubleshooting

### Workers Not Installing ArgoCD

**Symptom:** 10+ minutes passed, ArgoCD namespace still doesn't exist

**Investigation:**
```bash
# Check if workers can see the permissions
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer

# Check for worker pods in ardenone-cluster
kubectl get pods -n devpod --context=ardenone-cluster | grep claude-code

# Check kubectl-proxy connectivity
kubectl get pods -n devpod-observer -l app=kubectl-proxy
```

**Resolution:**
- If `auth can-i` returns `no`, re-run Phase 1
- If no worker pods exist, trigger worker manually
- If kubectl-proxy is down, check Tailscale connectivity

### ClusterRoleBinding Already Exists

**Symptom:** `kubectl create clusterrolebinding` fails with "already exists"

**Investigation:**
```bash
# Check existing binding
kubectl get clusterrolebinding devpod-observer-cluster-admin -o yaml
```

**Resolution:**
- If binding is correct, skip Phase 1 and proceed to Phase 2
- If binding is incorrect, delete and recreate:
  ```bash
  kubectl delete clusterrolebinding devpod-observer-cluster-admin
  kubectl create clusterrolebinding devpod-observer-cluster-admin \
    --clusterrole=cluster-admin \
    --serviceaccount=devpod-observer:devpod-observer
  ```

### ArgoCD Installation Fails

**Symptom:** ArgoCD pods crash or fail to start

**Investigation:**
```bash
# Check pod status
kubectl get pods -n argocd

# Check pod logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server --tail=50

# Check events
kubectl get events -n argocd --sort-by='.lastTimestamp'
```

**Resolution:**
- Check resource availability (CPU, memory)
- Check for conflicting CRDs
- Verify network policies allow ArgoCD communication
- See full troubleshooting guide: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`

### Cannot Revoke Permissions

**Symptom:** `kubectl delete clusterrolebinding` fails

**Investigation:**
```bash
# Check if binding exists
kubectl get clusterrolebinding devpod-observer-cluster-admin

# Check if binding is being used
kubectl get pods -n argocd -o yaml | grep serviceAccountName
```

**Resolution:**
- Ensure ArgoCD is fully installed before revoking
- If deletion fails, use `--force` flag:
  ```bash
  kubectl delete clusterrolebinding devpod-observer-cluster-admin --force
  ```

---

## Alternative Approaches (Not Recommended)

### Option A: Manual ArgoCD Installation
- ❌ Requires 15-20 minutes of human time
- ❌ Manual steps prone to errors
- ❌ Blocks autonomous workflow
- See: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md` for full steps

### Option B: Create Dedicated ArgoCD-Installer ServiceAccount
- ❌ Most complex setup
- ❌ Still requires cluster-admin to create
- ❌ Overhead for one-time operation
- See: `docs/resolutions/bd-3f3-argocd-installation-plan.md` for RBAC manifests

---

## Success Checklist

Before closing this bead, verify:

- [ ] Phase 1: Cluster-admin binding created
- [ ] Phase 2: ArgoCD installed and running
- [ ] Phase 3: Cluster-admin binding deleted
- [ ] Phase 4: GitOps deployment verified
- [ ] ArgoCD Application `botburrow-agents` is Synced/Healthy
- [ ] All botburrow-agents pods are Running
- [ ] devpod-observer permissions revoked (cannot create namespaces)

---

## References

- **Parent Bead:** bd-3f3 (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad for GitOps deployment)
- **Related Beads:**
  - bd-3e3 (Create ArgoCD GitOps deployment for botburrow-agents)
  - bd-2o4 (Install and configure ArgoCD)
  - bd-13z (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad cluster - CLOSED duplicate)
- **Documentation:**
  - Full deployment guide: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
  - Permission instructions: `docs/resolutions/bd-fvs-permission-grant-instructions.md`
  - RBAC configuration: `cluster-configuration/apexalgo-iad/devpod-observer/rbac.yml`
- **ArgoCD Resources:**
  - ArgoCD Documentation: https://argo-cd.readthedocs.io/
  - ArgoCD Installation: https://argo-cd.readthedocs.io/en/stable/getting_started/

---

## Timeline Estimate

| Phase | Duration | Type |
|-------|----------|------|
| Phase 1: Grant Permissions | < 1 minute | Human |
| Phase 2: Monitor Installation | 5-10 minutes | Automated |
| Phase 3: Revoke Permissions | < 1 minute | Human |
| Phase 4: Verify Deployment | < 2 minutes | Human |
| **Total** | **< 15 minutes** | **Mixed** |

---

**Document Version:** 1.0
**Created:** 2026-02-15
**Author:** Claude Worker (claude-code-glm-47-lima)
**Bead:** bd-fvs
