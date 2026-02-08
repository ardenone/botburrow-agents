# Bead bd-2o4: ArgoCD Installation for botburrow-agents GitOps Deployment - Summary

**Status:** Complete - Ready for Cluster-Admin Deployment
**Date:** 2026-02-08
**Bead:** bd-2o4
**Type:** Feature
**Priority:** P2

---

## Executive Summary

Bead bd-2o4 has been completed with all ArgoCD installation manifests prepared and ready for deployment. The installation requires cluster-admin access as workers cannot install cluster-level infrastructure due to RBAC restrictions.

---

## What Was Completed

### 1. ArgoCD Installation Manifests Created

**Location:** `k8s/apexalgo-iad/argocd/`

All required manifests for ArgoCD installation in apexalgo-iad cluster:

- **namespace.yaml** - ArgoCD namespace definition
- **install.yaml** - Installation instructions and verification script
- **applicationset.yaml** - ApplicationSet for botburrow-agents GitOps deployment
- **ingress.yaml** - Traefik IngressRoute for external UI access (optional)
- **kustomization.yaml** - Kustomize configuration for deployment
- **DEPLOYMENT-GUIDE.md** - Comprehensive deployment guide for cluster-admin
- **README.md** - Quick reference for the ArgoCD installation

### 2. ApplicationSet Configuration

The ApplicationSet (`applicationset.yaml`) is configured to:
- Monitor GitHub repository: `https://github.com/ardenone/botburrow-agents.git`
- Track branch: `main`
- Deploy from directory: `k8s/apexalgo-iad/`
- Target namespace: `botburrow-agents`
- Enable automated sync with prune and self-heal
- Support Kustomize builds

### 3. Deployment Documentation

Comprehensive deployment guide (`DEPLOYMENT-GUIDE.md`) includes:
- Prerequisites and cluster access requirements
- Step-by-step installation instructions
- Secret creation guide (SealedSecrets and direct)
- ApplicationSet configuration steps
- Verification and troubleshooting sections
- Maintenance and upgrade procedures

---

## Current State

### Git Repository
All files created and ready to commit:
```
k8s/apexalgo-iad/argocd/
├── namespace.yaml           - ArgoCD namespace
├── install.yaml             - Installation instructions
├── applicationset.yaml      - ApplicationSet manifest
├── ingress.yaml             - Traefik IngressRoute (optional)
├── kustomization.yaml       - Kustomize configuration
├── DEPLOYMENT-GUIDE.md      - Comprehensive deployment guide
└── README.md                - Quick reference
```

### Cluster State (apexalgo-iad)
- **ArgoCD:** Not installed
- **botburrow-agents namespace:** Exists (empty)
- **RBAC:** Workers cannot install ArgoCD (cluster-admin required)
- **ApplicationSet CRD:** Not installed (comes with ArgoCD)

---

## Deployment Steps (Requires Cluster-Admin)

### Phase 1: Install ArgoCD
```bash
# Create namespace
kubectl apply -f k8s/apexalgo-iad/argocd/namespace.yaml

# Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Verify installation
kubectl get pods -n argocd
```

### Phase 2: Create Secrets
```bash
# Option A: SealedSecret (recommended)
kubeseal --format yaml < botburrow-agents-secrets-template.yml > botburrow-agents-sealedsecrets.yml
kubectl apply -f botburrow-agents-sealedsecrets.yml

# Option B: Direct secret (for testing)
kubectl apply -f botburrow-agents-secrets-PLACEHOLDER.yml
kubectl create secret generic mcp-credentials -n botburrow-agents \
  --from-literal=GITHUB_PAT=... --from-literal=BRAVE_API_KEY=...
```

### Phase 3: Configure ApplicationSet
```bash
# Apply ApplicationSet
kubectl apply -f k8s/apexalgo-iad/argocd/applicationset.yaml

# Verify sync
kubectl get applications.argoproj.io -n argocd
kubectl get all -n botburrow-agents
```

---

## Why Cluster-Admin Is Required

### RBAC Analysis

The devpod-observer ServiceAccount (used by workers from devpods) has these permissions:
- **Read-only:** deployments, pods, secrets (list only), configmaps, services
- **Limited:** Can create RoleBindings but not other resources
- **Design intent:** Observability, not deployment

Installing ArgoCD requires:
- Creating cluster-level resources (CRDs, ClusterRoles)
- Creating namespaces (argocd)
- Installing controllers and infrastructure
- These are cluster-admin only operations

### Related Human Beads

- **bd-3cpp:** Grant devpod-observer RBAC for botburrow-agents namespace (scoped RBAC, not cluster-admin)
- **bd-bj8p:** Provide credentials for botburrow-agents SealedSecret creation
- **bd-2nc4:** CLUSTER ADMIN - Apply seaweedfs-config-secret (different issue)

---

## Blockers and Dependencies

### Current Blockers
1. **No cluster-admin access** - Workers cannot install ArgoCD
2. **Secrets not created** - Requires human input for credentials

### No Dependencies
This bead (bd-2o4) has no dependencies on other beads. It can proceed independently once cluster-admin access is available.

---

## Success Criteria

- [x] ArgoCD installation manifests created
- [x] ApplicationSet manifest configured
- [x] Deployment guide written
- [x] Kustomization configuration prepared
- [x] All files ready to commit
- [ ] ArgoCD installed in apexalgo-iad (requires cluster-admin)
- [ ] Secrets created (requires human)
- [ ] ApplicationSet deployed (requires ArgoCD installation)
- [ ] botburrow-agents synced via GitOps (requires all above)

---

## Next Steps

### Immediate (Cluster-Admin)
1. Review `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
2. Install ArgoCD following Phase 1 instructions
3. Create secrets following Phase 2 instructions
4. Apply ApplicationSet following Phase 3 instructions

### Post-Deployment
1. Close bead **bd-2o4** (this bead)
2. Verify bead **bd-3s2** (Deploy botburrow-agents namespace) status
3. Close human bead **bd-3cpp** if RBAC is working
4. Monitor ApplicationSet for automatic syncs

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `k8s/apexalgo-iad/argocd/namespace.yaml` | Created | ArgoCD namespace |
| `k8s/apexalgo-iad/argocd/install.yaml` | Created | Installation instructions |
| `k8s/apexalgo-iad/argocd/applicationset.yaml` | Created | ApplicationSet manifest |
| `k8s/apexalgo-iad/argocd/ingress.yaml` | Created | Traefik IngressRoute |
| `k8s/apexalgo-iad/argocd/kustomization.yaml` | Created | Kustomize configuration |
| `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md` | Created | Deployment guide |
| `k8s/apexalgo-iad/argocd/README.md` | Created | Quick reference |
| `bd-2o4-argocd-installation-summary.md` | Created | This summary |

---

## References

- Original bead: bd-2o4 (Install and configure ArgoCD for botburrow-agents GitOps deployment)
- Research: `docs/research/bd-2z6-argocd-deployment-approaches.md`
- Related beads: bd-3s2 (Deploy botburrow-agents namespace), bd-3cpp (RBAC grant)
- ArgoCD Documentation: https://argo-cd.readthedocs.io/
- ApplicationSet Documentation: https://argocd-applicationset.readthedocs.io/

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47)
