# BD-CED: Research Summary - botburrow-agents Deployment Options

**Date:** 2026-02-08
**Bead:** bd-ced (Alternative: Research and document options)
**Original Issue:** bd-1v9 - Fix botburrow-agents deployment via ArgoCD

---

## Executive Summary

This research document provides a focused summary of deployment options for botburrow-agents to the apexalgo-iad cluster. **Comprehensive research already exists** in `docs/research/bd-2z6-argocd-deployment-approaches.md` (694 lines, 5 approaches documented).

This document summarizes the key findings and provides actionable recommendations.

---

## Problem Statement

**Original Issue (bd-1v9):**
- The `botburrow-agents` namespace exists but is **EMPTY** (no deployments, pods, or services)
- ArgoCD GitOps was expected to manage deployment but resources were never synced
- Namespace has `argocd.argoproj.io/tracking-id` annotation but ArgoCD is not installed in apexalgo-iad cluster
- All manifests exist and are syntactically valid

**Root Cause:**
ArgoCD is not installed in apexalgo-iad cluster, but the deployment manifests are configured for ArgoCD GitOps.

---

## Deployment Approaches Summary

### Approach 1: Manual kubectl Deployment (Simplified)

**Description:** Deploy directly using kubectl with cluster-admin credentials.

**Status:** Already documented and ready to use.

**Implementation:**
```bash
# Step 1: Create placeholder secrets (requires cluster-admin)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Step 2: Deploy with simplified kustomization
kubectl apply -k k8s/apexalgo-iad/

# Step 3: Verify deployment
kubectl get pods -n botburrow-agents
```

**Pros:**
- Immediate deployment - works right now
- Simple - standard kubectl workflow
- Already documented - `DEPLOYMENT-SIMPLIFIED.md` exists
- No additional infrastructure needed

**Cons:**
- Not GitOps - deployment state not tracked in git
- Manual updates required for changes
- Drift risk - cluster can drift from git state
- Cluster-admin required - cannot be done from devpods

**Best For:** Immediate deployment, development/testing, emergency deployment

---

### Approach 2: Install and Configure ArgoCD

**Description:** Install ArgoCD in apexalgo-iad cluster and configure for GitOps.

**Implementation:**
```bash
# Step 1: Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Step 2: Create ApplicationSet (manifest exists in k8s/apexalgo-iad/)
kubectl apply -f k8s/apexalgo-iad/argocd-applicationset.yaml
```

**Pros:**
- True GitOps - everything tracked in git
- Automated sync - push to git triggers deployment
- Self-healing - drift detection and auto-correction
- Easy rollback - revert via git
- Multi-cluster support

**Cons:**
- Additional infrastructure - ArgoCD namespace, pods, resources
- Complexity - learning curve for ArgoCD
- Resource overhead - ArgoCD components use resources
- Initial setup - requires cluster-admin

**Best For:** Production environments, multi-cluster deployments, teams wanting GitOps

---

### Approach 3: Flux GitOps

**Description:** Use Flux instead of ArgoCD for GitOps deployment.

**Pros:**
- GitOps native - designed for git-driven deployment
- Lighter than ArgoCD - smaller resource footprint
- Kubernetes native - uses CRDs for everything
- Modular - use only components needed

**Cons:**
- CLI-focused vs ArgoCD UI
- Learning curve - different concepts than ArgoCD
- Less mature - smaller community than ArgoCD
- Bootstrap problem - same as ArgoCD

**Best For:** CLI-focused teams, resource-constrained clusters, already using Flux

---

### Approach 4: GitHub Actions Deployment

**Description:** Use GitHub Actions to deploy directly to cluster on push.

**Implementation:**
```yaml
# .github/workflows/deploy-k8s.yml
on:
  push:
    branches: [main]
    paths: ['k8s/**']
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        run: kubectl apply -k k8s/apexalgo-iad/
```

**Pros:**
- Leverages existing CI/CD - GitHub Actions already configured
- Familiar workflow - push, wait, deployed
- Easy rollback - revert commit, re-run workflow
- No cluster GitOps - no ArgoCD/Flux needed
- Good logging - GitHub Actions logs

**Cons:**
- Credentials in GitHub - kubeconfig secret required
- Not continuous - only checks on push
- No drift detection - manual changes not caught
- GitHub Actions dependency - external service required

**Best For:** Projects using GitHub Actions, single-cluster deployments

---

### Approach 5: Keep Current State (No Deployment)

**Description:** Accept empty namespace, document blockers, wait for human decision.

**Pros:**
- Minimal effort - no implementation work
- Forces decision - human must choose path
- Prevents partial work - no half-solutions

**Cons:**
- No deployment - system not running
- Beads blocked - dependent work cannot proceed
- Time lost - waiting for decision

**Best For:** When deployment approach is genuinely unclear, major infrastructure decisions needed

---

## Comparison Matrix

| Approach | GitOps | Automated | Infrastructure | Effort | Rollback | Best For |
|----------|--------|-----------|----------------|--------|----------|----------|
| 1. Manual kubectl | No | No | None | Low | Manual | Quick deployment |
| 2. ArgoCD | Yes | Yes | ArgoCD | High | Git revert | Production |
| 3. Flux | Yes | Yes | Flux | High | Git revert | CLI-focused |
| 4. GitHub Actions | Partial | On push | GitHub | Medium | Git revert | CI/CD-centric |
| 5. No Deployment | N/A | N/A | None | None | N/A | Decision pending |

---

## Existing Documentation

The following documentation already exists in the repository:

### Deployment Guides
1. **`docs/SIMPLIFIED_DEPLOYMENT.md`** - Simplified deployment guide
2. **`k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md`** - Minimal deployment guide
3. **`scripts/preflight-check.sh`** - Preflight validation script

### Research Documents
1. **`docs/research/bd-2z6-argocd-deployment-approaches.md`** - Comprehensive 5-approach comparison (694 lines)
2. **`docs/research/bd-2yb-simplified-approach-summary.md`** - Simplified approach details
3. **`docs/research/deployment-options-research-bd-32a.md`** - Coordinator deployment options

### Kustomization Files
1. **`k8s/apexalgo-iad/kustomization.yaml`** - Full ArgoCD configuration
2. **`k8s/apexalgo-iad/kustomization-full.yaml`** - Full deployment with ArgoCD labels
3. **`k8s/apexalgo-iad/kustomization-simplified.yaml`** - Simplified deployment for kubectl
4. **`k8s/apexalgo-iad/kustomization-minimal.yaml`** - Minimal viable deployment

---

## Recommended Approach

### Primary Recommendation: **Approach 1 (Manual kubectl) → Approach 2 (ArgoCD)**

**Hybrid Two-Phase Approach:**

#### Phase 1: Immediate Deployment (Manual kubectl)
- Use `kustomization-simplified.yaml` to deploy immediately
- Bypasses ArgoCD requirement
- Gets system running while ArgoCD is being set up
- Already documented and ready to use

#### Phase 2: Production Deployment (ArgoCD)
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

---

## Next Steps (Human Decision Required)

### Decision Point 1: Deployment Method

Which approach should we use for deploying botburrow-agents?

**Options:**
1. **Manual kubectl** - Deploy immediately, optimize later
2. **ArgoCD** - Install ArgoCD, then deploy
3. **Flux** - Alternative GitOps solution
4. **GitHub Actions** - CI/CD deployment
5. **Wait** - No deployment until decision

### Decision Point 2: Secrets Management

How should we manage secrets for botburrow-agents?

**Options:**
1. **Placeholder secrets** - Manual creation, update in-place
2. **SealedSecrets** - GitOps-native encrypted secrets
3. **External Secrets** - Sync from external vault
4. **Manual only** - No secrets in git

### Decision Point 3: Cluster Access

How should we handle cluster-admin access for deployment?

**Options:**
1. **Human deployment** - Cluster-admin deploys manually
2. **ServiceAccount elevation** - Grant devpod-observer create permissions
3. **GitOps automation** - ArgoCD/Flux handles deployment
4. **GitHub Actions** - CI/CD with elevated credentials

---

## Quick Reference

### Check Current Deployment Status
```bash
# Check if namespace exists
kubectl get namespace botburrow-agents

# Check if resources are deployed
kubectl get all -n botburrow-agents

# Check ArgoCD installation
kubectl get applications.argoproj.io -A
kubectl get namespace argocd
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

---

## Related Files

- `docs/research/bd-2z6-argocd-deployment-approaches.md` - Comprehensive 5-approach comparison (694 lines)
- `docs/SIMPLIFIED_DEPLOYMENT.md` - Manual deployment guide
- `k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md` - Minimal deployment guide
- `k8s/apexalgo-iad/kustomization.yaml` - Full ArgoCD kustomization
- `k8s/apexalgo-iad/kustomization-simplified.yaml` - Manual deployment kustomization
- `scripts/preflight-check.sh` - Preflight validation script

---

## Related Beads

- **bd-1v9**: Original bead (closed as resolved via alternative)
- **bd-2z6**: Comprehensive ArgoCD research (completed)
- **bd-2yb**: Simplified requirements approach (completed)
- **bd-30r**: Deployment health verification research (completed)
- **bd-ced**: This bead (research summary)

---

## Conclusion

The botburrow-agents deployment is blocked because ArgoCD is not installed in the apexalgo-iad cluster. This research document summarizes five documented approaches:

1. **Manual kubectl** - Immediate deployment, bypass GitOps
2. **Install ArgoCD** - True GitOps, requires setup
3. **Use Flux** - Alternative GitOps, CLI-focused
4. **GitHub Actions** - CI/CD deployment, no in-cluster GitOps
5. **No Deployment** - Wait for human decision

Comprehensive documentation already exists in `docs/research/bd-2z6-argocd-deployment-approaches.md`. The recommended approach is a **hybrid**: deploy manually first for immediate value (Approach 1), then migrate to ArgoCD for production GitOps workflow (Approach 2).

**Human decision required** to proceed with deployment.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47)
**Bead:** bd-ced
