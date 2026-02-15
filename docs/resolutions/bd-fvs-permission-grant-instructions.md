# bd-fvs: Grant Permissions to Install ArgoCD in apexalgo-iad

## Status: AWAITING CLUSTER-ADMIN ACTION

## Context
This bead tracks the specific permission-granting step required for ArgoCD installation in apexalgo-iad cluster. This is a sub-task of the parent human bead **bd-3f3** (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad for GitOps deployment).

## Current State (2026-02-15)
- ✅ botburrow-agents namespace exists with 13 healthy pods
- ✅ All ArgoCD manifests prepared in k8s/apexalgo-iad/argocd/
- ✅ Deployment guide ready: k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md
- ❌ ArgoCD namespace does not exist
- ❌ devpod-observer ServiceAccount lacks cluster-admin permissions
- ❌ Workers cannot create namespaces: `kubectl auth can-i create namespace` → no

## Recommended Approach: Temporary Cluster-Admin Grant

### Why This Approach?
1. **Speed:** Installation completes in < 5 minutes
2. **Autonomy:** Workers can complete installation without ongoing human intervention
3. **Security:** Time-boxed elevation (< 30 minutes), revoked immediately after
4. **Simplicity:** Single ClusterRoleBinding, easy rollback
5. **Low Risk:** devpod-observer already has read access to entire cluster

### Implementation Steps

**Phase 1: Grant Temporary Cluster-Admin (Human Administrator)**

Connect to apexalgo-iad cluster with cluster-admin credentials and run:

```bash
# Grant cluster-admin to devpod-observer ServiceAccount
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# Verify binding
kubectl get clusterrolebinding devpod-observer-cluster-admin
```

**Phase 2: Notify Workers (Human Administrator)**

Update bead bd-3f3 status to indicate permissions are granted:

```bash
# Notify workers via bead comment (if supported) or simply wait
# Workers monitoring bd-3f3 will detect the permission change
echo "✅ Permissions granted - workers can now install ArgoCD"
```

**Phase 3: Worker Installs ArgoCD (Automatic)**

Workers with access to apexalgo-iad kubectl will automatically:
1. Create ArgoCD namespace
2. Install ArgoCD manifests
3. Apply ArgoCD Application for botburrow-agents
4. Verify sync status

**Phase 4: Revoke Cluster-Admin (Human Administrator)**

After ArgoCD installation completes (verify with worker or check cluster):

```bash
# Revoke cluster-admin binding
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Verify deletion
kubectl get clusterrolebinding devpod-observer-cluster-admin
# Should return: Error from server (NotFound)
```

### Security Model
- **Duration:** < 30 minutes (only during installation)
- **Scope:** Limited to ArgoCD installation tasks
- **Audit:** All kubectl operations are logged
- **Rollback:** Simple - delete ClusterRoleBinding
- **Risk:** Minimal - devpod-observer already has extensive read permissions

### Verification Commands

After Phase 1 (verify permissions granted):
```bash
# From devpod with apexalgo-iad kubeconfig
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl auth can-i create namespace
# Should return: yes
```

After Phase 3 (verify ArgoCD installed):
```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get namespace argocd
kubectl get pods -n argocd
kubectl get application botburrow-agents -n argocd
```

After Phase 4 (verify permissions revoked):
```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl auth can-i create namespace
# Should return: no
```

## Alternative Approaches (Not Recommended)

### Option 2: Manual ArgoCD Installation by Cluster-Admin
- ❌ Requires 15-20 minutes of human time
- ❌ Manual steps prone to errors
- ❌ Blocks autonomous workflow
- See bd-3f3 for full manual installation steps

### Option 3: Create Dedicated ArgoCD-Installer ServiceAccount
- ❌ Most complex setup
- ❌ Still requires cluster-admin to create
- ❌ Overhead for one-time operation
- See docs/resolutions/bd-3f3-argocd-installation-plan.md for RBAC manifests

## Dependencies
- **Blocks:** bd-3f3 (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad for GitOps deployment)
- **Requires:** Human cluster-admin access to apexalgo-iad

## References
- Parent bead: bd-3f3
- Comprehensive analysis: docs/resolutions/bd-3f3-argocd-installation-plan.md
- Installation guide: k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md
- RBAC configuration: cluster-configuration/apexalgo-iad/devpod-observer/rbac.yml

## Timeline
- Created: 2026-02-15
- Status: Awaiting human cluster-admin action
- Expected resolution: < 5 minutes after permissions granted
