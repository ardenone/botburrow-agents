# ArgoCD Installation Plan for apexalgo-iad

**Bead:** bd-3f3  
**Status:** Blocked - Requires cluster-admin  
**Date:** 2026-02-15  
**Worker:** claude-code-glm-47-lima  

---

## Executive Summary

ArgoCD installation for apexalgo-iad cluster is **ready for deployment** but blocked by RBAC permissions. All manifests are prepared, tested, and documented. This document provides three resolution options with implementation details.

---

## Current State Analysis

### ✅ What's Working
- **botburrow-agents namespace:** Active with 13 running pods
- **Pods healthy:** All deployments running (coordinator, runners, valkey)
- **Secrets created:** botburrow-agents-secrets, mcp-credentials (via bd-2la)
- **SealedSecrets controller:** Running in sealed-secrets namespace
- **Manifests ready:** All ArgoCD manifests prepared and validated

### ❌ What's Blocking
- **ArgoCD not installed:** No `argocd` namespace in cluster
- **RBAC restriction:** devpod-observer ServiceAccount lacks cluster-admin
- **Permission check failed:** `kubectl auth can-i create namespace` → `no`

### 📦 Prepared Artifacts
```
k8s/apexalgo-iad/argocd/
├── DEPLOYMENT-GUIDE.md          ✅ Comprehensive step-by-step guide
├── namespace.yaml                ✅ ArgoCD namespace definition
├── applicationset.yaml           ✅ ApplicationSet for botburrow-agents
└── ingress.yaml                  ✅ Optional external access

k8s/apexalgo-iad/
├── argocd-application.yaml       ✅ ArgoCD Application manifest
└── [deployment manifests]        ✅ All k8s resources ready
```

---

## Resolution Options

### Option 1: Grant Temporary Cluster-Admin to devpod-observer (RECOMMENDED)

**Pros:**
- Fastest implementation (< 5 minutes)
- Workers can complete installation autonomously
- Temporary - can be revoked after installation
- Minimal security impact (time-boxed)

**Cons:**
- Requires human cluster-admin intervention
- Temporary elevated privileges

**Implementation:**
```bash
# Step 1: Grant cluster-admin (run as cluster-admin user)
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# Step 2: Worker completes installation (automatic)
# - Creates argocd namespace
# - Installs ArgoCD from stable manifest
# - Applies ArgoCD Application for botburrow-agents
# - Verifies sync and health

# Step 3: Revoke cluster-admin (run as cluster-admin user)
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Step 4: Restore read-only permissions (already in place)
# - ClusterRoleBinding: devpod-observer-cluster-viewer
# - RoleBinding: devpod-observer-full-access (devpod-observer namespace)
# - RoleBinding: devpod-observer-monitoring-access (monitoring namespace)
```

**Security Model:**
- **Duration:** < 30 minutes (only during installation)
- **Scope:** Limited to ArgoCD installation tasks
- **Audit:** All kubectl operations logged
- **Rollback:** Simple - delete ClusterRoleBinding

**Verification Commands:**
```bash
# Check if devpod-observer has cluster-admin
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl auth can-i create namespace
# Should return: yes

# Verify ArgoCD installation
kubectl get namespaces | grep argocd
kubectl get pods -n argocd
kubectl get applications.argoproj.io -n argocd
```

---

### Option 2: Manual ArgoCD Installation by Cluster-Admin

**Pros:**
- Zero additional permissions granted to workers
- Direct human oversight of installation
- No security policy changes

**Cons:**
- Requires human time (15-20 minutes)
- Manual steps prone to errors
- Blocks autonomous workflow

**Implementation:**

**Phase 1: Install ArgoCD (Cluster-Admin)**
```bash
# From machine with cluster-admin kubectl context
git clone https://github.com/ardenone/botburrow-agents.git
cd botburrow-agents

# Create namespace
kubectl apply -f k8s/apexalgo-iad/argocd/namespace.yaml

# Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for pods
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=argocd -n argocd --timeout=300s

# Verify installation
kubectl get pods -n argocd
kubectl get crd | grep argoproj.io
```

**Phase 2: Apply Application Manifest (Cluster-Admin)**
```bash
# Apply ArgoCD Application
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml

# Verify Application created
kubectl get applications.argoproj.io -n argocd

# Check sync status
kubectl get application botburrow-agents -n argocd -o yaml
```

**Phase 3: Verify GitOps Sync (Cluster-Admin)**
```bash
# Watch Application sync
kubectl get applications.argoproj.io -n argocd -w

# Check botburrow-agents resources
kubectl get all -n botburrow-agents

# Verify ArgoCD is managing resources
kubectl get pods -n botburrow-agents -o yaml | grep -A 5 "managed-by: argocd"
```

**Reference Documentation:**
- Complete guide: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
- Line-by-line instructions with verification steps

---

### Option 3: Create Dedicated ArgoCD-Installer ServiceAccount

**Pros:**
- Least-privilege approach
- Reusable for future ArgoCD operations
- Auditable permissions

**Cons:**
- Most complex setup
- Still requires cluster-admin to create
- Overhead for one-time operation

**Implementation:**

**Step 1: Create ServiceAccount and RBAC (Cluster-Admin)**
```yaml
# argocd-installer-rbac.yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: argocd-installer
  namespace: devpod-observer
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argocd-installer
rules:
  # Namespace creation
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["create", "get", "list"]
  
  # ArgoCD installation (in argocd namespace)
  - apiGroups: ["", "apps", "rbac.authorization.k8s.io"]
    resources: ["*"]
    verbs: ["*"]
    resourceNames: ["argocd"]
  
  # CRD installation
  - apiGroups: ["apiextensions.k8s.io"]
    resources: ["customresourcedefinitions"]
    verbs: ["create", "get", "list", "update", "patch"]
  
  # ArgoCD Application creation
  - apiGroups: ["argoproj.io"]
    resources: ["applications", "applicationsets"]
    verbs: ["create", "get", "list", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argocd-installer
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: argocd-installer
subjects:
  - kind: ServiceAccount
    name: argocd-installer
    namespace: devpod-observer
```

```bash
# Apply RBAC
kubectl apply -f argocd-installer-rbac.yaml
```

**Step 2: Update kubectl-proxy to Use argocd-installer (Cluster-Admin)**
```bash
# Temporarily update kubectl-proxy ServiceAccount
kubectl set serviceaccount deployment kubectl-proxy argocd-installer -n devpod-observer

# Workers can now install ArgoCD
```

**Step 3: Workers Complete Installation (Automatic)**
```bash
# Worker executes installation (now has permissions)
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl apply -f k8s/apexalgo-iad/argocd/namespace.yaml
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml
```

**Step 4: Restore Original ServiceAccount (Cluster-Admin)**
```bash
# Restore devpod-observer ServiceAccount
kubectl set serviceaccount deployment kubectl-proxy devpod-observer -n devpod-observer
```

---

## Recommendation

**Option 1** is recommended for the following reasons:

1. **Speed:** Installation completes in < 5 minutes
2. **Autonomy:** Workers complete installation without human intervention
3. **Security:** Time-boxed elevation, revoked immediately after
4. **Simplicity:** Single ClusterRoleBinding, easy rollback
5. **Audit:** All actions logged and attributable

**Risk Assessment:**
- **Low Risk:** devpod-observer already has read access to entire cluster
- **Limited Scope:** Only used for ArgoCD installation
- **Reversible:** Immediate ClusterRoleBinding deletion
- **Monitored:** All kubectl operations are audit-logged

---

## Post-Installation Verification

After installation (any option), verify:

```bash
# Check ArgoCD pods
kubectl get pods -n argocd
# Expected: 5-6 pods (applicationset-controller, dex-server, notifications-controller, redis, repo-server, server)

# Check ArgoCD Application
kubectl get applications.argoproj.io -n argocd
# Expected: botburrow-agents (Synced, Healthy)

# Check botburrow-agents managed by ArgoCD
kubectl get all -n botburrow-agents -l app.kubernetes.io/instance=botburrow-agents

# Verify GitOps sync working
# Make a small change to git repo and watch ArgoCD sync
```

---

## Rollback Plan

If ArgoCD installation fails or causes issues:

```bash
# Remove ArgoCD Application
kubectl delete application botburrow-agents -n argocd

# Delete ArgoCD installation
kubectl delete namespace argocd

# Resources in botburrow-agents remain unaffected
# (ArgoCD only manages, does not own resources)
```

---

## References

- ArgoCD Official Docs: https://argo-cd.readthedocs.io/
- Installation Guide: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
- RBAC Docs: https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- Cluster RBAC: `cluster-configuration/apexalgo-iad/devpod-observer/rbac.yml`

---

**Next Steps:** Human approval required to proceed with Option 1, 2, or 3.
