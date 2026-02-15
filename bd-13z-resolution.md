# bd-13z Resolution: ArgoCD Installation Requirements

**Status:** Closed as duplicate of bd-3f3
**Date:** 2026-02-15
**Worker:** claude-sonnet-4-5

---

## Summary

Bead **bd-13z** (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad cluster) has been closed as a duplicate of **bd-3f3**. This task requires cluster-admin access that is not available to workers in the devpod environment.

## Current State

✅ **botburrow-agents deployment is healthy:**
```
NAME                                    READY   STATUS    RESTARTS   AGE
coordinator-644b76d7bd-89trf            1/1     Running   0          17h
coordinator-644b76d7bd-pwlft            1/1     Running   0          17h
coordinator-git-sync-79db4b749c-4dz6d   2/2     Running   0          17h
coordinator-git-sync-79db4b749c-sbl4p   2/2     Running   0          17h
runner-exploration-77d87fbf5c-wvz9s     1/1     Running   0          17h
runner-git-sync-55758d68c4-hhzx4        2/2     Running   0          17h
runner-git-sync-55758d68c4-zj9v8        2/2     Running   0          16h
runner-hybrid-5f958ddfb5-68tc2          1/1     Running   0          17h
runner-hybrid-5f958ddfb5-skvnn          1/1     Running   0          17h
runner-notification-7ddb655b99-7f4m6    1/1     Running   0          17h
runner-notification-7ddb655b99-s9wk8    1/1     Running   0          17h
valkey-d4fc4c84d-ttdzw                  1/1     Running   0          4d15h
```

❌ **ArgoCD is not installed:**
```bash
$ kubectl get namespace argocd
Error from server (NotFound): namespaces "argocd" not found
```

❌ **No cluster-admin access available:**
```bash
$ kubectl auth can-i create namespaces --all-namespaces
no
```

## Why This Task Cannot Be Completed by Workers

1. **RBAC Restrictions:** The devpod-observer ServiceAccount has read-only permissions in most namespaces
2. **Namespace Creation:** Creating the `argocd` namespace requires cluster-admin permissions
3. **CRD Installation:** Installing ArgoCD CRDs requires cluster-wide permissions
4. **No Admin Kubeconfig:** The devpod environment only has access to the devpod-observer kubeconfig

## Resolution Path

The human administrator should work directly with **bead bd-3f3**, which contains:

- Detailed options analysis (3 approaches with pros/cons)
- Complete installation instructions
- References to all prepared manifests
- Comprehensive deployment guide

## Quick Start for Human Administrator

**Prerequisites:**
- Cluster-admin access to apexalgo-iad cluster
- kubectl configured with admin context

**Installation Steps:**

### Option 1: Install ArgoCD and Enable GitOps (RECOMMENDED)

```bash
# Set admin kubeconfig context
export KUBECONFIG=~/.kube/apexalgo-iad-admin.kubeconfig  # Use your admin config

# Phase 1: Install ArgoCD
kubectl apply -f k8s/apexalgo-iad/argocd/namespace.yaml
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Verify installation (~2 minutes for pods to start)
kubectl get pods -n argocd

# Phase 2: Apply ArgoCD Application
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml

# Verify GitOps sync
kubectl get applications.argoproj.io -n argocd
kubectl get all -n botburrow-agents
```

### Option 2: Keep kubectl Workaround (No ArgoCD)

If ArgoCD is not desired:
- Mark bd-3f3 and bd-3e3 as completed with note that kubectl deployment is permanent
- botburrow-agents is already deployed and running successfully via kubectl
- Manual updates will be required (no GitOps automation)

## Prepared Resources

All ArgoCD manifests are ready for deployment:

- **Namespace:** `k8s/apexalgo-iad/argocd/namespace.yaml`
- **Application:** `k8s/apexalgo-iad/argocd-application.yaml`
- **ApplicationSet:** `k8s/apexalgo-iad/argocd/applicationset.yaml`
- **Deployment Guide:** `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`

## Benefits of Installing ArgoCD

1. **Automated GitOps Sync:** Changes to Git automatically sync to cluster
2. **Declarative Configuration:** All manifests in Git are the source of truth
3. **Self-Healing:** ArgoCD automatically corrects drift from Git
4. **Audit Trail:** Git history provides complete audit trail
5. **Rollback:** Easy rollback to any previous Git commit

## Next Steps

Human administrator should:

1. Review **bd-3f3** for complete context and options
2. Choose installation approach (ArgoCD vs. kubectl workaround)
3. Execute installation steps with cluster-admin access
4. Update bd-3f3 status after completion
5. Update bd-3e3 (GitOps deployment) based on chosen approach

## References

- **Parent Human Bead:** bd-3f3 (CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad for GitOps deployment)
- **Deployment Guide:** k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md
- **Application Manifest:** k8s/apexalgo-iad/argocd-application.yaml
- **ApplicationSet Manifest:** k8s/apexalgo-iad/argocd/applicationset.yaml
- **Original GitOps Task:** bd-3e3 (Create ArgoCD GitOps deployment for botburrow-agents)
- **Workaround Documentation:** docs/workarounds/bd-cni-argocd-workaround.md

---

**Bead Status:** bd-13z closed (duplicate of bd-3f3)
**Close Reason:** Requires cluster-admin access not available to workers
**Action Required:** Human administrator to work with bd-3f3
