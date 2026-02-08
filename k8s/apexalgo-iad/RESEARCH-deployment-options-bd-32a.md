# Deployment Options Research for botburrow-agents Coordinator Stack

**Research Document for:** bd-32a (Alternative: Research and document options)
**Original Bead:** bd-33k - Deploy botburrow-agents coordinator stack in apexalgo-iad
**Date:** 2026-02-08

## Problem Summary

The botburrow-agents coordinator stack needs to be deployed to the apexalgo-iad cluster. Workers are currently blocked due to:

1. **Secrets Blocker (bd-3qi9):** Required secret values (HUB_API_KEY, R2 credentials, GITHUB_TOKEN, etc.) are not available - this is a cross-workspace human bead requiring human input to provide actual secret values.

2. **RBAC Constraint:** The devpod-observer ServiceAccount has read-only access to the botburrow-agents namespace, preventing direct `kubectl apply` deployment. An admin RBAC manifest exists (`devpod-observer-botburrow-agents-admin-rbac.yml`) but requires cluster-admin to apply first.

3. **ArgoCD Gap:** No ArgoCD Application manifest exists for GitOps-based deployment, which would bypass the RBAC constraint by using ArgoCD's service account.

This document provides a comprehensive comparison of deployment approaches to inform the human decision on how to proceed.

---

## Current State Analysis

### Existing Resources

**Kubernetes Manifests:**
- `k8s/apexalgo-iad/coordinator.yaml` - Coordinator Deployment (2 replicas)
- `k8s/apexalgo-iad/valkey.yaml` - Redis/Valkey StatefulSet
- `k8s/apexalgo-iad/runner-hybrid.yaml` - Hybrid runner Deployment
- `k8s/apexalgo-iad/runner-notification.yaml` - Notification runner
- `k8s/apexalgo-iad/runner-exploration.yaml` - Exploration runner
- `k8s/apexalgo-iad/rbac.yaml` - ServiceAccount, Role, RoleBinding
- `k8s/apexalgo-iad/configmap.yaml` - Configuration
- `k8s/apexalgo-iad/hpa.yaml` - HorizontalPodAutoscaler
- `k8s/apexalgo-iad/servicemonitor.yaml` - Prometheus monitoring

**Kustomizations:**
- `kustomization.yaml` - Full deployment (all components, ArgoCD managed)
- `kustomization-full.yaml` - Full deployment (all components, kubectl managed)
- `kustomization-simplified.yaml` - Simplified deployment (core components only)
- `kustomization-minimal.yaml` - Minimal deployment (valkey + hybrid runner only)

**Secrets:**
- `botburrow-agents-secret.yml.template` - Template with REPLACE_* placeholders
- `botburrow-agents-secrets-PLACEHOLDER.yml` - Placeholder secrets for initial deployment

**RBAC:**
- `devpod-observer-botburrow-agents-admin-rbac.yml` - Grants devpod-observer admin access (requires cluster-admin to apply)

### Namespace Status

- **Namespace:** `botburrow-agents` exists in apexalgo-iad cluster
- **Current State:** Empty (no deployed resources)
- **Blockers:** Missing secrets, RBAC constraints

### Deployment Requirements

| Component | Purpose | Secret Dependency |
|-----------|---------|-------------------|
| valkey | Redis/Valkey for coordination | None |
| coordinator | Leader election, work distribution | botburrow-agents-secrets |
| runner-hybrid | Hybrid runner (notifications + exploration) | botburrow-agents-secrets, mcp-credentials |
| runner-notification | Notification-only runner | botburrow-agents-secrets, mcp-credentials |
| runner-exploration | Exploration-only runner | botburrow-agents-secrets, mcp-credentials |

---

## Option 1: ArgoCD GitOps Deployment (RECOMMENDED)

**Description:** Create an ArgoCD Application manifest to manage deployment through GitOps. This bypasses devpod RBAC constraints since ArgoCD uses its own service account with cluster-wide permissions.

### Implementation

**Step 1: Create ArgoCD Application manifest**

Create `cluster-configuration/apexalgo-iad/argocd/botburrow-agents-application.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: botburrow-agents
  namespace: argocd
  labels:
    app.kubernetes.io/name: botburrow-agents
spec:
  project: default
  source:
    repoURL: https://github.com/jedarden/botburrow-agents.git
    targetRevision: main
    path: k8s/apexalgo-iad
    kustomize:
      # Use full kustomization for production
  destination:
    server: https://kubernetes.default.svc
    namespace: botburrow-agents
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
```

**Step 2: Create placeholder secrets**

From cluster-admin context:
```bash
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**Step 3: Apply ArgoCD Application**

From cluster-admin context:
```bash
kubectl apply -f cluster-configuration/apexalgo-iad/argocd/botburrow-agents-application.yaml
```

**Step 4: Update secrets with real values**

After deployment validates:
```bash
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
kubectl edit secret mcp-credentials -n botburrow-agents
kubectl rollout restart deployment/coordinator -n botburrow-agents
kubectl rollout restart deployment/runner-hybrid -n botburrow-agents
```

### Pros
- **GitOps Native:** Full deployment managed through git
- **No RBAC Issues:** Uses ArgoCD service account (has cluster-wide permissions)
- **Self-Healing:** ArgoCD automatically syncs and fixes drift
- **Audit Trail:** All deployment changes tracked in git
- **Rollback:** Easy rollback to previous git revisions
- **Multi-Environment:** Can easily create applications for dev/staging/prod
- **Secret Rotation:** Can integrate with SealedSecrets for automated secret management

### Cons
- **Cluster-Admin Required:** Initial application creation requires cluster-admin
- **ArgoCD Dependency:** Requires ArgoCD to be running and healthy
- **Complexity:** Additional layer of infrastructure to understand
- **Sync Latency:** Changes not applied immediately (depends on sync interval)
- **Debugging:** When things go wrong, need to check both k8s and ArgoCD

### Best For
- Production deployments
- Teams already using ArgoCD for other services
- Multi-environment setups
- Projects with frequent deployments

---

## Option 2: Grant devpod-observer Admin Access

**Description:** Apply the existing RBAC manifest to grant devpod-observer ServiceAccount admin permissions in botburrow-agents namespace, enabling direct kubectl deployment from devpods.

### Implementation

**Step 1: Grant admin permissions**

From cluster-admin context:
```bash
kubectl apply -f k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml
```

**Step 2: Verify permissions**

From devpod:
```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl auth can-i create deployments -n botburrow-agents
# Should output: yes
```

**Step 3: Create secrets**

From cluster-admin context (devpods can't create secrets):
```bash
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**Step 4: Deploy from devpod**

```bash
# Choose deployment variant
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml    # Minimal
# OR
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-full.yaml       # Full
```

### Pros
- **Direct Control:** Immediate deployment without waiting for ArgoCD sync
- **Developer-Friendly:** Workers/devpods can deploy directly
- **Simpler Debugging:** Direct kubectl access for troubleshooting
- **No New Infrastructure:** Uses existing kubectl workflow
- **Fast Iteration:** Quick deploy-test cycles during development

### Cons
- **Security Concern:** Grants elevated permissions to devpod-observer
- **Manual Deployment:** Not GitOps - deployments not tracked in git
- **No Self-Healing:** No automatic drift correction
- **Secret Management:** Secrets still require cluster-admin intervention
- **Multi-User Risk:** All devpods share the same elevated permissions
- **No Rollback Built-in:** Manual rollback required

### Best For
- Development environments
- Rapid prototyping
- Teams that prefer direct kubectl control
- Situations where ArgoCD is unavailable or problematic

---

## Option 3: Minimal Deployment with kubectl (One-Time)

**Description:** Use cluster-admin to perform a one-time deployment of the minimal stack, then manage ongoing operations through manual kubectl commands.

### Implementation

**Step 1: Cluster-admin deploys minimal stack**

```bash
# Apply secrets first
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Deploy minimal stack (valkey + hybrid runner)
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

**Step 2: Validate deployment**

```bash
kubectl get pods -n botburrow-agents
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid
```

**Step 3: Upgrade to full stack later**

```bash
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-full.yaml
```

### Pros
- **Fastest Initial Setup:** Single command deployment
- **Minimal Complexity:** No RBAC changes, no ArgoCD
- **Validates Core:** Tests core functionality first
- **Incremental:** Can add components incrementally
- **No Permission Changes:** Doesn't alter RBAC

### Cons
- **Cluster-Admin Required:** Every deployment needs cluster-admin
- **Not Sustainable:** Long-term operations require repeated admin access
- **No GitOps:** Manual process, not automated
- **Slow Iteration:** Each change requires admin intervention
- **Single Point of Failure:** Dependent on specific cluster-admin availability

### Best For
- Emergency/urgent deployments
- Proof of concept validation
- Temporary testing setups
- Initial deployment before transitioning to GitOps

---

## Option 4: SealedSecrets + ArgoCD (Production-Grade)

**Description:** Combine SealedSecrets for encrypted secrets in git with ArgoCD for true GitOps deployment. This is the most production-ready approach.

### Implementation

**Step 1: Create SealedSecret from template**

```bash
# Copy template
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml

# Edit with real values (cluster-admin or secret owner)
vim /tmp/botburrow-agents-secret.yml

# Seal the secret
kubeseal --format yaml < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# Clean up
rm /tmp/botburrow-agents-secret.yml
```

**Step 2: Update kustomization.yaml**

```yaml
resources:
  - namespace.yaml
  - rbac.yaml
  - configmap.yaml
  - botburrow-agents-sealedsecret.yml  # Add sealed secret
  - mcp-credentials-sealedsecret.yml   # Add MCP credentials sealed secret
  - valkey.yaml
  - coordinator.yaml
  - runner-hybrid.yaml
  # ... other resources
```

**Step 3: Create ArgoCD Application**

Same as Option 1.

**Step 4: Commit and push**

```bash
git add k8s/apexalgo-iad/*.yml k8s/apexalgo-iad/kustomization.yaml
git commit -m "feat: add SealedSecrets for production deployment"
git push origin main
```

### Pros
- **True GitOps:** Everything including secrets in git
- **Encrypted at Rest:** Secrets encrypted in repository
- **Automatic Deployment:** ArgoCD handles everything
- **Audit Trail:** All changes including secret updates tracked
- **Cluster-Specific:** SealedSecrets only decrypt in target cluster
- **Zero Manual Steps:** After initial setup, fully automated

### Cons
- **Requires SealedSecret Controller:** Must be installed in cluster
- **Complex Setup:** Initial kubeseal setup has learning curve
- **Cluster-Specific Secrets:** Can't share sealed secrets between clusters
- **Secret Rotation:** Still requires resealing for secret updates
- **Infrastructure Dependency:** Additional controller to maintain

### Best For
- Production environments
- Compliance-required deployments
- Multi-region/multi-cluster setups
- Teams with mature GitOps practices

---

## Option 5: Hybrid Approach (Phased Deployment)

**Description:** Start with minimal deployment via cluster-admin, then transition to GitOps once ArgoCD Application is created.

### Implementation

**Phase 1: Emergency Minimal Deployment (Cluster-Admin)**

```bash
# Immediate deployment for validation
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

**Phase 2: Create ArgoCD Application (Cluster-Admin)**

```bash
# Create ArgoCD Application for ongoing management
kubectl apply -f cluster-configuration/apexalgo-iad/argocd/botburrow-agents-application.yaml
```

**Phase 3: Transition to GitOps**

Once ArgoCD syncs, all further changes are managed through git commits. The minimal deployment can be upgraded to full by updating the kustomization reference in the ArgoCD Application.

### Pros
- **Immediate Results:** Fast initial deployment
- **Smooth Transition:** Gradual move to GitOps
- **Risk Mitigation:** Validates core before committing to approach
- **Flexible:** Can stop at any phase based on results
- **Best of Both Worlds:** Quick start + long-term automation

### Cons
- **Two-Step Process:** Requires coordination between phases
- **Potential Duplication:** Risk of managing both kubectl and ArgoCD
- **Configuration Drift:** Need to ensure ArgoCD picks up existing resources
- **Complex Planning:** Requires planning the transition

### Best For
- Organizations new to GitOps
- Critical services needing immediate deployment
- Migration scenarios from manual to automated
- Teams wanting to validate GitOps before full commitment

---

## Comparison Matrix

| Approach | GitOps | Setup Speed | Admin Access Needed | Secret Management | Long-Term Sustainability |
|----------|--------|-------------|---------------------|-------------------|--------------------------|
| **ArgoCD GitOps** | Yes | Medium | One-time | Manual/SealedSecret | High |
| **Grant devpod Admin** | No | Fast | One-time (RBAC) | Manual | Medium |
| **Minimal kubectl** | No | Fastest | Every deployment | Manual | Low |
| **SealedSecrets + ArgoCD** | Yes | Slow | One-time | Automated | Very High |
| **Hybrid Phased** | Yes (eventually) | Fast | One-time | Manual → Auto | High |

---

## Decision Framework

### Choose ArgoCD GitOps (Option 1) if:
- ArgoCD is already available and healthy
- You want true GitOps with minimal RBAC changes
- Long-term sustainability is important
- You have cluster-admin access for initial setup

### Choose Grant devpod Admin (Option 2) if:
- Rapid development iteration is priority
- You prefer direct kubectl control
- ArgoCD is problematic or unavailable
- Security model allows devpod elevated access

### Choose Minimal kubectl (Option 3) if:
- This is a proof of concept or temporary deployment
- You need to validate core functionality quickly
- Cluster-admin access is readily available
- You plan to redeploy properly later

### Choose SealedSecrets + ArgoCD (Option 4) if:
- Production deployment with compliance requirements
- You want everything in git including secrets
- SealedSecret controller is available
- Long-term automation is critical

### Choose Hybrid Phased (Option 5) if:
- You need immediate deployment but want GitOps eventually
- You're new to GitOps and want to validate the approach
- You want to mitigate risk by phasing in automation
- Critical service with time pressure

---

## Recommended Approach: Option 1 (ArgoCD GitOps)

### Rationale

1. **Aligns with Existing Infrastructure:** The apexalgo-iad cluster already uses ArgoCD for other services (evidenced by the argocd namespace and existing patterns)

2. **Solves RBAC Constraint:** ArgoCD uses its own service account with cluster-wide permissions, bypassing the devpod-observer RBAC limitation

3. **GitOps Best Practice:** Matches the intended deployment model for the cluster

4. **Minimal RBAC Changes:** Doesn't require granting elevated permissions to devpod-observer

5. **Sustainable:** Long-term automation with self-healing

### Implementation Steps

**For Cluster-Admin:**

1. Create placeholder secrets:
   ```bash
   kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
   ```

2. Create ArgoCD Application:
   ```bash
   kubectl apply -f cluster-configuration/apexalgo-iad/argocd/botburrow-agents-application.yaml
   ```

3. Monitor ArgoCD sync:
   ```bash
   kubectl get application botburrow-agents -n argocd -w
   ```

**For Ongoing Operations:**

4. Update secrets with real values (after sync):
   ```bash
   kubectl edit secret botburrow-agents-secrets -n botburrow-agents
   kubectl edit secret mcp-credentials -n botburrow-agents
   ```

5. Restart deployments to pick up new secrets:
   ```bash
   kubectl rollout restart deployment/coordinator -n botburrow-agents
   kubectl rollout restart deployment/runner-hybrid -n botburrow-agents
   ```

---

## Alternative: If SealedSecret Controller is Available

If the apexalgo-iad cluster has the SealedSecret controller installed (check with `kubectl get crd sealedsecrets.bitnami.com`), then **Option 4 (SealedSecrets + ArgoCD)** becomes the superior choice:

1. Creates fully automated GitOps deployment
2. Secrets are encrypted in git
3. Zero manual secret management after initial setup
4. Best security and compliance posture

---

## Next Steps (Human Decision Required)

1. **Verify ArgoCD availability** in apexalgo-iad cluster:
   ```bash
   kubectl get pods -n argocd
   ```

2. **Check for SealedSecret controller**:
   ```bash
   kubectl get crd sealedsecrets.bitnami.com
   ```

3. **Choose deployment approach** based on:
   - ArgoCD availability
   - SealedSecret availability
   - Security requirements
   - Time pressure
   - Team preference

4. **Execute chosen approach** following the implementation steps

5. **Close bd-32a** after human decision is made, or **proceed with bd-33k** to implement the chosen approach

---

## Related Beads

- **bd-33k** - Original bead: Deploy botburrow-agents coordinator stack
- **bd-3l1** - Create ArgoCD Application (CLOSED - needs implementation)
- **bd-3qi9** - Cross-workspace human bead for secret values
- **bd-31k** - Coordinator leader election verification (depends on bd-33k)

---

## Appendix: Quick Reference Commands

### Check ArgoCD Status
```bash
# List all applications
kubectl get applications -n argocd

# Get botburrow-agents application details
kubectl get application botburrow-agents -n argocd -o yaml

# Watch sync status
kubectl get application botburrow-agents -n argocd -w
```

### Check Deployment Status
```bash
# All resources in namespace
kubectl get all -n botburrow-agents

# Pod logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator

# Describe failing pod
kubectl describe pod -n botburrow-agents <pod-name>
```

### Manual Rollback (kubectl)
```bash
# Rollback deployment
kubectl rollout undo deployment/coordinator -n botburrow-agents

# Check rollout status
kubectl rollout status deployment/coordinator -n botburrow-agents
```

### ArgoCD Rollback
```bash
# In ArgoCD UI or CLI, rollback to previous git commit
# Or using kubectl:
kubectl patch application botburrow-agents -n argocd \
  --type='json' -p='[{"op": "replace", "path": "/spec/source/targetRevision", "value": "<previous-commit>"}]'
```
