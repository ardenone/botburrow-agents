# ArgoCD Permission Management Scripts

## Overview
These scripts manage temporary cluster-admin permissions for ArgoCD installation in apexalgo-iad cluster.

**Related Bead:** bd-fvs (CLUSTER-ADMIN: Grant permissions to install ArgoCD in apexalgo-iad)

## Scripts

### 1. grant-argocd-permissions.sh
Grants temporary cluster-admin to devpod-observer ServiceAccount.

**Usage:**
```bash
# Run with cluster-admin credentials on apexalgo-iad
./scripts/grant-argocd-permissions.sh
```

**What it does:**
- Creates ClusterRoleBinding: `devpod-observer-cluster-admin`
- Grants cluster-admin role to `devpod-observer:devpod-observer`
- Verifies the grant

**Duration:** < 1 minute

### 2. revoke-argocd-permissions.sh
Revokes cluster-admin after ArgoCD installation completes.

**Usage:**
```bash
# Run after ArgoCD installation completes (< 30 minutes)
./scripts/revoke-argocd-permissions.sh
```

**What it does:**
- Verifies ArgoCD is installed (namespace + pods)
- Deletes ClusterRoleBinding: `devpod-observer-cluster-admin`
- Verifies revocation
- Tests that permissions are correctly removed

**Duration:** < 1 minute

## Complete Workflow

### Phase 1: Grant Permissions (Human Administrator)
```bash
# 1. Connect to apexalgo-iad with cluster-admin
export KUBECONFIG=~/.kube/apexalgo-iad-admin.kubeconfig

# 2. Grant permissions
./scripts/grant-argocd-permissions.sh
```

### Phase 2: Installation (Autonomous Workers)
Workers automatically:
1. Create ArgoCD namespace
2. Install ArgoCD manifests
3. Apply ArgoCD Application for botburrow-agents
4. Verify sync status

**Timeline:** 5-10 minutes

### Phase 3: Revoke Permissions (Human Administrator)
```bash
# 1. Verify installation complete
kubectl get pods -n argocd
kubectl get application botburrow-agents -n argocd

# 2. Revoke permissions
./scripts/revoke-argocd-permissions.sh
```

## Security Model

### Before Grant
```bash
# devpod-observer has read-only access
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Returns: no
```

### During Installation (< 30 minutes)
```bash
# devpod-observer has cluster-admin
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Returns: yes
```

### After Revocation
```bash
# devpod-observer has read-only access again
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Returns: no
```

## Verification Commands

### Check Current Permission State
```bash
# Check for cluster-admin binding
kubectl get clusterrolebinding devpod-observer-cluster-admin

# Test namespace creation permission
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
```

### Monitor Installation Progress
```bash
# Watch ArgoCD installation
watch -n 5 'kubectl get namespace argocd; kubectl get pods -n argocd'

# Check Application status
kubectl get application botburrow-agents -n argocd -o yaml
```

### Verify Complete Installation
```bash
# All-in-one verification
kubectl get namespace argocd && \
kubectl get pods -n argocd && \
kubectl get application botburrow-agents -n argocd && \
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer | grep -q "no" && \
echo "✅ Installation complete and permissions revoked"
```

## Troubleshooting

### Grant Script Fails
**Error:** `clusterrolebindings.rbac.authorization.k8s.io "devpod-observer-cluster-admin" already exists`

**Solution:**
```bash
# Binding already exists, verify it's correct
kubectl get clusterrolebinding devpod-observer-cluster-admin -o yaml

# If incorrect, delete and recreate
kubectl delete clusterrolebinding devpod-observer-cluster-admin
./scripts/grant-argocd-permissions.sh
```

### Revoke Script Fails - ArgoCD Not Found
**Error:** `ArgoCD namespace does not exist`

**Cause:** Installation not yet complete

**Solution:**
```bash
# Wait for workers to complete installation
kubectl get namespace argocd
kubectl get pods -n argocd

# Retry revocation when ready
./scripts/revoke-argocd-permissions.sh
```

### Permissions Not Working After Grant
**Error:** Workers still can't create namespaces

**Diagnosis:**
```bash
# 1. Verify ClusterRoleBinding exists
kubectl get clusterrolebinding devpod-observer-cluster-admin

# 2. Check binding details
kubectl get clusterrolebinding devpod-observer-cluster-admin -o yaml

# 3. Test permission directly
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
```

**Common Issues:**
- ServiceAccount name typo (should be `devpod-observer:devpod-observer`)
- Namespace typo (should be `devpod-observer` namespace)
- RBAC caching delay (wait 30 seconds and retry)

## Timeline Reference

| Phase | Duration | Actions |
|-------|----------|---------|
| Grant permissions | < 1 min | Run grant script |
| Worker installation | 5-10 min | Automatic |
| Verify installation | 1-2 min | Check pods/apps |
| Revoke permissions | < 1 min | Run revoke script |
| **TOTAL** | **< 15 min** | **Complete workflow** |

## Related Documentation
- Permission grant instructions: `docs/resolutions/bd-fvs-permission-grant-instructions.md`
- Verification status: `docs/resolutions/bd-fvs-verification-status.md`
- ArgoCD deployment guide: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
- Parent bead: bd-3f3 (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad for GitOps deployment)
