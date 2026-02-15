# ArgoCD Installation Blocker - bd-3f3

**Status:** ⛔ BLOCKED - Requires Cluster-Admin Access
**Date:** 2026-02-15
**Bead:** bd-3f3 (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad for GitOps deployment)
**Blocker Bead:** bd-13z (HUMAN: Cluster-admin to install ArgoCD)

---

## Problem Summary

Workers cannot install ArgoCD in apexalgo-iad cluster due to RBAC restrictions. The `devpod-observer` ServiceAccount lacks cluster-admin permissions required to:
1. Create the `argocd` namespace
2. Install ArgoCD CRDs (Custom Resource Definitions)
3. Deploy ArgoCD components

**RBAC Error:**
```
Error from server (Forbidden): namespaces is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "namespaces" in API group "" at the cluster scope
```

---

## Current State

### ✅ Working Components
- botburrow-agents namespace exists and is running
- All pods are healthy:
  - coordinator (2 replicas)
  - coordinator-git-sync (2 replicas)
  - runner-exploration (1 replica)
  - runner-git-sync (2 replicas)
  - runner-hybrid (3 replicas)
  - runner-notification (2 replicas)
  - valkey (1 replica)
- Secrets created: `botburrow-agents-secrets`, `mcp-credentials`
- SealedSecrets controller is running

### ❌ Missing Components
- ArgoCD namespace does not exist
- ArgoCD not installed
- GitOps automation not enabled

### ✅ Prepared Artifacts
- ArgoCD namespace manifest: `k8s/apexalgo-iad/argocd/namespace.yaml`
- ArgoCD installation guide: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
- ArgoCD Application manifest: `k8s/apexalgo-iad/argocd-application.yaml`
- ArgoCD ApplicationSet manifest: `k8s/apexalgo-iad/argocd/applicationset.yaml`

---

## Solution: Cluster-Admin Installation

**Human bead bd-13z** requests cluster-admin to perform the following steps:

### Phase 1: Install ArgoCD

```bash
# Step 1: Set kubeconfig to apexalgo-iad with cluster-admin context
export KUBECONFIG=~/.kube/apexalgo-iad-admin.kubeconfig  # Use admin context

# Step 2: Create ArgoCD namespace
kubectl apply -f k8s/apexalgo-iad/argocd/namespace.yaml

# Step 3: Install ArgoCD stable release
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Step 4: Verify installation (wait ~2 minutes for pods to start)
kubectl get pods -n argocd

# Expected output:
# NAME                                      READY   STATUS    RESTARTS   AGE
# argocd-applicationset-controller-...      1/1     Running   0          1m
# argocd-dex-server-...                     1/1     Running   0          1m
# argocd-notifications-controller-...       1/1     Running   0          1m
# argocd-redis-...                          1/1     Running   0          1m
# argocd-repo-server-...                    1/1     Running   0          1m
# argocd-server-...                         1/1     Running   0          1m

# Step 5: Check CRDs are installed
kubectl get crd | grep argoproj.io

# Expected output:
# applicationsets.argoproj.io
# applications.argoproj.io
# appprojects.argoproj.io
```

### Phase 2: Apply ArgoCD Application

```bash
# Step 6: Apply ArgoCD Application manifest
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml

# Step 7: Verify Application sync
kubectl get applications.argoproj.io -n argocd

# Expected output:
# NAME                SYNC STATUS   HEALTH STATUS
# botburrow-agents    Synced        Healthy

# Step 8: Verify all resources are synced
kubectl get all -n botburrow-agents
```

### Phase 3: Verify GitOps Workflow (Optional)

```bash
# Get ArgoCD admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d

# Port-forward to ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open browser to https://localhost:8080
# Login with username: admin, password from above
```

---

## After Installation

Once cluster-admin completes the installation:

1. **Verify ArgoCD is running:**
   ```bash
   export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
   kubectl get pods -n argocd
   kubectl get applications.argoproj.io -n argocd
   ```

2. **Close blocker bead bd-13z:**
   ```bash
   br close bd-13z --status completed
   ```

3. **Resume work on bd-3f3:**
   - Workers will automatically resume when dependency is resolved
   - No manual intervention needed

4. **Verify GitOps automation:**
   - Make a change to git repo
   - Watch ArgoCD automatically sync it
   - Verify changes appear in cluster

---

## Alternative Approaches Considered

### ❌ Option 2: Grant devpod-observer cluster-admin
**Rejected** - Violates security best practices and principle of least privilege

### ❌ Option 3: Skip ArgoCD, keep kubectl workaround
**Rejected** - Defeats purpose of GitOps automation and bd-3e3 task

---

## References

- **Original Task:** bd-3e3 (Create ArgoCD GitOps deployment for botburrow-agents)
- **Blocker Bead:** bd-13z (HUMAN: Cluster-admin to install ArgoCD)
- **Deployment Guide:** k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md
- **Application Manifest:** k8s/apexalgo-iad/argocd-application.yaml
- **Previous Work:** bd-2o4 (Install and configure ArgoCD)
- **Workaround:** docs/workarounds/bd-cni-argocd-workaround.md

---

## Timeline

- **2026-02-15 18:08:** Blocker identified (RBAC Forbidden error)
- **2026-02-15 18:08:** Human bead bd-13z created
- **2026-02-15 18:08:** Dependency added: bd-3f3 → bd-13z
- **Pending:** Cluster-admin installation
- **Pending:** Blocker resolution and task completion

---

**Document Version:** 1.0
**Author:** Claude Worker
**Last Updated:** 2026-02-15
