# Botburrow-Agents Deployment: Alternative Approaches Research

**Date:** 2026-02-08
**Bead:** bd-ced (Alternative: Research and document options)
**Original Bead:** bd-1v9 (Fix botburrow-agents deployment via ArgoCD)

## Executive Summary

This document provides a comprehensive comparison of alternative approaches for deploying the botburrow-agents system to Kubernetes. The research was commissioned as an alternative to resolving the ArgoCD sync issue that prevented deployment via GitOps.

---

## Problem Context

### Current Situation
- **Namespace Status:** `botburrow-agents` namespace exists in apexalgo-iad cluster
- **ArgoCD Status:** Application `botburrow-agents-ns-apexalgo-iad` exists but only synced the Namespace resource
- **Resources Deployed:** Zero - no deployments, services, or other resources
- **Git State:** All manifests exist in `cluster-configuration/apexalgo-iad/botburrow-agents/` and are pushed to GitHub
- **Hypothesis:** ArgoCD Application sync stalled or failed for unknown reasons (requires ArgoCD UI access to diagnose)

### Deployment Components
The full botburrow-agents deployment consists of:
1. **Namespace** (`namespace.yaml`) - Already created
2. **RBAC** (`rbac.yaml`) - ServiceAccount, Role, RoleBinding
3. **ConfigMaps** (`configmap.yaml`) - App config, agent definitions repo, permissions
4. **Secrets** (`botburrow-agents-secrets-PLACEHOLDER.yml`) - Hub credentials, API keys, MCP credentials
5. **Valkey** (`valkey.yaml`) - Redis-compatible data store
6. **Coordinator** (`coordinator.yaml`) - 2 replicas, manages agent lifecycles
7. **Runners:**
   - `runner-hybrid.yaml` - 2 replicas (scales to 20 via HPA)
   - `runner-exploration.yaml` - 1 replica
   - `runner-notification.yaml` - 2 replicas (scales to 10 via HPA)
8. **HPA** (`hpa.yaml`) - HorizontalPodAutoscaler for runners
9. **ServiceMonitor** (`servicemonitor.yaml`) - Prometheus metrics scraping
10. **Skill Sync** (`skill-sync.yaml`) - Optional skill synchronization

---

## Alternative Approaches

### Option 1: Direct kubectl Apply (Workaround)

**Description:** Deploy resources directly using `kubectl apply -k` with the simplified kustomization.

**Implementation:**
```bash
# Pre-requisite: Create secrets manually
kubectl create secret generic botburrow-agents-secrets \
  --from-literal=HUB_API_KEY=xxx \
  --from-literal=HUB_API_SECRET=xxx \
  --namespace=botburrow-agents

kubectl create secret generic mcp-credentials \
  --from-literal=ZAI_API_KEY=xxx \
  --namespace=botburrow-agents

# Deploy using simplified kustomization
kubectl apply -k k8s/apexalgo-iad/ --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig
```

**Pros:**
- Immediate deployment - bypasses ArgoCD issue entirely
- Uses existing simplified kustomization already prepared
- Full control over deployment order
- No dependency on external services
- Reversible with `kubectl delete -k`

**Cons:**
- Breaks GitOps principle - cluster state diverges from git
- Manual intervention required for secrets
- No automatic sync on git changes
- Must manually re-apply for updates
- Creates technical debt - future ArgoCD sync may conflict

**Risk Level:** Low (technical debt, not operational risk)

**Suitable For:** Quick testing, emergency deployments, proof-of-concept

---

### Option 2: Debug and Fix ArgoCD Application

**Description:** Investigate the root cause of the ArgoCD sync failure and fix the underlying issue.

**Implementation Steps:**
1. Get ArgoCD Application status:
   ```bash
   kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o yaml
   ```
2. Check sync status and health:
   ```bash
   argocd app get botburrow-agents-ns-apexalgo-iad
   ```
3. Identify sync errors from Application status
4. Fix underlying issue (see Common ArgoCD Issues below)
5. Trigger manual sync: `argocd app sync botburrow-agents-ns-apexalgo-iad`

**Common ArgoCD Issues & Fixes:**

| Issue | Symptoms | Fix |
|-------|----------|-----|
| **Missing SealedSecret** | Sync error "Secret not found" | Create `botburrow-agents-sealedsecret.yml` and commit to git |
| **Invalid health check** | Sync stuck "Progressing" | Add `healthCheck` override or fix liveness/readiness probes |
| **Resource quota exceeded** | Sync error "insufficient quota" | Request quota increase or reduce resource requests |
| **CRD not installed** | Sync error "could not find apiVersion" | Install missing CRDs (e.g., SealedSecret) |
| **ApplicationSet not refreshed** | No application created | Re-apply ApplicationSet manifest |
| **Self-healing loop** | Resources keep reverting | Fix divergent live config or disable auto-sync |

**Pros:**
- Maintains GitOps architecture
- Long-term sustainable solution
- Automatic sync on future changes
- Proper audit trail via git history
- Aligns with cluster management standards

**Cons:**
- Requires ArgoCD access (UI or CLI)
- May require investigation time
- Could be blocked by missing permissions
- Root cause might be complex

**Risk Level:** Low (fixing, not bypassing)

**Suitable For:** Production deployments, long-term maintainability

---

### Option 3: Helm Chart Deployment

**Description:** Package the manifests as a Helm chart and deploy via Helm.

**Implementation:**
```bash
# Convert existing manifests to Helm chart
helm create botburrow-agents-chart
# Copy manifests to templates/, add values.yaml

# Deploy
helm install botburrow-agents ./botburrow-agents-chart \
  --namespace botburrow-agents \
  --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig \
  --set hub.apiKey=xxx \
  --set hub.apiSecret=xxx
```

**Pros:**
- Standard packaging format
- Easy upgrades via `helm upgrade`
- Values-based configuration
- Can integrate with ArgoCD later via Helm release
- Good for multi-environment deployments

**Cons:**
- Requires converting manifests to Helm format
- Adds another tool dependency
- More complex than direct kubectl
- Still bypasses current ArgoCD setup
- Requires value files for secrets management

**Risk Level:** Medium

**Suitable For:** Teams already using Helm, multi-cluster deployments

---

### Option 4: Create Standalone ArgoCD Application

**Description:** Instead of relying on the ApplicationSet auto-discovery, create a dedicated Application manifest for botburrow-agents.

**Implementation:**
```yaml
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

**Cons:**
- Duplicates ApplicationSet functionality
- Manual Application management
- Still needs ArgoCD access to create
- May conflict with ApplicationSet if not excluded

**Risk Level:** Low

**Suitable For:** Teams wanting fine-grained control over ArgoCD applications

---

### Option 5: GitHub Actions Kubernetes Deploy

**Description:** Use GitHub Actions to deploy directly to Kubernetes, bypassing ArgoCD entirely.

**Implementation:**
```yaml
# .github/workflows/deploy.yml
name: Deploy to Kubernetes
on:
  push:
    branches: [main]
    paths: ['k8s/**']
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: azure/k8s-deploy@v4
        with:
          manifests: |
            k8s/apexalgo-iad/namespace.yaml
            k8s/apexalgo-iad/rbac.yaml
            k8s/apexalgo-iad/configmap.yaml
            k8s/apexalgo-iad/valkey.yaml
            k8s/apexalgo-iad/coordinator.yaml
            k8s/apexalgo-iad/runner-*.yaml
          kubeconfig: ${{ secrets.KUBECONFIG }}
          namespace: botburrow-agents
```

**Pros:**
- Git-triggered deployments
- No dependency on ArgoCD
- Can integrate with CI/CD pipeline
- Works with existing GitHub Actions
- Good for teams already using GitHub Actions

**Cons:**
- Not true GitOps (push-based, not pull-based)
- Requires GitHub Actions runner with kubectl access
- Credentials in GitHub Secrets
- No automatic drift detection
- May conflict with ArgoCD if both manage same resources

**Risk Level:** Medium

**Suitable For:** Teams preferring CI/CD over GitOps, simpler deployments

---

### Option 6: Flux CD Alternative

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

**Cons:**
- Major infrastructure change
- Requires installing Flux CD
- Learning curve for team
- Not aligned with cluster standard (ArgoCD)
- Duplicate tooling

**Risk Level:** High (major infrastructure change)

**Suitable For:** Teams wanting to switch from ArgoCD entirely

---

### Option 7: SealedSecret-First Approach

**Description:** Focus on fixing the SealedSecret deployment issue first, as this may be blocking ArgoCD sync.

**Root Cause Hypothesis:** ArgoCD may be failing to sync because the SealedSecret doesn't exist or can't be unsealed.

**Implementation:**
```bash
# 1. Check if SealedSecret controller is running
kubectl get pods -n sealed-secrets

# 2. Check if SealedSecret exists
kubectl get sealedsecret botburrow-agents-secrets -n botburrow-agents

# 3. Create SealedSecret from template
cp k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml /tmp/secrets.yml
# Fill in values
kubeseal --format yaml < /tmp/secrets.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret for botburrow-agents"
git push

# 4. Verify unsealing
kubectl get secret botburrow-agents-secrets -n botburrow-agents
```

**Pros:**
- Addresses likely root cause
- Minimal change to architecture
- Maintains GitOps
- Once secret is deployed, ArgoCD may sync successfully

**Cons:**
- Requires cluster-admin access to create SealedSecret
- Still depends on ArgoCD working
- May not be the actual issue

**Risk Level:** Low

**Suitable For:** When missing SealedSecret is the suspected blocker

---

## Comparison Matrix

| Approach | GitOps | Speed | Complexity | Risk | Maintainability |
|----------|--------|-------|------------|------|-----------------|
| 1. kubectl Apply | No | Fast | Low | Medium | Low |
| 2. Fix ArgoCD | Yes | Slow | Medium | Low | High |
| 3. Helm Chart | Partial | Medium | High | Medium | Medium |
| 4. Standalone App | Yes | Medium | Low | Low | High |
| 5. GitHub Actions | No | Fast | Medium | Medium | Medium |
| 6. Flux CD | Yes | Slow | High | High | Medium |
| 7. SealedSecret-First | Yes | Medium | Low | Low | High |

---

## Recommendation

### Primary Recommendation: **Option 2 (Fix ArgoCD) with Option 7 (SealedSecret-First) as First Step**

**Rationale:**
1. **Maintains GitOps architecture** - aligns with cluster standards
2. **Long-term maintainability** - automatic sync, audit trail
3. **Low risk** - fixing existing system rather than bypassing
4. **SealedSecret-first** - addresses most likely root cause immediately

**Implementation Path:**
```bash
# Step 1: Create SealedSecret (most likely issue)
kubeseal --format yaml < botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml
git add botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret"
git push

# Step 2: Wait 2-3 minutes for ArgoCD sync

# Step 3: Check status
kubectl get all -n botburrow-agents

# Step 4: If still empty, check ArgoCD Application
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o yaml
```

### Fallback Recommendation: **Option 1 (kubectl Apply) with Plan to Return to GitOps**

**If ArgoCD cannot be fixed:**
1. Deploy via `kubectl apply -k k8s/apexalgo-iad/`
2. Add label: `app.kubernetes.io/managed-by: manual`
3. Document the workaround
4. Plan to migrate back to GitOps once ArgoCD is fixed

**Rationale:**
- Unblocks deployment immediately
- Reversible with proper labeling
- Temporary measure
- Preserves ability to return to GitOps

---

## Next Steps

1. **Confirm SealedSecret status** - Check if `botburrow-agents-sealedsecret.yml` exists in git
2. **Get ArgoCD access** - Request UI or CLI access to check Application status
3. **Create SealedSecret** if missing - Use `kubeseal` to encrypt secrets
4. **Monitor sync** - After committing, watch for resource deployment
5. **Document decision** - Record which approach was chosen and why

---

## Appendix: Quick Reference Commands

```bash
# Check namespace status
kubectl get namespace botburrow-agents -o yaml

# Check deployed resources
kubectl get all -n botburrow-agents

# Check ArgoCD Application
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o yaml

# Check ApplicationSet
kubectl get applicationset manifest-appset-apexalgo-iad -n argocd -o yaml

# Manual deploy via kubectl
kubectl apply -k k8s/apexalgo-iad/

# Delete all resources (cleanup)
kubectl delete -k k8s/apexalgo-iad/

# Check ArgoCD sync history
kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o jsonpath='{.status.operationState}'

# Trigger manual ArgoCD sync (requires argocd CLI)
argocd app sync botburrow-agents-ns-apexalgo-iad
```
