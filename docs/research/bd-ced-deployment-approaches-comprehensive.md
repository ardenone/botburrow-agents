# BD-CED: Comprehensive Deployment Approaches Comparison

**Date:** 2026-02-08
**Bead:** bd-ced (Alternative: Research and document options)
**Original Issue:** bd-1v9 - Fix botburrow-agents deployment via ArgoCD

---

## Executive Summary

This document provides a comprehensive comparison of all possible deployment approaches for the botburrow-agents system to the apexalgo-iad cluster. The research consolidates findings from multiple previous research documents and provides a clear decision framework for choosing the appropriate deployment method.

### Key Finding

**The root cause of the deployment issue is that ArgoCD is not installed in the apexalgo-iad cluster.** All deployment manifests exist and are syntactically valid, but the GitOps automation cannot function because ArgoCD itself is not present.

### Existing Documentation

This research consolidates findings from:
- `docs/deployment-alternatives-research.md` - 7 approaches with detailed comparison
- `docs/research/bd-ced-research-summary.md` - 5 approaches summary
- `docs/research/bd-2z6-argocd-deployment-approaches.md` - Comprehensive ArgoCD research (694 lines)
- `k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md` - Minimal deployment guide
- `docs/SIMPLIFIED_DEPLOYMENT.md` - Simplified deployment guide
- `scripts/deploy-workaround.sh` - Automated deployment script

---

## Problem Statement

### Current Situation

| Aspect | Status |
|--------|--------|
| **Namespace** | `botburrow-agents` exists in apexalgo-iad cluster |
| **ArgoCD** | **NOT INSTALLED** in apexalgo-iad cluster |
| **Resources Deployed** | Zero - no deployments, services, or pods |
| **Git State** | All manifests exist in repo, pushed to GitHub |
| **Manifest Validity** | All manifests pass `kubectl apply --dry-run=client` |

### Expected Deployment Architecture

```
apexalgo-iad cluster
└── botburrow-agents namespace
    ├── RBAC (ServiceAccount, Role, RoleBinding)
    ├── ConfigMaps (app config, agent definitions, permissions)
    ├── Secrets (hub credentials, API keys, MCP credentials)
    ├── Valkey (Redis/Valkey for leader election)
    ├── Coordinator (2 replicas - manages agent lifecycles)
    ├── Runners:
    │   ├── runner-hybrid (2 replicas, scales to 20)
    │   ├── runner-exploration (1 replica)
    │   └── runner-notification (2 replicas, scales to 10)
    ├── HPA (HorizontalPodAutoscaler)
    └── ServiceMonitor (Prometheus metrics)
```

---

## Deployment Approaches Comparison

### Approach 1: Direct kubectl Deployment (RECOMMENDED FOR IMMEDIATE DEPLOYMENT)

**Description:** Deploy resources directly using `kubectl apply -k` with the minimal kustomization.

**Implementation:**
```bash
# Step 1: Apply placeholder secrets (cluster-admin required)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Step 2: Deploy minimal components
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml

# Step 3: Verify deployment
kubectl get pods -n botburrow-agents

# Step 4: Update secrets with real values
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
kubectl edit secret mcp-credentials -n botburrow-agents

# Step 5: Restart runners to pick up new secrets
kubectl rollout restart deployment/runner-hybrid -n botburrow-agents
```

**Automated Script Available:**
```bash
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh
```

**Pros:**
- Immediate deployment - works right now
- Simple - standard kubectl workflow
- Full control over deployment order
- No dependency on external services
- Already documented and scripted
- Reversible with `kubectl delete -k`
- Minimal viable deployment validates core functionality

**Cons:**
- Not GitOps - deployment state not tracked in git
- Manual updates required for changes
- Drift risk - cluster can diverge from git state
- Cluster-admin required for initial secret creation
- No automatic sync on git changes

**Risk Level:** Low (operational risk, technical debt from not using GitOps)

**Best For:** Immediate deployment, development/testing, proof-of-concept, getting unblocked

**What Gets Deployed (Minimal):**
- valkey (Redis/Valkey for leader election)
- runner-hybrid (2 replicas - handles all work types)
- RBAC (ServiceAccount, Role, RoleBinding)
- ConfigMaps (application configuration)

---

### Approach 2: Install and Configure ArgoCD (RECOMMENDED FOR PRODUCTION)

**Description:** Install ArgoCD in apexalgo-iad cluster and configure for GitOps deployment.

**Implementation:**
```bash
# Step 1: Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Step 2: Access ArgoCD UI (port-forward)
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Step 3: Get initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d

# Step 4: Create ApplicationSet for botburrow-agents
kubectl apply -f k8s/apexalgo-iad/argocd-applicationset.yaml

# Step 5: Create SealedSecret for secrets
kubeseal --format yaml < botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml
git add botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret"
git push

# Step 6: Monitor sync in ArgoCD UI
```

**Pros:**
- True GitOps - everything tracked in git
- Automated sync - push to git triggers deployment
- Self-healing - drift detection and auto-correction
- Easy rollback - revert via git
- Multi-cluster support
- Proper audit trail via git history
- Aligns with cluster management standards

**Cons:**
- Additional infrastructure - ArgoCD namespace, pods, resources
- Complexity - learning curve for ArgoCD
- Resource overhead - ArgoCD components use resources
- Initial setup - requires cluster-admin
- Delay to deployment - must install ArgoCD first

**Risk Level:** Low (infrastructure change, but industry standard)

**Best For:** Production environments, multi-cluster deployments, teams wanting GitOps

**Resource Requirements:**
- ArgoCD components: ~2-3 GB memory, ~2-3 CPU cores
- Additional namespace: `argocd`
- Storage: ArgoCD can use cluster storage for configs

---

### Approach 3: Helm Chart Deployment

**Description:** Package the manifests as a Helm chart and deploy via Helm.

**Implementation:**
```bash
# Step 1: Convert manifests to Helm chart
helm create botburrow-agents-chart
# Copy manifests to templates/, add values.yaml

# Step 2: Deploy
helm install botburrow-agents ./botburrow-agents-chart \
  --namespace botburrow-agents \
  --kubeconfig=/path/to/kubeconfig \
  --set hub.apiKey=xxx \
  --set hub.apiSecret=xxx

# Step 3: Upgrade
helm upgrade botburrow-agents ./botburrow-agents-chart
```

**Pros:**
- Standard packaging format
- Easy upgrades via `helm upgrade`
- Values-based configuration
- Can integrate with ArgoCD later via Helm release
- Good for multi-environment deployments
- Rollback support: `helm rollback`

**Cons:**
- Requires converting manifests to Helm format
- Adds another tool dependency
- More complex than direct kubectl
- Still bypasses current ArgoCD setup
- Requires value files for secrets management
- Additional learning curve

**Risk Level:** Medium (tool complexity, not industry standard for this use case)

**Best For:** Teams already using Helm, multi-environment deployments

---

### Approach 4: Create Standalone ArgoCD Application

**Description:** Create a dedicated Application manifest for botburrow-agents instead of relying on ApplicationSet auto-discovery.

**Implementation:**
```yaml
# k8s/apexalgo-iad/argocd-application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: botburrow-agents
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/jedarden/botburrow-agents
    targetRevision: main
    path: k8s/apexalgo-iad
    kustomize:
      images:
        - name: ghcr.io/botburrow/botburrow-agents
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

**Pros:**
- Bypasses potential ApplicationSet issues
- Direct control over Application configuration
- Can enable auto-sync and prune
- Still GitOps-compliant
- Easier to debug than ApplicationSet
- No additional infrastructure

**Cons:**
- Requires ArgoCD to be installed first
- Duplicates ApplicationSet functionality
- Manual Application management
- May conflict with ApplicationSet if not excluded

**Risk Level:** Low (assuming ArgoCD is installed)

**Best For:** Teams wanting fine-grained control over ArgoCD applications

**Note:** This approach is only viable if ArgoCD is installed (see Approach 2)

---

### Approach 5: GitHub Actions Kubernetes Deployment

**Description:** Use GitHub Actions to deploy directly to Kubernetes on git push.

**Implementation:**
```yaml
# .github/workflows/deploy-k8s.yml
name: Deploy to Kubernetes
on:
  push:
    branches: [main]
    paths: ['k8s/**']
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Kubernetes
        uses: azure/k8s-deploy@v4
        with:
          manifests: |
            k8s/apexalgo-iad/namespace.yaml
            k8s/apexalgo-iad/rbac.yaml
            k8s/apexalgo-iad/configmap.yaml
            k8s/apexalgo-iad/valkey.yaml
            k8s/apexalgo-iad/runner-hybrid.yaml
          kubeconfig: ${{ secrets.KUBECONFIG }}
          namespace: botburrow-agents
```

**Pros:**
- Git-triggered deployments
- No dependency on ArgoCD
- Can integrate with CI/CD pipeline
- Works with existing GitHub Actions
- Familiar workflow for many teams
- Good logging via GitHub Actions

**Cons:**
- Not true GitOps (push-based, not pull-based)
- Requires GitHub Actions runner with kubectl access
- Credentials in GitHub Secrets
- No automatic drift detection
- May conflict with ArgoCD if both manage same resources
- External service dependency

**Risk Level:** Medium (credentials management, no drift detection)

**Best For:** Teams preferring CI/CD over GitOps, simpler deployments

---

### Approach 6: Flux CD Alternative

**Description:** Replace ArgoCD with Flux CD for GitOps deployment.

**Implementation:**
```yaml
# k8s/apexalgo-iad/gotk-kustomization.yaml
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
```

**Pros:**
- Alternative GitOps tool
- May avoid ArgoCD-specific issues
- Good Kubernetes-native integration
- Simpler than ArgoCD for some use cases
- Lighter resource footprint

**Cons:**
- Major infrastructure change
- Requires installing Flux CD
- Learning curve for team
- Not aligned with cluster standard (ArgoCD)
- Duplicate tooling if ArgoCD is added later
- CLI-focused vs ArgoCD's UI

**Risk Level:** High (major infrastructure change, not aligned with cluster standards)

**Best For:** Teams wanting to switch from ArgoCD entirely, CLI-focused workflows

---

### Approach 7: SealedSecret-First Approach

**Description:** Focus on fixing the SealedSecret deployment issue first, as this may be enabling ArgoCD sync.

**Root Cause Hypothesis:** Even if ArgoCD were installed, the lack of SealedSecrets might be blocking sync.

**Implementation:**
```bash
# Step 1: Check if SealedSecret controller is running
kubectl get pods -n sealed-secrets

# Step 2: Check if SealedSecret exists
kubectl get sealedsecret botburrow-agents-secrets -n botburrow-agents

# Step 3: Create SealedSecret from template
cp k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml /tmp/secrets.yml
# Fill in real values
kubeseal --format yaml < /tmp/secrets.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret for botburrow-agents"
git push

# Step 4: Verify unsealing
kubectl get secret botburrow-agents-secrets -n botburrow-agents
```

**Pros:**
- Addresses likely root cause
- Minimal change to architecture
- Maintains GitOps
- Once secret is deployed, ArgoCD may sync successfully
- Best practice for secrets management

**Cons:**
- Requires cluster-admin access to create SealedSecret
- Still depends on ArgoCD being installed
- May not be the actual issue (ArgoCD not installed)
- Requires SealedSecret controller

**Risk Level:** Low (infrastructure improvement)

**Best For:** When SealedSecret is the suspected blocker, preparing for ArgoCD deployment

---

## Comparison Matrix

| Approach | GitOps | Speed | Complexity | Infrastructure | Risk | Maintainability | Best For |
|----------|--------|-------|------------|----------------|------|-----------------|----------|
| **1. kubectl Apply** | No | Fast | Low | None | Low | Low | Immediate deployment, testing |
| **2. Install ArgoCD** | Yes | Slow | Medium | ArgoCD | Low | High | Production, GitOps |
| **3. Helm Chart** | Partial | Medium | High | None | Medium | Medium | Helm users |
| **4. Standalone App** | Yes | Medium | Low | ArgoCD | Low | High | Fine-grained ArgoCD control |
| **5. GitHub Actions** | No | Fast | Medium | GitHub | Medium | Medium | CI/CD-centric teams |
| **6. Flux CD** | Yes | Slow | High | Flux | High | Medium | CLI-focused teams |
| **7. SealedSecret-First** | Yes | Medium | Low | SealedSecret | Low | High | Preparing for ArgoCD |

---

## Decision Framework

### Choose Approach 1 (kubectl Apply) if:
- You need deployment **immediately** (today)
- You're in **development/testing** phase
- You **don't have ArgoCD** and won't install it now
- You want **full control** over deployment
- You're comfortable with manual operations
- **Getting unblocked is the priority**

### Choose Approach 2 (Install ArgoCD) if:
- You want **true GitOps** workflow
- You're deploying to **production**
- You have **multiple clusters** to manage
- You want **automated sync** and self-healing
- You can install additional infrastructure
- **Long-term maintainability is the priority**

### Choose Approach 4 (Standalone App) if:
- ArgoCD is **already installed**
- You want **fine-grained control** over the Application
- ApplicationSet is **not working** for this namespace
- You need to **debug** sync issues

### Choose Approach 5 (GitHub Actions) if:
- You already use **GitHub Actions heavily**
- You have a **single cluster**
- You want to **avoid in-cluster GitOps**
- You're comfortable with credentials in GitHub

### Choose Approach 7 (SealedSecret-First) if:
- You're planning to install ArgoCD (Approach 2)
- You want to follow **best practices** for secrets
- You need to prepare for **GitOps deployment**

---

## Recommendations

### Primary Recommendation: **Two-Phase Hybrid Approach**

#### Phase 1: Immediate Deployment (Approach 1 - kubectl Apply)
**Timeline:** Today
**Goal:** Get botburrow-agents deployed and running immediately

```bash
# Deploy now using minimal kustomization
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh

# Or manually
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

**Benefits:**
- Immediate value - deploy now, optimize later
- Risk mitigation - test with manual, then automate
- Learning opportunity - understand system before GitOps
- Unblocks dependent work

#### Phase 2: Production Deployment (Approach 2 + 7 - ArgoCD + SealedSecrets)
**Timeline:** After Phase 1 validation
**Goal:** Migrate to proper GitOps workflow

```bash
# Step 1: Create SealedSecrets
kubeseal --format yaml < botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml
git add botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret"
git push

# Step 2: Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Step 3: Create ApplicationSet
kubectl apply -f k8s/apexalgo-iad/argocd-applicationset.yaml

# Step 4: Monitor sync in ArgoCD UI
```

**Benefits:**
- True GitOps - everything tracked in git
- Automated sync - push to git triggers deployment
- Self-healing - drift detection and auto-correction
- Production-ready

---

## Next Steps

### Immediate Actions (Today)

1. **Deploy via kubectl** to get unblocked:
   ```bash
   cd /home/coder/botburrow-agents
   ./scripts/deploy-workaround.sh
   ```

2. **Verify deployment**:
   ```bash
   kubectl get pods -n botburrow-agents
   kubectl logs -f deployment/runner-hybrid -n botburrow-agents
   ```

3. **Update secrets** with real values:
   ```bash
   kubectl edit secret botburrow-agents-secrets -n botburrow-agents
   kubectl edit secret mcp-credentials -n botburrow-agents
   kubectl rollout restart deployment/runner-hybrid -n botburrow-agents
   ```

### Planning Actions (This Week)

1. **Decide on ArgoCD**: Schedule ArgoCD installation for apexalgo-iad
2. **Create SealedSecrets**: Prepare encrypted secrets for GitOps
3. **Plan migration**: Document transition from kubectl to ArgoCD

### Follow-up Actions (Next Sprint)

1. **Install ArgoCD** in apexalgo-iad cluster
2. **Create ApplicationSet** for botburrow-agents
3. **Validate GitOps workflow**
4. **Document operational procedures**

---

## Quick Reference Commands

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

### Manual Deployment (Approach 1)
```bash
# Create placeholder secrets
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Deploy with minimal kustomization
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml

# Verify deployment
kubectl get pods -n botburrow-agents -w
```

### ArgoCD Installation (Approach 2)
```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access ArgoCD UI (port-forward)
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

### Cleanup
```bash
# Delete all resources (kubectl approach)
kubectl delete -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml

# Delete namespace
kubectl delete namespace botburrow-agents
```

---

## Related Documentation

### Existing Research Documents
1. `docs/deployment-alternatives-research.md` - 7 approaches with detailed comparison
2. `docs/research/bd-ced-research-summary.md` - 5 approaches summary
3. `docs/research/bd-2z6-argocd-deployment-approaches.md` - Comprehensive ArgoCD research (694 lines)
4. `docs/research/bd-2yb-simplified-approach-summary.md` - Simplified approach details

### Deployment Guides
1. `k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md` - Minimal deployment guide
2. `docs/SIMPLIFIED_DEPLOYMENT.md` - Simplified deployment guide
3. `scripts/preflight-check.sh` - Preflight validation script
4. `scripts/deploy-workaround.sh` - Automated deployment script

### Kustomization Files
1. `k8s/apexalgo-iad/kustomization.yaml` - Full ArgoCD configuration
2. `k8s/apexalgo-iad/kustomization-full.yaml` - Full deployment with ArgoCD labels
3. `k8s/apexalgo-iad/kustomization-simplified.yaml` - Simplified deployment for kubectl
4. `k8s/apexalgo-iad/kustomization-minimal.yaml` - Minimal viable deployment

### Related Beads
- **bd-1v9**: Original bead (closed as resolved via alternative)
- **bd-cni**: Workaround implementation bead (closed)
- **bd-2yb**: Simplified requirements approach (completed)
- **bd-2z6**: Comprehensive ArgoCD research (completed)
- **bd-ced**: This bead (comprehensive comparison)

---

## Conclusion

The botburrow-agents deployment is blocked because **ArgoCD is not installed** in the apexalgo-iad cluster. This document consolidates research from multiple previous investigations and provides a comprehensive comparison of 7 deployment approaches:

1. **kubectl Apply** - Immediate deployment, bypass GitOps
2. **Install ArgoCD** - True GitOps, requires setup
3. **Helm Chart** - Standard packaging, additional complexity
4. **Standalone ArgoCD App** - Fine-grained control, requires ArgoCD
5. **GitHub Actions** - CI/CD deployment, no in-cluster GitOps
6. **Flux CD** - Alternative GitOps, major infrastructure change
7. **SealedSecret-First** - Prepare for ArgoCD, best practices

**Recommended Approach:** Two-phase hybrid - deploy immediately via kubectl (Phase 1), then migrate to ArgoCD for production GitOps (Phase 2).

**Human Decision Required:** Choose deployment approach and timeline for ArgoCD installation.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47)
**Bead:** bd-ced
