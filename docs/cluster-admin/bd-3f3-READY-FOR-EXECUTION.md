# bd-3f3: READY FOR CLUSTER-ADMIN EXECUTION

**Status:** ✅ ALL PREPARATION COMPLETE - READY FOR IMMEDIATE EXECUTION
**Date:** 2026-02-16
**Estimated Human Time:** < 5 minutes
**Estimated Total Time:** < 15 minutes (mostly automated)

---

## Executive Summary

All worker preparation is COMPLETE. This bead is ready for a human cluster administrator to execute a simple 3-phase process:

1. **Grant** cluster-admin to `devpod-observer` ServiceAccount (1 command, < 1 min)
2. **Monitor** workers installing ArgoCD automatically (watch mode, 5-10 min)
3. **Revoke** cluster-admin permissions (1 command, < 1 min)

**Why This Approach?**
- ✅ **Minimal Human Time:** < 5 minutes active work (rest is automated monitoring)
- ✅ **Secure:** Time-boxed elevation, revoked immediately after installation
- ✅ **Simple:** 2 kubectl commands from a human cluster-admin
- ✅ **Autonomous:** Workers handle all installation complexity
- ✅ **Auditable:** All actions logged in Kubernetes audit logs

---

## Prerequisites Verification

**Current State (Verified 2026-02-16):**

✅ **botburrow-agents namespace exists:**
```bash
$ kubectl get namespace botburrow-agents
NAME               STATUS   AGE
botburrow-agents   Active   14d
```

✅ **13 healthy pods running:**
```bash
$ kubectl get pods -n botburrow-agents
NAME                                    READY   STATUS    RESTARTS   AGE
coordinator-644b76d7bd-89trf            1/1     Running   0          23h
coordinator-644b76d7bd-pwlft            1/1     Running   0          23h
coordinator-git-sync-79db4b749c-4dz6d   2/2     Running   0          23h
runner-hybrid-5f958ddfb5-68tc2          1/1     Running   0          23h
valkey-d4fc4c84d-ttdzw                  1/1     Running   0          4d21h
... (13 pods total)
```

✅ **devpod-observer ServiceAccount exists:**
```bash
$ kubectl get serviceaccount devpod-observer -n devpod-observer
NAME              SECRETS   AGE
devpod-observer   0         32d
```

✅ **ArgoCD manifests prepared:**
```bash
$ ls -1 k8s/apexalgo-iad/argocd/
applicationset.yaml
DEPLOYMENT-GUIDE.md
ingress.yaml
install.sh
install.yaml
kustomization.yaml
namespace.yaml
README.md
```

❌ **ArgoCD namespace does NOT exist (expected):**
```bash
$ kubectl get namespace argocd
Error from server (NotFound): namespaces "argocd" not found
```

❌ **cluster-admin binding does NOT exist (expected):**
```bash
$ kubectl get clusterrolebinding devpod-observer-cluster-admin
Error from server (NotFound): clusterrolebindings.rbac.authorization.k8s.io "devpod-observer-cluster-admin" not found
```

---

## Pre-Flight Verification (Optional but Recommended)

Before executing the commands below, run this verification script to ensure all prerequisites are met:

```bash
cd /home/coder/botburrow-agents
./docs/cluster-admin/bd-3f3-VERIFY-READY.sh
```

This will check:
- ✓ You have cluster-admin permissions
- ✓ All required namespaces and ServiceAccounts exist
- ✓ ArgoCD namespace does NOT exist yet (as expected)
- ✓ All manifests are present
- ✓ kubectl-proxy is accessible (optional)

---

## Quick Start: Execute These Commands

### IMPORTANT: Cluster Access Requirements

**❌ DO NOT USE** the devpod kubeconfig at `/home/coder/.kube/apexalgo-iad.kubeconfig`
- This kubeconfig uses the `devpod-observer` ServiceAccount (read-only)
- It CANNOT create ClusterRoleBindings or install ArgoCD

**✅ USE** your personal cluster-admin kubeconfig for apexalgo-iad:
- You need TRUE cluster-admin credentials
- This might be in your local `~/.kube/config` or a separate kubeconfig file
- Verify with: `kubectl auth can-i create clusterrolebinding`

---

### Phase 1: Grant Cluster-Admin (< 1 minute)

```bash
# CRITICAL: Use YOUR cluster-admin kubeconfig, NOT the devpod kubeconfig!
# Set your cluster-admin context
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig
# OR: kubectl config use-context apexalgo-iad-admin

# Verify you have cluster-admin permissions
kubectl auth can-i create clusterrolebinding
# Expected output: yes

# Grant temporary cluster-admin to devpod-observer ServiceAccount
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# Verify binding was created
kubectl get clusterrolebinding devpod-observer-cluster-admin

# Verify permissions granted
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected output: yes
```

**Success Criteria:**
- ✅ ClusterRoleBinding `devpod-observer-cluster-admin` exists
- ✅ devpod-observer can create namespaces

---

### Phase 2: Monitor Worker Installation (5-10 minutes, automated)

**What Happens Automatically:**
1. Workers detect elevated permissions
2. Create ArgoCD namespace
3. Install ArgoCD CRDs and components (7-8 pods)
4. Apply ArgoCD Application for botburrow-agents
5. Verify sync status

**Monitoring Commands:**

```bash
# Watch for ArgoCD namespace creation (may take 1-2 minutes)
kubectl get namespace argocd -w

# Once namespace exists, monitor ArgoCD pods
kubectl get pods -n argocd -w

# Expected timeline:
# T+0 min: namespace/argocd created
# T+2 min: ArgoCD pods starting (ContainerCreating)
# T+5 min: All pods Running (7-8 pods)
# T+7 min: ArgoCD Application created
# T+10 min: botburrow-agents synced

# Check ArgoCD Application (once pods are Running)
kubectl get applications.argoproj.io -n argocd

# Expected output:
# NAME                SYNC STATUS   HEALTH STATUS
# botburrow-agents    Synced        Healthy
```

**Success Indicators:**
- ✅ ArgoCD namespace exists
- ✅ 7-8 ArgoCD pods in Running state
- ✅ ArgoCD Application `botburrow-agents` shows Synced/Healthy

**Troubleshooting:**
- If namespace doesn't appear after 5 minutes, workers may be offline
- Check kubectl-proxy connectivity: `kubectl get pods -n devpod-observer -l app=kubectl-proxy`
- See detailed troubleshooting: `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`

---

### Phase 3: Revoke Cluster-Admin (< 1 minute) ⚠️ CRITICAL

**⚠️ EXECUTE IMMEDIATELY AFTER ARGOCD INSTALLATION COMPLETES**

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

# Verify permissions revoked
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no
```

**Success Criteria:**
- ✅ ClusterRoleBinding deleted
- ✅ devpod-observer CANNOT create namespaces
- ✅ ArgoCD remains functional (pods still Running)

---

## Verification

After all phases complete, verify GitOps deployment:

```bash
# Check ArgoCD Application status
kubectl get application botburrow-agents -n argocd

# Verify all resources are synced
kubectl get all -n botburrow-agents

# Get ArgoCD admin password (optional - for UI access)
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d

# Port-forward to ArgoCD UI (optional)
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open https://localhost:8080
# Login: admin / <password from above>
```

**Expected Results:**
- ✅ Application `botburrow-agents` is Synced and Healthy
- ✅ All resources in `botburrow-agents` namespace are managed by ArgoCD
- ✅ ArgoCD UI accessible (optional)

---

## Security Model

### Permission Elevation Details
- **ServiceAccount:** `devpod-observer` in `devpod-observer` namespace
- **ClusterRole:** `cluster-admin` (full cluster privileges)
- **Duration:** < 30 minutes (only during ArgoCD installation)
- **Audit:** All kubectl operations logged in Kubernetes audit logs
- **Rollback:** Simple - delete ClusterRoleBinding

### Why This Is Safe
1. **devpod-observer already has extensive read permissions** across the cluster
2. **Time-boxed elevation:** Permissions revoked immediately after installation
3. **Single-purpose:** Only used for ArgoCD installation
4. **Auditable:** All actions logged in cluster audit logs
5. **Reversible:** ClusterRoleBinding can be deleted instantly

### Risk Assessment
- **Risk Level:** ⚠️ MEDIUM (temporary cluster-admin access)
- **Mitigation:** Time-boxed (< 30 minutes), monitored, immediately revoked
- **Impact if compromised:** Limited to ArgoCD installation window
- **Recovery:** Delete ClusterRoleBinding, rollback ArgoCD if needed

---

## Timeline Estimate

| Phase | Duration | Type | Actions |
|-------|----------|------|---------|
| Phase 1: Grant Permissions | < 1 minute | Human | 1 kubectl create command |
| Phase 2: Monitor Installation | 5-10 minutes | Automated | Watch mode (kubectl get -w) |
| Phase 3: Revoke Permissions | < 1 minute | Human | 1 kubectl delete command |
| **Total** | **< 15 minutes** | **Mixed** | **2 kubectl commands** |

**Human Active Time:** < 5 minutes (2 commands + verification)
**Automated Time:** 5-10 minutes (workers install ArgoCD)

---

## After Completion

### Close This Bead

```bash
# From repository: /home/coder/botburrow-agents
cd /home/coder/botburrow-agents

# Close bead bd-3f3
br close bd-3f3 --status completed

# Sync beads to JSONL
br sync --flush-only

# Commit bead status update
git add .beads/*.jsonl
git commit -m "chore(bd-3f3): cluster-admin installed ArgoCD in apexalgo-iad

Phases completed:
1. Granted temporary cluster-admin to devpod-observer ServiceAccount
2. Workers installed ArgoCD (7 pods Running, Healthy)
3. Revoked cluster-admin permissions
4. Verified GitOps deployment (botburrow-agents Synced/Healthy)

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

### Unblocked Beads

This will automatically unblock:
- **bd-3e3** - Create ArgoCD GitOps deployment for botburrow-agents
- Any downstream beads depending on ArgoCD

---

## Documentation References

### Primary Reference
- **Cluster-Admin Checklist:** `docs/cluster-admin/bd-fvs-permission-grant-checklist.md`
  - Complete step-by-step guide with troubleshooting
  - Alternative approaches (not recommended)
  - Detailed security model

### Supporting Documentation
- **Worker Assessment:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/FINAL-STATUS.md`
  - Worker verification results (2026-02-16)
  - Proof that workers cannot proceed without cluster-admin
- **Deployment Guide:** `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
  - Full ArgoCD installation guide
  - Manual installation steps (if needed)
  - Troubleshooting section

### Related Beads
- **bd-fvs** - CLOSED - Worker preparation bead (verification complete)
- **bd-13z** - CLOSED - Duplicate bead (consolidated into bd-3f3)
- **bd-3e3** - BLOCKED by bd-3f3 - GitOps deployment (will unblock after this)

---

## Troubleshooting

### Problem: "AlreadyExists" error when creating ClusterRoleBinding

**Symptom:**
```
Error from server (AlreadyExists): clusterrolebindings.rbac.authorization.k8s.io "devpod-observer-cluster-admin" already exists
```

**Resolution:**
```bash
# Binding already exists - skip Phase 1, proceed to Phase 2
kubectl get clusterrolebinding devpod-observer-cluster-admin
```

---

### Problem: Workers not installing ArgoCD after 10+ minutes

**Investigation:**
```bash
# Check if workers can see the permissions
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer

# Check kubectl-proxy connectivity
kubectl get pods -n devpod-observer -l app=kubectl-proxy

# Check for worker pods in ardenone-cluster (if you have access)
kubectl get pods -n devpod --context=ardenone-cluster | grep claude-code
```

**Resolution:**
- If `auth can-i` returns `no`, re-run Phase 1
- If kubectl-proxy is down, check Tailscale connectivity
- If no worker pods exist, manually trigger worker or install ArgoCD manually (see DEPLOYMENT-GUIDE.md)

---

### Problem: ArgoCD pods crashing or failing to start

**Investigation:**
```bash
# Check pod status
kubectl get pods -n argocd

# Check pod logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server --tail=50

# Check events
kubectl get events -n argocd --sort-by='.lastTimestamp' | tail -20
```

**Resolution:**
- Check resource availability (CPU, memory)
- Check for conflicting CRDs
- Verify network policies allow ArgoCD communication
- See full troubleshooting: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`

---

### Problem: Cannot revoke permissions (delete fails)

**Investigation:**
```bash
# Check if binding exists
kubectl get clusterrolebinding devpod-observer-cluster-admin

# Try force delete
kubectl delete clusterrolebinding devpod-observer-cluster-admin --force --grace-period=0
```

---

## Alternative Approaches (Not Recommended)

### Option A: Manual ArgoCD Installation by Human
- ❌ Requires 15-20 minutes of human time
- ❌ Manual steps prone to errors
- ❌ Blocks autonomous workflow
- See: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`

### Option B: Create Dedicated ArgoCD-Installer ServiceAccount
- ❌ Most complex setup (requires creating RBAC manifests)
- ❌ Still requires cluster-admin to create
- ❌ Overhead for one-time operation
- See: `docs/resolutions/bd-3f3-argocd-installation-plan.md`

**Recommended:** Use the simple 3-phase approach outlined above.

---

## Success Checklist

Before closing bead bd-3f3, verify ALL items:

- [ ] Phase 1: Cluster-admin binding created successfully
- [ ] Phase 2: ArgoCD namespace exists
- [ ] Phase 2: All ArgoCD pods (7-8) are Running
- [ ] Phase 2: ArgoCD Application `botburrow-agents` exists
- [ ] Phase 3: Cluster-admin binding deleted successfully
- [ ] Phase 3: devpod-observer CANNOT create namespaces (permissions revoked)
- [ ] Verification: Application `botburrow-agents` is Synced and Healthy
- [ ] Verification: All botburrow-agents pods are Running
- [ ] Bead bd-3f3 closed with status=completed
- [ ] Bead status committed and pushed to GitHub

---

**Document Version:** 1.0
**Created:** 2026-02-16
**Author:** Claude Worker
**Bead:** bd-3f3
**Repository:** /home/coder/botburrow-agents
