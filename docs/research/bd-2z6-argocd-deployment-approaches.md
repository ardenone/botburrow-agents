# BD-2Z6: ArgoCD Deployment Approaches for botburrow-agents

**Status:** Research Document
**Date:** 2026-02-08
**Original Bead:** bd-1v9 (Fix botburrow-agents deployment via ArgoCD)
**Alternative Bead:** bd-2z6 (Alternative: Research and document options)

---

## Executive Summary

This document provides a detailed comparison of possible approaches for deploying botburrow-agents to the apexalgo-iad cluster when ArgoCD is not available or not functioning. **Key Finding:** The deployment is currently blocked because the manifests reference ArgoCD as the deployment manager, but ArgoCD is not installed in the target cluster.

This research documents multiple deployment approaches to inform human decision on how to proceed.

---

## Context: Current Deployment State

### Original Issue (bd-1v9)

**Title:** Fix botburrow-agents deployment via ArgoCD

**Problem Statement:**
- The `botburrow-agents` namespace exists but is **EMPTY** (no pods, deployments, or services)
- ArgoCD Application was expected to manage deployment but resources were never synced
- Namespace has `argocd.argoproj.io/tracking-id` annotation suggesting ArgoCD management
- All manifests exist in git and are syntactically valid

**Root Cause:**
1. **ArgoCD not installed** in apexalgo-iad cluster
2. **RBAC restrictions** prevent direct kubectl deployment from devpods
3. **Missing secrets** block deployment even if ArgoCD were available

**Current State:**
- Namespace `botburrow-agents` exists with ArgoCD tracking annotations
- No resources deployed (verified via `kubectl get all -n botburrow-agents`)
- All k8s manifests exist and are valid
- Simplified deployment approach already documented (`DEPLOYMENT-SIMPLIFIED.md`)

---

## Problem Analysis

### Why ArgoCD Deployment Failed

**Expected GitOps Flow:**
```
Git Push → ArgoCD Application → Sync Resources → Kubernetes Deployment
```

**Actual State:**
```
Git Push → [No ArgoCD] → No Sync → Empty Namespace
```

**Evidence:**
```bash
# ArgoCD CRD not registered
kubectl get applications.argoproj.io -A
# Error: the server doesn't have a resource type "applications"

# No ArgoCD namespace
kubectl get ns | grep argocd
# (no output)

# Namespace has tracking annotation but no resources
kubectl get all -n botburrow-agents
# No resources found.
```

### Secondary Blockers

**1. RBAC Restrictions:**
- Devpods use `devpod-observer` ServiceAccount
- Limited permissions (intentional security boundary)
- Cannot create deployments, services, or secrets

**2. Missing Secrets:**
- `botburrow-agents-secrets` - Hub API, R2 storage, Git credentials
- `mcp-credentials` - MCP server API keys
- Cannot be created by workers due to RBAC

---

## Deployment Approaches

### Approach 1: Manual kubectl Deployment (Simplified)

**Description:** Deploy directly using kubectl with cluster-admin credentials, bypassing ArgoCD entirely.

**Implementation:**
```bash
# From a cluster-admin context (not from devpod):
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
kubectl apply -k k8s/apexalgo-iad/

# Or use the simplified kustomization
kubectl apply -k k8s/apexalgo-iad/ --context=apexalgo-iad
```

**Pros:**
- **Immediate deployment** - works right now
- **Simple** - standard kubectl workflow
- **Full control** - no GitOp abstraction layer
- **Already documented** - `DEPLOYMENT-SIMPLIFIED.md` exists
- **No additional infrastructure** - uses existing kubectl

**Cons:**
- **Not GitOps** - deployment state not tracked in git
- **Manual updates** - each change requires manual kubectl apply
- **Drift risk** - cluster can drift from git state
- **No automated rollback** - manual revert required
- **Cluster-admin required** - cannot be done from devpods

**Best For:**
- Emergency deployments
- Development/testing environments
- Situations requiring immediate deployment
- Learning the system before GitOps

**Status:** **Already implemented** as workaround (kustomization-simplified.yaml)

---

### Approach 2: Install and Configure ArgoCD

**Description:** Install ArgoCD in apexalgo-iad cluster and configure ApplicationSet for botburrow-agents.

**Implementation:**

**Step 1: Install ArgoCD**
```bash
# Create namespace
kubectl create namespace argocd

# Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Verify installation
kubectl get pods -n argocd
```

**Step 2: Create ApplicationSet**
```yaml
# k8s/apexalgo-iad/argocd-applicationset.yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: botburrow-agents
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/your-org/botburrow-agents.git
        revision: main
        directories:
          - path: k8s/apexalgo-iad
  template:
    metadata:
      name: botburrow-agents
      namespace: botburrow-agents
    spec:
      project: default
      source:
        repoURL: https://github.com/your-org/botburrow-agents.git
        targetRevision: main
        path: k8s/apexalgo-iad
        kustomize:
          images:
            - name: botburrow-agents
              newTag: latest
      destination:
        server: https://kubernetes.default.svc
        namespace: botburrow-agents
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

**Step 3: Configure Secrets**
```bash
# Option A: Create SealedSecrets
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/secrets.yml
# Edit with real values
kubeseal --format yaml < /tmp/secrets.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# Option B: Manual secret creation (cluster-admin only)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**Pros:**
- **True GitOps** - everything tracked in git
- **Automated sync** - push to git triggers deployment
- **Self-healing** - drift detection and auto-correction
- **Rollback** - easy revert via git
- **Multi-cluster** - same manifests, multiple clusters
- **Audit trail** - all changes in git history

**Cons:**
- **Additional infrastructure** - ArgoCD namespace, pods, resources
- **Complexity** - learning curve for ArgoCD
- **Bootstrap problem** - need ArgoCD to deploy via ArgoCD
- **Resource overhead** - ArgoCD components use resources
- **Initial setup** - requires cluster-admin for installation

**Best For:**
- Production environments
- Teams wanting GitOps workflow
- Multi-cluster deployments
- Projects with frequent changes

**Status:** **Not implemented** - ArgoCD not installed in apexalgo-iad

---

### Approach 3: Flux GitOps

**Description:** Use Flux instead of ArgoCD for GitOps deployment.

**Implementation:**

**Step 1: Install Flux**
```bash
flux install \
  --version=latest \
  --namespace=flux-system \
  --arch=amd64
```

**Step 2: Create Kustomization**
```yaml
# k8s/apexalgo-iad/flux-kustomization.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: botburrow-agents
  namespace: flux-system
spec:
  interval: 5m
  path: ./k8s/apexalgo-iad
  prune: true
  sourceRef:
    kind: GitRepository
    name: botburrow-agents
  targetNamespace: botburrow-agents
```

**Step 3: Create GitRepository source**
```yaml
# k8s/apexalgo-iad/flux-source.yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: botburrow-agents
  namespace: flux-system
spec:
  interval: 5m
  url: https://github.com/your-org/botburrow-agents.git
  ref:
    branch: main
```

**Pros:**
- **GitOps native** - designed for git-driven deployment
- **Lighter than ArgoCD** - smaller resource footprint
- **Kubernetes native** - uses CRDs for everything
- **Modular** - use only components you need
- **Good Kubernetes integration** - native tooling

**Cons:**
- **Different UI paradigm** - CLI-focused vs ArgoCD UI
- **Learning curve** - different concepts than ArgoCD
- **Less mature** - smaller community than ArgoCD
- **Additional infrastructure** - still need Flux installed
- **Bootstrap problem** - same as ArgoCD

**Best For:**
- Teams preferring CLI over UI
- Resource-constrained clusters
- Already using Flux elsewhere
- Kubernetes-native preference

**Status:** **Not implemented** - Flux not installed in apexalgo-iad

---

### Approach 4: GitHub Actions Deployment

**Description:** Use GitHub Actions to deploy directly to cluster on push.

**Implementation:**
```yaml
# .github/workflows/deploy-k8s.yml
name: Deploy to Kubernetes

on:
  push:
    branches: [main]
    paths:
      - 'k8s/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure kubectl
        uses: azure/k8s-set-context@v3
        with:
          method: kubeconfig
          kubeconfig: ${{ secrets.KUBECONFIG_APEXALGO_IAD }}

      - name: Apply manifests
        run: |
          kubectl apply -k k8s/apexalgo-iad/
          kubectl rollout status deployment -n botburrow-agents
```

**Pros:**
- **Leverages existing CI/CD** - GitHub Actions already configured
- **Familiar workflow** - push, wait, deployed
- **Easy rollback** - revert commit, re-run workflow
- **No cluster GitOps** - no ArgoCD/Flux needed
- **Logging** - GitHub Actions logs for debugging

**Cons:**
- **Credentials in GitHub** - kubeconfig secret required
- **Not continuous** - only checks on push
- **No drift detection** - manual changes not caught
- **GitHub Actions dependency** - external service required
- **Slower feedback** - push → workflow → deploy vs immediate sync

**Best For:**
- Projects already using GitHub Actions
- Single-cluster deployments
- Teams comfortable with GitHub Actions
- Situations without GitOps infrastructure

**Status:** **CI/CD exists** but only builds images, doesn't deploy

---

### Approach 5: Keep Current State (No Deployment)

**Description:** Accept empty namespace, document blockers, wait for human decision.

**Implementation:**
1. Close bd-1v9 with "ArgoCD not installed - cannot deploy via ArgoCD"
2. Create human bead for deployment decision
3. Document current state in project README
4. No deployment until human chooses approach

**Pros:**
- **Minimal effort** - no implementation work
- **Forces decision** - human must choose path
- **Prevents partial work** - no half-solutions
- **Clear documentation** - blockers explicit

**Cons:**
- **No deployment** - system not running
- **Beads blocked** - dependent work cannot proceed
- **Time lost** - waiting for decision
- **No progress** - project stalled

**Best For:**
- When deployment approach is genuinely unclear
- When major infrastructure decisions needed
- When human input required for security/access

**Status:** **Current state** - deployment blocked, awaiting decision

---

## Comparison Matrix

| Approach | GitOps | Automated | Infrastructure | Effort | Rollback | Best For |
|----------|--------|-----------|----------------|--------|----------|----------|
| 1. Manual kubectl | No | No | None | Low | Manual | Quick deployment |
| 2. ArgoCD | Yes | Yes | ArgoCD | High | Git revert | Production |
| 3. Flux | Yes | Yes | Flux | High | Git revert | CLI-focused teams |
| 4. GitHub Actions | Partial | On push | GitHub | Medium | Git revert | CI/CD-centric |
| 5. No Deployment | N/A | N/A | None | None | N/A | Decision pending |

---

## Decision Framework

### Choose Approach 1 (Manual kubectl) if:
- You need deployment **immediately**
- You're in **development/testing** phase
- You **don't have ArgoCD** and won't install it
- You want **full control** over deployment
- You're comfortable with manual operations

### Choose Approach 2 (ArgoCD) if:
- You want **true GitOps** workflow
- You're deploying to **production**
- You have **multiple clusters** to manage
- You want **automated sync** and self-healing
- You can install additional infrastructure

### Choose Approach 3 (Flux) if:
- You prefer **CLI over UI**
- You want **smaller footprint** than ArgoCD
- You're already using **Flux elsewhere**
- You value **Kubernetes-native** tools

### Choose Approach 4 (GitHub Actions) if:
- You already use **GitHub Actions heavily**
- You have a **single cluster**
- You want to **avoid in-cluster GitOps**
- You're comfortable with credentials in GitHub

### Choose Approach 5 (No Deployment) if:
- You need **human input** on architecture
- You're unsure which approach is best
- There are **security/access considerations**
- You want to **pause** until decision is made

---

## Security Considerations

### RBAC Requirements

**Current State (devpod-observer SA):**
- Can read most resources
- Cannot create deployments, services, secrets
- Intentionally restricted (security boundary)

**For Approach 1 (Manual kubectl):**
- Requires cluster-admin credentials
- One-time deployment from admin context
- Ongoing operations need elevated access

**For Approach 2 (ArgoCD):**
- ArgoCD needs cluster-admin (standard)
- ArgoCD handles all deployments
- Devpods only need ArgoCD read access

**For Approach 4 (GitHub Actions):**
- kubeconfig secret with cluster-admin
- Stored in GitHub secrets
- Workflow runs with elevated permissions

### Secrets Management

**Current State:**
- `botburrow-agents-secrets-PLACEHOLDER.yml` exists
- Cannot be applied by workers (RBAC)
- Requires cluster-admin to create

**Recommendation:** Use SealedSecrets for production
```bash
# Create sealed secret from template
cp botburrow-agents-secret.yml.template /tmp/secrets.yml
# Edit with real values
kubeseal --format yaml < /tmp/secrets.yml > botburrow-agents-sealedsecret.yml
# Add to kustomization.yaml and commit
```

---

## Existing Work and Documentation

### Already Implemented

1. **Simplified Deployment Guide** (`DEPLOYMENT-SIMPLIFIED.md`)
   - MVP deployment with kubectl
   - Deferred components documented
   - Troubleshooting guide included

2. **Simplified Kustomization** (`kustomization-simplified.yaml`)
   - Minimal resource set
   - Manual deployment labels
   - Ready to use

3. **Secrets Setup Guide** (`SECRET_SETUP.md`)
   - Placeholder secrets approach
   - SealedSecrets instructions
   - Key reference documentation

4. **Secrets Research** (`RESEARCH-secrets-management-approaches.md`)
   - Detailed comparison of secret management options
   - SealedSecrets recommendation
   - Implementation steps

### Related Beads

- **bd-1v9**: Original bead (closed as resolved via alternative)
- **bd-2z6**: This bead (research alternative)
- **bd-30r**: Deployment health verification research (completed)
- **bd-3s2**: Worker activation testing (blocked by deployment)
- **bd-3mqz**: Human bead for ArgoCD access check

---

## Recommended Approach

### Primary Recommendation: **Approach 1 (Manual kubectl) → Approach 2 (ArgoCD)**

**Rationale:**

**Phase 1: Immediate Deployment (Manual kubectl)**
- Use `kustomization-simplified.yaml` to deploy immediately
- Bypasses ArgoCD requirement
- Gets system running while ArgoCD is being set up
- Already documented and ready to use

**Phase 2: Production Deployment (ArgoCD)**
- Install ArgoCD in apexalgo-iad cluster
- Configure ApplicationSet for botburrow-agents
- Convert to true GitOps workflow
- Enables multi-cluster deployments

**Why This Hybrid Approach:**
1. **Immediate value** - deploy now, optimize later
2. **Risk mitigation** - test with manual, then automate
3. **Learning opportunity** - understand system before GitOps
4. **Production-ready** - end state is proper GitOps
5. **Flexibility** - can pause at Phase 1 if needed

### Implementation Timeline

**Week 1: Manual Deployment**
```bash
# Day 1: Create secrets
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Day 2: Deploy simplified stack
kubectl apply -k k8s/apexalgo-iad/ --context=apexalgo-iad

# Day 3-5: Verify and test
kubectl get pods -n botburrow-agents
kubectl logs -n botburrow-agents -l app.kubernetes.io/component=runner
```

**Week 2: ArgoCD Setup**
```bash
# Day 1: Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Day 2: Create ApplicationSet
kubectl apply -f k8s/apexalgo-iad/argocd-applicationset.yaml

# Day 3: Verify sync
# Check ArgoCD UI or CLI for sync status

# Day 4-5: Convert secrets to SealedSecrets
# See SECRET_SETUP.md for instructions
```

**Week 3: Production Migration**
- Update kustomization to use `kustomization-full.yaml`
- Verify all components syncing via ArgoCD
- Remove manual deployment workflow
- Document GitOps process

---

## Next Steps (Human Decision Required)

### Decision Point 1: Deployment Method

**Question:** Which approach should we use for deploying botburrow-agents?

**Options:**
1. **Manual kubectl** - Deploy immediately, optimize later
2. **ArgoCD** - Install ArgoCD, then deploy
3. **Flux** - Alternative GitOps solution
4. **GitHub Actions** - CI/CD deployment
5. **Wait** - No deployment until decision

### Decision Point 2: Secrets Management

**Question:** How should we manage secrets for botburrow-agents?

**Options:**
1. **Placeholder secrets** - Manual creation, update in-place
2. **SealedSecrets** - GitOps-native encrypted secrets
3. **External Secrets** - Sync from external vault
4. **Manual only** - No secrets in git

### Decision Point 3: Cluster Access

**Question:** How should we handle cluster-admin access for deployment?

**Options:**
1. **Human deployment** - Cluster-admin deploys manually
2. **ServiceAccount elevation** - Grant devpod-observer create permissions
3. **GitOps automation** - ArgoCD/Flux handles deployment
4. **GitHub Actions** - CI/CD with elevated credentials

---

## Appendix: Quick Reference

### Check Current Deployment Status
```bash
# Check if namespace exists
kubectl get namespace botburrow-agents

# Check if resources are deployed
kubectl get all -n botburrow-agents

# Check ArgoCD installation
kubectl get applications.argoproj.io -A
kubectl get namespace argocd

# Check Flux installation
kubectl get namespace flux-system
kubectl get kustomizations.kustomize.toolkit.fluxcd.io -A
```

### Manual Deployment Commands
```bash
# Create placeholder secrets
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Deploy with simplified kustomization
kubectl apply -k k8s/apexalgo-iad/

# Verify deployment
kubectl get pods -n botburrow-agents -w
```

### ArgoCD Installation Commands
```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access ArgoCD UI (port-forward)
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

### Verify Deployment Health
```bash
# Check all pods are running
kubectl get pods -n botburrow-agents

# Check deployments are ready
kubectl get deployments -n botburrow-agents

# Check pod logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/component=runner --tail=50

# Check metrics endpoint (if service accessible)
kubectl exec -n botburrow-agents <pod-name> -- curl -s http://localhost:9090/metrics | head -20
```

---

## Related Files

- `k8s/apexalgo-iad/kustomization.yaml` - Full ArgoCD kustomization
- `k8s/apexalgo-iad/kustomization-simplified.yaml` - Manual deployment kustomization
- `k8s/apexalgo-iad/DEPLOYMENT-SIMPLIFIED.md` - Manual deployment guide
- `k8s/apexalgo-iad/SECRET_SETUP.md` - Secrets setup instructions
- `k8s/apexalgo-iad/RESEARCH-secrets-management-approaches.md` - Secrets management research
- `docs/research/bd-30r-deployment-health-verification-approaches.md` - Health verification research

---

## Conclusion

The botburrow-agents deployment is blocked because ArgoCD is not installed in the apexalgo-iad cluster, but the manifests are configured for ArgoCD GitOps. This research document presents five approaches:

1. **Manual kubectl** - Immediate deployment, bypass GitOps
2. **Install ArgoCD** - True GitOps, requires setup
3. **Use Flux** - Alternative GitOps, CLI-focused
4. **GitHub Actions** - CI/CD deployment, no in-cluster GitOps
5. **No Deployment** - Wait for human decision

The recommended approach is a **hybrid**: deploy manually first for immediate value, then migrate to ArgoCD for production GitOps workflow. This provides both immediate results and long-term maintainability.

**Human decision required** to proceed with deployment.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47)
