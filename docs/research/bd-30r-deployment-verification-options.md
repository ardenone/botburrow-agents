# botburrow-agents Deployment Health Verification: Options Research

**Alternative Bead:** bd-30r
**Original Bead:** bd-38r - Verify botburrow-agents deployment health
**Research Approach:** Create detailed comparison document of possible approaches
**Date:** 2026-02-08
**Status:** Research Complete - Awaiting Human Decision

---

## Executive Summary

This research document analyzes options for verifying the health of the botburrow-agents deployment in the apexalgo-iad Kubernetes cluster. The original task (bd-38r) was blocked by a critical discovery: **ArgoCD is NOT installed in apexalgo-iad cluster**, which means the GitOps deployment method cannot work as designed.

This document presents:
1. The root cause of the deployment issue
2. Multiple resolution approaches with trade-offs
3. Recommendations for immediate and long-term solutions

---

## Current State Analysis

### The Problem: Deployment Not Found

The `botburrow-agents` namespace exists but contains **ZERO deployed resources**:

```
$ kubectl get all -n botburrow-agents
No resources found in botburrow-agents namespace.
```

**Expected resources** (not deployed):
- `coordinator` Deployment (2 replicas)
- `runner-hybrid`, `runner-notification`, `runner-exploration` Deployments
- `valkey` StatefulSet (Redis/Valkey)
- Services, ConfigMaps, SealedSecrets

### Root Cause: ArgoCD Not Installed

**CRITICAL FINDING:** ArgoCD is NOT deployed in apexalgo-iad cluster.

```bash
# Checked for ArgoCD in apexalgo-iad:
$ kubectl get applications.argoproj.io -A
error: the server doesn't have a resource type "applications"

$ kubectl get ns | grep -i argo
# (no output - no ArgoCD namespace)
```

**Impact:**
- The Kustomization manifest has `managed-by: argocd` label
- No ArgoCD controller exists to sync manifests from git
- ApplicationSet cannot create or sync resources
- Deployment via GitOps is **impossible** without ArgoCD

### Secondary Issue: RBAC Restrictions

The `devpod-observer` ServiceAccount (used for kubectl access from devpods) lacks permissions to create resources:

```
Error: User "system:serviceaccount:devpod-observer:devpod-observer"
cannot create resource "deployments" in API group "apps"
in the namespace "botburrow-agents"
```

---

## Resolution Options

### Option 1: Install ArgoCD in apexalgo-iad (GitOps Approach)

**Description:** Install ArgoCD in the apexalgo-iad cluster and configure it to manage botburrow-agents.

**Implementation:**

```bash
# 1. Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 2. Create ApplicationSet for botburrow-agents
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: botburrow-agents
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/ardenone/ardenone-cluster
        revision: HEAD
        directories:
          - path: cluster-configuration/apexalgo-iad/botburrow-agents
  template:
    metadata:
      name: botburrow-agents
    spec:
      project: default
      source:
        repoURL: https://github.com/ardenone/ardenone-cluster
        targetRevision: HEAD
        path: '{{path}}'
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
- Proper GitOps workflow (desired state in git)
- Automatic sync and self-healing
- Rollback capabilities via ArgoCD
- UI for deployment visualization
- Multi-cluster management (if needed later)
- Audit trail of all changes

**Cons:**
- Additional infrastructure to maintain (ArgoCD)
- Requires cluster-admin to install
- Learning curve for team
- Additional resource usage (memory/CPU)
- Another service to monitor
- Initial setup complexity

**Effort:** Medium-High (initial install), Low (ongoing)
**Maintenance:** Medium

**Use Case:** Recommended for production GitOps workflow

---

### Option 2: Direct kubectl Apply with Cluster Admin (Manual Approach)

**Description:** Apply manifests directly using kubectl with cluster-admin credentials, bypassing GitOps temporarily.

**Implementation:**

```bash
# Requires cluster-admin access to apexalgo-iad
kubectl apply -k /home/coder/botburrow-agents/k8s/apexalgo-iad/

# Or apply individual manifests
kubectl apply -f k8s/apexalgo-iad/namespace.yaml
kubectl apply -f k8s/apexalgo-iad/rbac.yaml
kubectl apply -f k8s/apexalgo-iad/configmap.yaml
kubectl apply -f k8s/apexalgo-iad/valkey.yaml
kubectl apply -f k8s/apexalgo-iad/coordinator.yaml
kubectl apply -f k8s/apexalgo-iad/runner-hybrid.yaml
kubectl apply -f k8s/apexalgo-iad/runner-notification.yaml
kubectl apply -f k8s/apexalgo-iad/runner-exploration.yaml
kubectl apply -f k8s/apexalgo-iad/skill-sync.yaml
kubectl apply -f k8s/apexalgo-iad/hpa.yaml
kubectl apply -f k8s/apexalgo-iad/servicemonitor.yaml
```

**Pros:**
- Immediate deployment possible
- No additional infrastructure
- Simple and direct
- Full control over deployment
- No learning curve

**Cons:**
- Breaks GitOps principle (state divergence)
- Manual deployment required for updates
- No automatic sync from git
- No self-healing
- Configuration drift risk
- Requires cluster-admin access each time

**Effort:** Low (one-time), Medium (ongoing manual updates)
**Maintenance:** High (manual process)

**Use Case:** Quick fix, testing, or if ArgoCD installation is delayed

---

### Option 3: Hybrid - Manual Initial Deploy + Add GitOps Later

**Description:** Deploy manually now, install ArgoCD later, then migrate to GitOps.

**Implementation:**

```bash
# Phase 1: Manual deployment (immediate)
kubectl apply -k /home/coder/botburrow-agents/k8s/apexalgo-iad/

# Verify deployment
./scripts/simplified-health-check.sh

# Phase 2: Install ArgoCD (later)
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Phase 3: Create Application (later)
# ArgoCD will adopt existing resources and manage going forward
kubectl apply -f botburrow-agents-application.yaml
```

**Pros:**
- Unblocks deployment immediately
- Migrates to proper GitOps when ready
- Low risk (existing resources adopted)
- Flexible timeline

**Cons:**
- Two-step process
- Temporary configuration drift
- Migration effort required
- Manual verification needed during migration

**Effort:** Low (initial), Medium (migration)
**Maintenance:** Low (after migration)

**Use Case:** Immediate need + long-term GitOps goal

---

### Option 4: Use Existing Devpod Automation Script

**Description:** Leverage existing verification scripts for deployment validation.

**Implementation:**

The repository already has comprehensive health check scripts:

```bash
# Run simplified health check (already implemented)
./scripts/simplified-health-check.sh

# Run full deployment verification
./scripts/verify-deployment.sh

# Quick check (from docs/verification/quick-check.md)
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get pods -n botburrow-agents
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=50
```

**Pros:**
- Already implemented and tested
- No new code required
- Quick to run
- Multiple verification levels

**Cons:**
- Only validates, doesn't deploy
- Requires deployment to exist first

**Effort:** None (already exists)
**Maintenance:** Low

**Use Case:** Post-deployment verification (all options)

---

### Option 5: GitHub Actions Direct Deploy (CI/CD Approach)

**Description:** Use GitHub Actions to deploy directly to apexalgo-iad cluster, bypassing ArgoCD.

**Implementation:**

```yaml
# .github/workflows/deploy-apexalgo-iad.yml
name: Deploy to apexalgo-iad
on:
  push:
    branches: [main]
    paths:
      - 'botburrow-agents/**'
      - 'cluster-configuration/apexalgo-iad/botburrow-agents/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Configure kubectl
        run: |
          echo "${{ secrets.APEXALGO_IAD_KUBECONFIG }}" > kubeconfig
          export KUBECONFIG=kubeconfig
      - name: Deploy manifests
        run: |
          kubectl apply -k cluster-configuration/apexalgo-iad/botburrow-agents/
          kubectl rollout status deployment/coordinator -n botburrow-agents
      - name: Verify deployment
        run: |
          kubectl get pods -n botburrow-agents
```

**Pros:**
- Automated deployment on git push
- CI/CD integration
- Deployment status in GitHub
- No additional cluster infrastructure

**Cons:**
- Requires GitHub Actions runner with kubectl access
- Credential management (kubeconfig in GitHub Secrets)
- No ArgoCD UI or rollback
- Self-healing not automatic

**Effort:** Medium
**Maintenance:** Medium

**Use Case:** CI/CD-focused workflow without ArgoCD

---

### Option 6: Terraform/Ansible Infrastructure as Code

**Description:** Use Terraform or Ansible for deployment management.

**Implementation:**

```hcl
# Terraform example
resource "kubernetes_deployment" "coordinator" {
  metadata {
    name = "coordinator"
    namespace = "botburrow-agents"
  }
  spec {
    # ... deployment spec
  }
}
```

**Pros:**
- Infrastructure as Code
- State management
- Drift detection
- Multi-tool support

**Cons:**
- New toolchain requirement
- Additional complexity
- Learning curve
- Overkill for single namespace

**Effort:** High
**Maintenance:** Medium

**Use Case:** Large-scale infrastructure management

---

## Comparison Matrix

| Option | GitOps | Immediate | Effort | Maintenance | Best For |
|--------|--------|-----------|--------|-------------|----------|
| **1. Install ArgoCD** | Yes | No | Med-High | Low | Production GitOps |
| **2. Direct kubectl** | No | Yes | Low (one-time) | High | Quick/testing |
| **3. Hybrid** | Yes (later) | Yes | Low-Med | Low (after) | Unblocking + GitOps |
| **4. Use Scripts** | N/A | N/A | None | Low | Verification only |
| **5. GitHub Actions** | Partial | Yes | Medium | Medium | CI/CD focus |
| **6. Terraform** | Yes | No | High | Medium | Large infra |

---

## Health Verification Approaches

Once deployed, the following verification methods are available (existing research from bd-2lb):

### Existing Verification Tools

1. **simplified-health-check.sh** - Quick pod + metrics check
2. **verify-deployment.sh** - Comprehensive verification
3. **verify_leader_election.py** - Leader election verification
4. **verify_metrics.py** - Prometheus metrics verification

### Verification Hierarchy

```
Layer 1: Pod Health (Kubernetes Probes)
  └─> Liveness: Process alive
  └─> Readiness: Dependencies satisfied

Layer 2: Application Health (Enhanced /ready)
  └─> Redis connectivity
  └─> Hub API connectivity
  └─> Work queue status

Layer 3: Service Health (Prometheus Metrics)
  └─> Leader election status
  └─> Queue depth
  └─> Activation rates
  └─> Runner heartbeats

Layer 4: Business Logic Health (E2E Tests)
  └─> End-to-end activation flow
  └─> Work claiming and processing
  └─> Configuration sync

Layer 5: Manual Verification (Scripts)
  └─> Quick deployment check
  └─> Troubleshooting guide
```

---

## Recommendations

### Immediate Action (To Unblock bd-38r)

**Recommended: Option 2 (Direct kubectl) OR Option 3 (Hybrid)**

Given that:
1. The original task bd-38r requires deployment verification
2. ArgoCD is NOT installed in apexalgo-iad
3. The namespace exists but has no resources
4. Worker was blocked on deployment not existing

**Choose based on urgency:**

- **If urgent:** Use Option 2 (Direct kubectl with cluster-admin)
- **If time permits:** Use Option 3 (Hybrid - manual now, ArgoCD later)

### Long-term Strategy

**Recommended: Option 1 (Install ArgoCD)**

For production GitOps workflow:
1. Install ArgoCD in apexalgo-iad
2. Migrate to ApplicationSet-based management
3. Enable automated sync and self-healing
4. Use existing verification scripts for post-deployment checks

### Verification Strategy

Regardless of deployment method, use existing verification tools:

```bash
# 1. Deploy (chosen method)
# 2. Quick health check
./scripts/simplified-health-check.sh

# 3. Full verification
./scripts/verify-deployment.sh

# 4. Ongoing monitoring
# - Prometheus metrics (already configured)
# - Kubernetes probes (already configured)
```

---

## Next Steps (Human Decision Required)

### Decision Point

Please choose ONE of the following approaches:

**A. Install ArgoCD in apexalgo-iad** (Production GitOps)
- Pro: Proper GitOps, self-healing, UI
- Con: Initial setup effort
- Effort: Medium-High (one-time)
- Timeline: 1-2 hours setup + testing

**B. Direct kubectl apply with cluster-admin** (Quick Fix)
- Pro: Immediate deployment
- Con: Manual process, no GitOps
- Effort: Low (one-time)
- Timeline: 15-30 minutes

**C. Hybrid approach** (Unblock now, GitOps later)
- Pro: Immediate + long-term
- Con: Two-step process
- Effort: Low now, Medium later
- Timeline: 15-30 min now, migration later

**D. Alternative solution** (Specify)
- Please describe preferred approach

### After Deployment

Once deployment method is chosen and resources are deployed, the verification can proceed:

```bash
# Run verification
cd /home/coder/botburrow-agents
./scripts/simplified-health-check.sh
./scripts/verify-deployment.sh
```

---

## References

- **Existing Research:** `/home/coder/botburrow-agents/docs/deployment-verification-research-bd-2lb.md`
- **Verification Scripts:** `/home/coder/botburrow-agents/scripts/`
- **Quick Check Guide:** `/home/coder/botburrow-agents/docs/verification/quick-check.md`
- **ArgoCD Installation:** https://argo-cd.readthedocs.io/en/stable/getting_started/
- **Kubernetes Probes:** https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- **Kustomize Documentation:** https://kustomize.io/

---

## Appendix: Related Bead Status

**bd-38r** (CLOSED): "Verify botburrow-agents deployment health"
- Status: Closed (deployment not found, blocked by missing ArgoCD)

**bd-1v9** (CLOSED): "Fix botburrow-agents deployment via ArgoCD"
- Was blocked by human bead for ArgoCD access
- Root cause: ArgoCD not installed in apexalgo-iad

**bd-30r** (IN PROGRESS): This alternative research bead
- Purpose: Document options for human decision

**Dependency Chain:**
```
bd-30r (this research) - IN PROGRESS
  ↓ (informs decision on deployment method)
bd-38r (verify deployment) - CLOSED (blocked)
  ↓
bd-2f8 (fix deployment issues) - BLOCKED by bd-38r
  ↓
bd-13j (build and deploy) - BLOCKED by bd-2f8
```

---

**Document Status:** Research Complete - Awaiting Human Decision
**Generated:** 2026-02-08T08:00:00Z
**Workspace:** /home/coder/botburrow-agents
