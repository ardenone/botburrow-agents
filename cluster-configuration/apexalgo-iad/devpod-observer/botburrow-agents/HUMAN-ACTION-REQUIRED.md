# 🚨 HUMAN ACTION REQUIRED - Install ArgoCD in apexalgo-iad

**Bead:** bd-3f3
**Priority:** P0 CRITICAL (blocks bd-3e3 - GitOps deployment)
**Required Role:** cluster-admin access to apexalgo-iad cluster
**Estimated Time:** < 15 minutes total (< 5 minutes human active time)

## TL;DR - What You Need to Do

Grant temporary cluster-admin permissions to devpod-observer ServiceAccount, monitor automated ArgoCD installation by workers, then revoke permissions.

## Quick Start (Copy-Paste)

**⚠️ CRITICAL:** Do NOT use `/home/coder/.kube/apexalgo-iad.kubeconfig` (read-only devpod kubeconfig)
**✅ USE:** Your personal cluster-admin kubeconfig for apexalgo-iad cluster

```bash
# PHASE 1: Grant cluster-admin (< 1 minute)
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig

# Verify you have cluster-admin permissions
kubectl auth can-i create clusterrolebinding
# Expected: yes

# Grant temporary cluster-admin to devpod-observer
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# PHASE 2: Monitor automated ArgoCD installation (5-10 minutes)
kubectl get namespace argocd -w
# Wait for namespace to appear, then Ctrl+C

kubectl get pods -n argocd -w
# Wait for all 7-8 pods to be Running, then Ctrl+C

# PHASE 3: Revoke cluster-admin (< 1 minute) ⚠️ CRITICAL
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Verify revocation
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no
```

## Why This Is Needed

Workers cannot install ArgoCD because it requires cluster-admin permissions to create namespaces, CRDs, and cluster-level RBAC resources. The devpod-observer ServiceAccount has read-only access by design.

**What This Unblocks:**
- ✅ bd-3e3 - Create ArgoCD GitOps deployment for botburrow-agents
- ✅ GitOps-based deployment automation for all future changes
- ✅ Autonomous worker management of Kubernetes resources

## What This Process Does

### Phase 1: Grant Temporary Cluster-Admin
- Creates ClusterRoleBinding for devpod-observer ServiceAccount
- Grants cluster-admin privileges (time-boxed to installation window)

### Phase 2: Automated ArgoCD Installation (Workers)
- Workers detect elevated permissions and automatically:
  - Create ArgoCD namespace
  - Install ArgoCD CRDs and components (7-8 pods)
  - Apply ArgoCD Application for botburrow-agents
  - Verify sync status

### Phase 3: Revoke Cluster-Admin
- Deletes ClusterRoleBinding (instant revocation)
- devpod-observer returns to read-only permissions
- ArgoCD continues running (unaffected)

## Security Review

**Is this safe?** ✅ YES (with time-boxed elevation)

- ✅ **Time-boxed:** Cluster-admin only during installation (< 30 minutes)
- ✅ **Revocable:** Delete ClusterRoleBinding instantly revokes permissions
- ✅ **Monitored:** All actions logged in Kubernetes audit logs
- ✅ **Auditable:** devpod-observer actions traceable to this bead (bd-3f3)
- ✅ **Limited Scope:** Only used for ArgoCD installation
- ⚠️ **Medium Risk:** Temporary cluster-admin access (mitigated by immediate revocation)

## Expected Output

**Phase 1 - Grant Permissions:**
```
clusterrolebinding.rbac.authorization.k8s.io/devpod-observer-cluster-admin created
yes
```

**Phase 2 - Monitor Installation:**
```
# After 1-2 minutes:
namespace/argocd created

# After 5-7 minutes:
NAME                                               READY   STATUS    AGE
argocd-application-controller-0                    1/1     Running   2m
argocd-applicationset-controller-xxx               1/1     Running   2m
argocd-dex-server-xxx                              1/1     Running   2m
argocd-notifications-controller-xxx                1/1     Running   2m
argocd-redis-xxx                                   1/1     Running   2m
argocd-repo-server-xxx                             1/1     Running   2m
argocd-server-xxx                                  1/1     Running   2m
```

**Phase 3 - Revoke Permissions:**
```
clusterrolebinding.rbac.authorization.k8s.io "devpod-observer-cluster-admin" deleted
Error from server (NotFound): clusterrolebindings.rbac.authorization.k8s.io "devpod-observer-cluster-admin" not found
no
```

## Verification Commands

```bash
# Verify ArgoCD is installed
kubectl get namespace argocd
kubectl get pods -n argocd
# All pods should be Running

# Verify ArgoCD Application exists
kubectl get application botburrow-agents -n argocd
# Should show: Synced / Healthy

# Verify permissions were revoked
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Should return: no

# Optional: Get ArgoCD admin password for UI access
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

## After You Apply

Close the beads to mark this work complete:

```bash
# From botburrow-agents repository
cd /home/coder/botburrow-agents

# Close both beads
br close bd-1qs --status completed
br close bd-33d --status completed

# Sync and commit
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs,bd-33d): cluster-admin applied RBAC manifests

Applied RBAC roles for devpod-observer in botburrow-agents namespace:
- secrets-manager (get/list/patch/update secrets)
- deployment-scaler (scale deployments, manage HPAs)

Unblocks: bd-12r, bd-2jm, bd-3o6

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

Workers will automatically resume blocked beads (bd-2jm, bd-3o6) once permissions are verified.

## Need Help?

See detailed instructions: `CLUSTER-ADMIN-INSTRUCTIONS.md` in this directory
