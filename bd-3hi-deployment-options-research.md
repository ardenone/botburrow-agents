# botburrow-agents Deployment Options Research (bd-3hi)

**Date:** 2026-02-08
**Alternative for:** bd-13j - Build and deploy botburrow-agents updates
**Approach:** research-only

## Executive Summary

This document provides a detailed comparison of deployment approaches for botburrow-agents. The research is based on analysis of:
- Current deployment configuration (GitHub Actions, Kubernetes manifests)
- Existing deployment issues (bd-2f8 findings)
- Cluster constraints (ArgoCD not installed in apexalgo-iad)
- Project documentation and best practices

---

## Background: Why This Research Exists

The original bead bd-13j describes a 12-step deployment process:
1. Update code in botburrow-agents repo
2. Update VERSION file
3. Run tests: pytest tests/
4. Commit and push to GitHub
5. GitHub Actions builds Docker images (coordinator, runner, skill-sync)
6. Wait for build completion (~5 min)
7. Verify images pushed to Docker Hub
8. Update manifests in ardenone-cluster repo
9. Commit and push manifests
10. ArgoCD syncs to apexalgo-iad cluster
11. Monitor rolling update of pods
12. Verify no activation processing interruption

**Critical Issue:** Step 10 assumes ArgoCD manages the deployment, but **ArgoCD is NOT installed** in apexalgo-iad cluster (per bd-2f8 investigation).

---

## Deployment Options

### Option 1: Direct kubectl Apply (Manual/Scripted)

**Description:** Deploy Kubernetes manifests directly using kubectl, bypassing GitOps.

**Implementation:**
```bash
# From botburrow-agents repo
kubectl apply -f k8s/apexalgo-iad/namespace.yaml
kubectl apply -f k8s/apexalgo-iad/rbac.yaml
kubectl apply -f k8s/apexalgo-iad/configmap.yaml
kubectl apply -f k8s/apexalgo-iad/valkey.yaml
kubectl apply -f k8s/apexalgo-iad/coordinator.yaml
kubectl apply -f k8s/apexalgo-iad/runner-hybrid.yaml
# ... etc
```

Or using Kustomize:
```bash
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

**Pros:**
- Works immediately without additional infrastructure
- Simple and predictable
- Direct control over deployment timing
- No dependency on ArgoCD installation
- Faster iteration for development

**Cons:**
- Manual process (error-prone without automation)
- No automated sync from Git
- Drift detection requires manual effort
- No built-in rollback automation
- Requires cluster-admin access

**Best For:**
- Initial deployment and testing
- Development/staging environments
- Quick iterations during development

**Requirements:**
- cluster-admin permissions
- kubectl access to apexalgo-iad
- Secrets pre-created (SealedSecrets or manual)

---

### Option 2: GitHub Actions + kubectl (GitOps-Lite)

**Description:** Continue using GitHub Actions CI/CD but replace ArgoCD with direct kubectl deployment.

**Implementation:**
The existing `.github/workflows/deploy-kubernetes.yml` already supports this:
```yaml
# Current workflow already does:
# 1. Build Docker images
# 2. Configure kubectl from KUBE_CONFIG_DATA_APEXALGO_IAD secret
# 3. Apply manifests with kubectl
# 4. Run health checks
# 5. Rollback on failure
```

**Pros:**
- Already implemented and configured
- Automated deployment on push to main
- Includes health checks and rollback
- Uses existing GitHub Actions infrastructure
- No additional software required

**Cons:**
- Requires KUBE_CONFIG_DATA_APEXALGO_IAD secret in GitHub
- No continuous reconciliation (one-time apply only)
- Manual intervention needed for drift correction
- GitHub Actions runner executes kubectl (not in-cluster)

**Best For:**
- Production deployment without ArgoCD
- Teams already using GitHub Actions
- Environments needing automated but not continuous sync

**Requirements:**
- GitHub Actions configured with kubeconfig secret
- cluster-admin permissions for the service account
- DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD secrets

---

### Option 3: Install ArgoCD in apexalgo-iad

**Description:** Install ArgoCD to enable true GitOps with continuous reconciliation.

**Implementation:**
```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Apply botburrow-agents Application manifest
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml
```

**Pros:**
- True GitOps with continuous reconciliation
- Automated drift detection and correction
- Declarative deployment model
- Rich UI for visualization
- Supports multi-cluster deployments
- Application-level health checks

**Cons:**
- Additional infrastructure to maintain
- Additional resource consumption
- Initial setup complexity
- Overkill for single-cluster simple deployments
- Learning curve for team

**Best For:**
- Production environments
- Multi-cluster deployments
- Teams wanting full GitOps experience
- Environments with frequent changes

**Requirements:**
- cluster-admin to install ArgoCD
- Ongoing maintenance of ArgoCD control plane
- Network access to ArgoCD API/UI

---

### Option 4: Minimal Deployment (Fastest Validation)

**Description:** Use the minimal kustomization to deploy only essential components.

**Implementation:**
```bash
# From botburrow-agents repo
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

**Components:**
- valkey (Redis/Valkey)
- runner-hybrid (single runner type for all work)
- Basic RBAC
- ConfigMaps

**Pros:**
- Fastest path to validation
- Minimal resource footprint
- Reduced complexity
- Easier troubleshooting

**Cons:**
- No dedicated coordinator
- No HPA (manual scaling)
- No ServiceMonitor (limited observability)
- Single point of failure (single runner type)

**Best For:**
- Initial deployment validation
- Development environments
- Proof-of-concept deployments

**Deferred Components:**
- coordinator.yaml (optional for simple deployments)
- Additional runners (notification, exploration)
- hpa.yaml (autoscaling)
- servicemonitor.yaml (Prometheus metrics)
- skill-sync.yaml (background skill sync)

---

### Option 5: Alternative GitOps (Flux, etc.)

**Description:** Use alternative Git operators instead of ArgoCD.

**Options:**
- **Flux CD** - Lightweight GitOps with Kubernetes native CRDs
- **Carvel kapp-controller** - Lightweight GitOps
- **Keptn** - Cloud-native delivery automation

**Pros:**
- Potentially lighter weight than ArgoCD
- Different feature sets may better match requirements
- Flux has strong Helm/Kustomize support

**Cons:**
- Additional infrastructure to install
- Less mature than ArgoCD (depending on choice)
- Additional learning curve
- No existing manifests/config for these tools

**Best For:**
- Teams with specific requirements not met by ArgoCD
- Environments already using alternative GitOps tools

---

## Comparison Matrix

| Aspect | kubectl Manual | GitHub Actions + kubectl | ArgoCD GitOps | Minimal Deployment |
|--------|---------------|-------------------------|---------------|-------------------|
| **Setup Complexity** | Low | Medium (requires secrets) | High | Low |
| **Automation** | Manual | Automated | Automated | Manual |
| **Git Sync** | None | One-time | Continuous | None |
| **Drift Detection** | Manual | Manual | Automatic | Manual |
| **Rollback** | Manual | Automated | Automated | Manual |
| **Resource Overhead** | None | CI/CD runner only | ArgoCD control plane | None |
| **Best For** | Dev/Testing | Production | Production/Multi-cluster | Quick validation |
| **Learning Curve** | Low | Low | Medium | Low |
| **Maintenance** | Manual process | CI/CD pipeline | ArgoCD upgrades | Manual process |

---

## Cluster State Analysis (from bd-2f8)

### Current Issues
1. **botburrow-agents namespace does not exist** - Not deployed yet
2. **ArgoCD not installed** - `kubectl get applications.argoproj.io -A` returns error
3. **mcp-implementation-worker ImagePullBackOff** - Wrong image reference

### Existing Infrastructure
- botburrow namespace exists
- botburrow-hub pods running (2/2 replicas)
- Multiple Valkey instances in other namespaces (kalsha, polymarket, stock-research, valkey)
- Docker Hub registry secret exists in botburrow namespace

---

## Recommended Approach (Tiered)

### Phase 1: Immediate Validation (Option 4 - Minimal)

```bash
# 1. Apply placeholder secrets
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# 2. Deploy minimal stack
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml

# 3. Verify
kubectl get pods -n botburrow-agents
```

**Goal:** Validate core functionality with minimal complexity and risk.

### Phase 2: Production Automation (Option 2 - GitHub Actions)

Once minimal deployment is validated:
1. Configure `KUBE_CONFIG_DATA_APEXALGO_IAD` secret in GitHub
2. Ensure `DOCKERHUB_USERNAME` and `DOCKERHUB_PASSWORD` are set
3. Enable the existing `deploy-kubernetes.yml` workflow
4. Deploy on push to main branch

**Goal:** Automated deployment without ArgoCD dependency.

### Phase 3: Future Enhancement (Option 3 - ArgoCD)

If/when continuous reconciliation becomes important:
1. Install ArgoCD in apexalgo-iad
2. Apply `argocd-application.yaml` manifest
3. Enable automated sync policy

**Goal:** Full GitOps with drift detection and auto-correction.

---

## Security Considerations

### Secrets Management
All options require secrets to be created:
- `botburrow-agents-secrets` - Hub API key, R2 credentials, API keys
- `mcp-credentials` - GitHub PAT, Brave API key, etc.

**Options for secrets:**
1. **SealedSecrets** - Encrypt secrets, commit to Git (recommended for production)
2. **Manual secret creation** - `kubectl create secret literal` (for initial setup)
3. **External Secret Operator** - Sync from external secret managers (AWS Secrets Manager, etc.)

### RBAC Requirements
All deployment options require:
- cluster-admin for initial setup (namespace, secrets)
- ServiceAccount with appropriate permissions for ongoing operations

---

## Cost Analysis

| Option | Infrastructure Cost | Maintenance Effort |
|--------|-------------------|-------------------|
| kubectl Manual | None | Manual per deployment |
| GitHub Actions | CI/CD minutes (free tier usually sufficient) | Maintain workflow files |
| ArgoCD | ~1-2 CPU, 2-4 GB RAM for control plane | ArgoCD upgrades, configuration |
| Minimal | None | Manual per deployment |

---

## Decision Framework

Use this flowchart to decide:

```
Need continuous reconciliation?
├─ Yes → Install ArgoCD (Option 3)
└─ No
    ├─ Need automation on push?
    │   ├─ Yes → GitHub Actions + kubectl (Option 2)
    │   └─ No → kubectl Manual (Option 1)
    └─ Just need to validate quickly?
        └─ Yes → Minimal Deployment (Option 4)
```

**Questions to ask:**
1. How frequently will deployments happen?
   - Daily/Weekly → Consider ArgoCD
   - Monthly/Quarterly → GitHub Actions or manual
2. How important is drift detection?
   - Critical → ArgoCD
   - Nice to have → GitHub Actions with periodic checks
   - Not important → Manual
3. What's the team's familiarity with these tools?
   - Kubernetes experts → Any option
   - Learning phase → Start with minimal/manual
4. Are there multi-cluster requirements?
   - Yes → ArgoCD or Flux
   - No → Simpler options suffice

---

## Implementation Checklist

Regardless of option chosen, complete these steps first:

### Pre-deployment
- [ ] Verify kubectl access to apexalgo-iad cluster
- [ ] Verify cluster-admin permissions (or coordinate with cluster admin)
- [ ] Create botburrow-agents namespace (or verify it exists)
- [ ] Create placeholder secrets (SealedSecrets or manual)
- [ ] Update VERSION file in botburrow-agents repo
- [ ] Run tests: `pytest tests/`

### During deployment
- [ ] Build Docker images (manually or via GitHub Actions)
- [ ] Verify images pushed to Docker Hub
- [ ] Apply manifests in correct order (namespace, rbac, configmap, valkey, deployments)
- [ ] Wait for pod readiness
- [ ] Verify pod health

### Post-deployment
- [ ] Update secrets with real values (if using placeholders)
- [ ] Verify connectivity to Hub API
- [ ] Verify R2/S3 connectivity
- [ ] Test agent activation flow
- [ ] Configure monitoring/alerting

---

## Conclusion

The deployment approach depends on your priorities:

1. **For fastest validation:** Use Option 4 (Minimal Deployment) with manual kubectl
2. **For production automation:** Use Option 2 (GitHub Actions + kubectl) - already configured
3. **For full GitOps:** Install ArgoCD (Option 3) - but requires additional setup

**Recommendation:** Start with Option 4 for validation, then move to Option 2 for production automation. Consider Option 3 only if continuous reconciliation becomes a requirement.

---

## Next Steps (Human Decision Required)

Please choose one of the following:

1. **Proceed with Minimal Deployment (Option 4)** - Fastest path to validate core functionality
2. **Enable GitHub Actions Deployment (Option 2)** - Requires `KUBE_CONFIG_DATA_APEXALGO_IAD` secret configuration
3. **Install ArgoCD (Option 3)** - Requires cluster-admin and additional infrastructure setup
4. **Manual kubectl Deployment (Option 1)** - Direct control without automation
5. **Alternative approach** - Specify your requirements

Once a decision is made, the worker can proceed with implementation or create appropriate follow-up beads for the chosen approach.

---

**Document Status:** Research complete, awaiting human decision
**Bead ID:** bd-3hi
**Generated:** 2026-02-08T09:00:00Z
