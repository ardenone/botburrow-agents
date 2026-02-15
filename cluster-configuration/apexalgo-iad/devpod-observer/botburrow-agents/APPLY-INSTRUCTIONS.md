# RBAC Application Instructions for Cluster Admin

**Status:** ✅ **READY TO APPLY**
**Date:** 2026-02-15
**Bead:** bd-1qs (CLUSTER-ADMIN: Apply RBAC manifests for devpod-observer in botburrow-agents namespace)
**Cluster:** apexalgo-iad

---

## Summary

The devpod-observer ServiceAccount needs RBAC permissions to access the botburrow-agents namespace. Two minimal-permission RBAC manifests are ready to apply, but require **cluster-admin access** to apexalgo-iad.

---

## Manifests to Apply

### 1. Secrets Manager Role
**File:** `secrets-manager-role.yml`
**Purpose:** Grant devpod-observer permission to read/update secrets in botburrow-agents namespace
**Required for:** bd-2jm (Hub API authentication fix)
**Permissions:** `get`, `list`, `patch`, `update` on secrets

### 2. Deployment Scaler Role
**File:** `deployment-scaler-role.yml`
**Purpose:** Grant devpod-observer permission to scale deployments and manage HPAs
**Required for:** bd-3o6 (Runner scaling tests)
**Permissions:**
- `get`, `patch`, `update` on deployments/scale
- `get`, `list`, `watch` on deployments, pods, replicasets
- `get`, `list`, `watch`, `patch`, `update` on HPAs
- `create`, `get` on pods/portforward (for Valkey testing)

---

## Application Commands

### Prerequisites
- Access to cluster-admin kubeconfig for **apexalgo-iad** cluster
- Manifests are in this directory

### Apply Both Manifests
```bash
# Navigate to manifest directory
cd cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# Apply secrets-manager role and binding
kubectl apply -f secrets-manager-role.yml

# Apply deployment-scaler role and binding
kubectl apply -f deployment-scaler-role.yml
```

### Verification
```bash
# Test secrets access
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

kubectl auth can-i patch secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

# Test deployment scaling access
kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

kubectl auth can-i create pods/portforward -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes
```

---

## Security Review

### Secrets Manager Permissions
✅ **Minimal scope** - Only secrets in botburrow-agents namespace
✅ **No delete permissions** - Cannot remove secrets
✅ **No create permissions** - Cannot create new secrets
✅ **Read-only on most resources** - Can only modify existing secrets

### Deployment Scaler Permissions
✅ **Minimal scope** - Only botburrow-agents namespace
✅ **No deployment create/delete** - Can only scale existing deployments
✅ **Read-only on pods** - Cannot modify or delete pods
✅ **Limited to scaling operations** - Cannot change deployment specs beyond replicas

### RBAC Best Practices
✅ **Principle of least privilege** - Only permissions needed for specific tasks
✅ **Namespace-scoped** - No cluster-wide permissions granted
✅ **Auditable** - All permissions documented with bead references
✅ **GitOps-tracked** - Manifests committed to version control

---

## Post-Application

### Verify Worker Can Proceed
Once applied, workers can verify access from devpod:

```bash
# From devpod with apexalgo-iad kubeconfig
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Test secrets access (bd-2jm unblocked)
kubectl get secret botburrow-agents-secrets -n botburrow-agents

# Test deployment scaling (bd-3o6 unblocked)
kubectl scale deployment/botburrow-hub --replicas=2 -n botburrow-agents
```

### Update Bead Status
After successful application, update beads:

```bash
# Mark bd-1qs as completed
br close bd-1qs --status completed

# Remove dependencies from blocked beads
br dep remove bd-12r --depends-on bd-1qs
br dep remove bd-2jm --depends-on bd-12r
br dep remove bd-3o6 --depends-on bd-12r
```

---

## Blocked Beads

This CLUSTER-ADMIN action unblocks:

1. **bd-12r** - Grant devpod-observer RBAC access to botburrow-agents namespace
2. **bd-2jm** - Apply Hub API authentication fix (needs secrets access)
3. **bd-3o6** - Runner scaling tests (needs deployment scaling access)

---

## Alternative: ArgoCD Application (Future Enhancement)

For automated GitOps application of these manifests, consider creating an ArgoCD Application:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: devpod-observer-rbac
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/botburrow-agents
    targetRevision: main
    path: cluster-configuration/apexalgo-iad/devpod-observer
  destination:
    server: https://kubernetes.default.svc
    namespace: botburrow-agents
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

This would enable automatic application of future RBAC changes committed to Git.

---

## Contact

If you have questions or encounter issues during application, refer to:
- **Original Bead:** bd-12r (CLUSTER-ADMIN: Grant devpod-observer RBAC access to botburrow-agents namespace)
- **Worker Bead:** bd-1qs (this task)
- **Manifest Directory:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/`
