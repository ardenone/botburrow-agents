# Bead bd-3e3: ArgoCD GitOps Deployment Status

**Status:** Blocked on ArgoCD Installation (bd-3f3)
**Date:** 2026-02-15
**Bead:** bd-3e3
**Type:** Task
**Priority:** P2

---

## Executive Summary

Task bd-3e3 (Create ArgoCD GitOps deployment for botburrow-agents) is blocked because ArgoCD is not installed in the apexalgo-iad cluster. All preparation work is complete, including manifests, documentation, and infrastructure. The only remaining blocker is ArgoCD installation, which requires cluster-admin privileges.

---

## Current Status

### ✅ Completed
1. **botburrow-agents deployment is running** (via kubectl workaround from bd-cni)
   - All pods are healthy and operational
   - Coordinator, runners, and valkey are deployed
   - Secrets exist (resolved via bd-2la)

2. **ArgoCD manifests prepared and ready**
   - Application manifest: `k8s/apexalgo-iad/argocd-application.yaml`
   - ApplicationSet manifest: `k8s/apexalgo-iad/argocd/applicationset.yaml`
   - GitOps kustomization: `k8s/apexalgo-iad/kustomization-gitops.yaml`
   - Health check hooks: `k8s/apexalgo-iad/argocd-health-checks.yaml`

3. **Documentation complete**
   - Deployment guide: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
   - GitOps guide: `k8s/apexalgo-iad/DEPLOYMENT-GITOPS.md`
   - Installation summary: `bd-2o4-argocd-installation-summary.md`

4. **Prerequisites verified**
   - SealedSecrets controller is running in sealed-secrets namespace
   - Namespace exists and is operational
   - All required secrets exist (botburrow-agents-secrets, mcp-credentials)

### ❌ Blocker
**ArgoCD is NOT installed in apexalgo-iad cluster**
- Namespace `argocd` does not exist
- CRDs for Application/ApplicationSet not available
- Installation requires cluster-admin privileges
- Human bead **bd-3f3** created to request cluster-admin installation

---

## Deployment Architecture (When Complete)

```
┌─────────────────────────────────────────────────────────────────────┐
│  GitOps Automation Flow                                            │
│                                                                     │
│  GitHub Repository                                                  │
│  └── k8s/apexalgo-iad/                                              │
│      ├── argocd-application.yaml      ← ArgoCD Application         │
│      ├── kustomization-gitops.yaml    ← GitOps Kustomization        │
│      ├── argocd-health-checks.yaml    ← Pre/post sync hooks         │
│      └── *.yaml                       → All manifests               │
│                                ↓                                     │
│                        ArgoCD Sync                                   │
│                                ↓                                     │
│  apexalgo-iad Cluster                                                │
│  └── botburrow-agents namespace                                     │
│      ├── Valkey (Redis)                                             │
│      ├── Coordinator (2 replicas, leader election)                  │
│      ├── Runners (hybrid, notification, exploration)                │
│      └── Secrets (via SealedSecrets)                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Dependencies

### Resolved Dependencies
- **bd-2la** (CLOSED) - Create botburrow-agents-secrets and mcp-credentials
  - Status: ✅ Complete
  - Secrets exist in cluster

### Current Blockers
- **bd-3f3** (OPEN) - CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad
  - Status: ⏳ Waiting for cluster-admin
  - Type: Human bead
  - Priority: P0 (Critical)
  - Created: 2026-02-15

---

## What Needs to Happen

### Phase 1: Cluster-Admin Installs ArgoCD (bd-3f3)

The cluster-admin needs to follow the deployment guide at `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`:

```bash
# Step 1: Create ArgoCD namespace
kubectl apply -f k8s/apexalgo-iad/argocd/namespace.yaml

# Step 2: Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Step 3: Verify installation
kubectl get pods -n argocd
```

### Phase 2: Apply ArgoCD Application (bd-3e3 can resume)

Once ArgoCD is installed, this bead (bd-3e3) can resume and apply the Application manifest:

```bash
# Apply ArgoCD Application
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml

# Verify sync
kubectl get application botburrow-agents -n argocd
kubectl get all -n botburrow-agents
```

### Phase 3: Verify GitOps Workflow

```bash
# Check Application status
kubectl get application botburrow-agents -n argocd -o yaml

# Verify automated sync
# Make a change to git repo and watch ArgoCD sync it
```

---

## Files Ready for Deployment

| File | Purpose | Status |
|------|---------|--------|
| `k8s/apexalgo-iad/argocd-application.yaml` | ArgoCD Application manifest | ✅ Ready |
| `k8s/apexalgo-iad/kustomization-gitops.yaml` | GitOps kustomization | ✅ Ready |
| `k8s/apexalgo-iad/argocd-health-checks.yaml` | Pre/post sync hooks | ✅ Ready |
| `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md` | Installation guide | ✅ Ready |
| `k8s/apexalgo-iad/argocd/namespace.yaml` | ArgoCD namespace | ✅ Ready |
| `k8s/apexalgo-iad/argocd/applicationset.yaml` | ApplicationSet (alternative) | ✅ Ready |

---

## Current Deployment (kubectl workaround)

The deployment is currently managed via kubectl workaround (bd-cni):

```bash
# Verify current deployment
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get pods -n botburrow-agents

# Output (as of 2026-02-15):
NAME                                    READY   STATUS    RESTARTS   AGE
coordinator-644b76d7bd-89trf            1/1     Running   0          17h
coordinator-644b76d7bd-pwlft            1/1     Running   0          17h
coordinator-git-sync-79db4b749c-4dz6d   2/2     Running   0          16h
coordinator-git-sync-79db4b749c-sbl4p   2/2     Running   0          16h
runner-exploration-77d87fbf5c-wvz9s     1/1     Running   0          17h
runner-git-sync-55758d68c4-hhzx4        2/2     Running   0          16h
runner-git-sync-55758d68c4-zj9v8        2/2     Running   0          16h
runner-hybrid-5f958ddfb5-68tc2          1/1     Running   0          17h
runner-hybrid-5f958ddfb5-skvnn          1/1     Running   0          17h
runner-notification-7ddb655b99-7f4m6    1/1     Running   0          17h
runner-notification-7ddb655b99-s9wk8    1/1     Running   0          17h
valkey-d4fc4c84d-ttdzw                  1/1     Running   0          4d15h
```

---

## Migration Plan (After ArgoCD Installation)

Once ArgoCD is installed and the Application manifest is applied:

1. **ArgoCD will detect existing resources** - All currently deployed resources will be recognized by ArgoCD
2. **Automated sync will be enabled** - Changes pushed to git will automatically sync to cluster
3. **Health checks will run** - Pre/post sync hooks will validate deployment
4. **Kubectl workaround can be deprecated** - ArgoCD becomes the primary deployment method

---

## Success Criteria

- [x] botburrow-agents namespace deployed and running
- [x] All secrets created (via bd-2la)
- [x] ArgoCD manifests prepared
- [x] Documentation complete
- [ ] ArgoCD installed (blocked on bd-3f3)
- [ ] ArgoCD Application deployed
- [ ] GitOps sync verified
- [ ] Health checks passing

---

## Next Steps

### Immediate
1. **Wait for bd-3f3 resolution** - Cluster-admin installs ArgoCD
2. **Resume bd-3e3** - Apply ArgoCD Application manifest
3. **Verify GitOps workflow** - Test automated sync from git

### Post-Deployment
1. **Close bd-3e3** after successful GitOps deployment
2. **Monitor ArgoCD sync** for automated updates
3. **Deprecate kubectl workaround** documentation
4. **Document GitOps workflow** for future updates

---

## References

- Human bead: bd-3f3 (CLUSTER-ADMIN: Install ArgoCD)
- Previous secret work: bd-2la (Create botburrow-agents-secrets)
- ArgoCD preparation: bd-2o4 (Install and configure ArgoCD)
- Workaround deployment: bd-cni (kubectl workaround)
- ArgoCD deployment guide: `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
- GitOps guide: `k8s/apexalgo-iad/DEPLOYMENT-GITOPS.md`

---

**Document Version:** 1.0
**Last Updated:** 2026-02-15
**Author:** Claude Worker (claude-code-glm-47-lima)
