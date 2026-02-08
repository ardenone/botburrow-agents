# Deployment Options Research for botburrow-agents
**Research Bead:** bd-32a (Alternative: Research and document options)
**Original Bead:** bd-33k (Deploy botburrow-agents coordinator stack in apexalgo-iad)
**Date:** 2026-02-08

## Executive Summary

The botburrow-agents coordinator stack deployment to apexalgo-iad cluster has **two blockers**:

1. **Secret values needed** - Requires human input for API keys and credentials
2. **ArgoCD Application manifest needed** - Required for GitOps deployment due to RBAC constraints

This document compares the available deployment approaches with their trade-offs.

---

## Current Situation Analysis

### Cluster Configuration
- **Target Cluster:** apexalgo-iad
- **Deployment Namespace:** botburrow-agents (already exists)
- **RBAC Status:** devpod-observer ServiceAccount has **read-only** access
- **Deployment Method:** ArgoCD GitOps (kubectl apply is blocked by RBAC)

### What Needs to Be Deployed

| Component | Purpose | Required? |
|-----------|---------|-----------|
| namespace.yaml | Namespace isolation | Already exists |
| rbac.yaml | ServiceAccount, Role, RoleBinding | Required |
| configmap.yaml | Application configuration | Required |
| valkey.yaml | Redis/Valkey for coordination | Required |
| coordinator.yaml | Coordination service with leader election | **Required (original goal)** |
| runner-hybrid.yaml | Hybrid runner for all work types | Required |
| botburrow-agents-secrets | API keys and credentials | **Critical blocker** |

### Existing Deployment Options in Repo

The repo already has three deployment configurations:

| File | Description | Includes Coordinator? |
|------|-------------|----------------------|
| `kustomization.yaml` | Full ArgoCD deployment | Yes |
| `kustomization-minimal.yaml` | Minimal viable deployment (no coordinator) | No |
| `kustomization-simplified.yaml` | Simplified ArgoCD deployment (no coordinator) | No |

---

## Deployment Options Comparison

### Option 1: Full Coordinator Stack via ArgoCD (Original Goal)

**Description:** Deploy complete stack with coordinator using ArgoCD GitOps.

**Pros:**
- Leader election for high availability
- Dedicated coordination service
- Proper GitOps workflow
- Production-ready architecture
- Scalable to multiple runner types

**Cons:**
- **BLOCKED** on secret values (human input required)
- **BLOCKED** on ArgoCD Application manifest creation
- More complex to debug initially
- Requires all components working together

**Implementation Steps:**
1. Human provides secret values (bd-3qi9)
2. Create SealedSecret from template
3. Create ArgoCD Application manifest
4. Apply via ArgoCD
5. Verify deployment health

**Estimated Time:** 2-4 hours (depending on human input availability)

**Risk Level:** Medium (more components to configure)

---

### Option 2: Minimal Deployment via ArgoCD (Simplified)

**Description:** Deploy simplified stack without coordinator, use single hybrid runner.

**Pros:**
- Simpler initial deployment
- Faster to validate core functionality
- Easier to debug
- Can add coordinator later via upgrade

**Cons:**
- No leader election (single point of failure)
- **BLOCKED** on secret values (human input required)
- **BLOCKED** on ArgoCD Application manifest creation
- Not production-ready architecture
- Limited scalability

**Implementation Steps:**
1. Human provides secret values (bd-3qi9)
2. Create SealedSecret from template
3. Create ArgoCD Application manifest (use minimal kustomization)
4. Apply via ArgoCD
5. Verify deployment health

**Estimated Time:** 1-2 hours (depending on human input availability)

**Risk Level:** Low (simpler architecture)

---

### Option 3: Direct kubectl Deployment with Placeholder Secrets

**Description:** Request cluster-admin to grant devpod-observer admin permissions, deploy via kubectl with placeholder secrets.

**Pros:**
- **Bypasses** the secret values blocker (use placeholders)
- **Bypasses** the ArgoCD manifest blocker
- Immediate deployment possible
- Can update real secrets later via cluster-admin

**Cons:**
- **Requires RBAC change** (devpod-observer admin access in botburrow-agents namespace)
- Breaks GitOps model (manual deployment)
- Security concern (broader permissions for devpod-observer)
- Requires cluster-admin intervention anyway

**Implementation Steps:**
1. Cluster-admin applies RBAC grant: `devpod-observer-botburrow-agents-admin-rbac.yml`
2. Apply placeholder secrets: `botburrow-agents-secrets-PLACEHOLDER.yml`
3. Deploy via kubectl: `kubectl apply -k k8s/apexalgo-iad/`
4. Verify deployment
5. Cluster-admin updates real secret values later

**Estimated Time:** 30 minutes (if cluster-admin available)

**Risk Level:** Low (existing documented approach)

**Note:** RBAC manifest already exists at `k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml`

---

### Option 4: Hybrid - ArgoCD with Placeholder Secrets

**Description:** Create ArgoCD Application with placeholder secrets, update via SealedSecret later.

**Pros:**
- Maintains GitOps workflow
- Can start deployment immediately
- Upgrade path to production-ready
- No RBAC changes required

**Cons:**
- **BLOCKED** on ArgoCD Application manifest creation
- Requires two-phase secret update
- Coordinator won't function properly with placeholder secrets

**Implementation Steps:**
1. Create ArgoCD Application manifest
2. Include placeholder secrets in initial deployment
3. Apply via ArgoCD
4. Create SealedSecret with real values
5. Update deployment

**Estimated Time:** 1-2 hours

**Risk Level:** Medium (two-phase process)

---

### Option 5: Staged Deployment - Start Minimal, Upgrade Later

**Description:** Deploy minimal stack first (valkey + runner-hybrid), verify, then add coordinator.

**Pros:**
- Validates core functionality first
- Easier troubleshooting
- Can test Hub connectivity before adding complexity
- Lower initial risk

**Cons:**
- **BLOCKED** on secret values (human input required)
- **BLOCKED** on ArgoCD Application manifest creation
- Requires two deployment cycles
- No coordinator for initial testing

**Implementation Steps:**
1. Deploy minimal stack (kustomization-minimal.yaml)
2. Verify runner connects to Hub and processes work
3. Create ArgoCD Application for full stack
4. Upgrade to coordinator-inclusive deployment
5. Verify leader election

**Estimated Time:** 2-3 hours

**Risk Level:** Low (iterative approach)

---

## Blocker Analysis

### Blocker 1: Secret Values (bd-3qi9)

**Status:** Human bead exists in /home/coder workspace

**Required Values:**
```
HUB_API_KEY          - Botburrow Hub API key
R2_ENDPOINT          - Cloudflare R2 endpoint URL
R2_ACCESS_KEY        - R2 access key ID
R2_SECRET_KEY        - R2 secret access key
FORGEJO_USER         - Forgejo service account username
FORGEJO_TOKEN        - Forgejo access token
GITHUB_USER          - GitHub username
GITHUB_TOKEN         - GitHub PAT with repo scope
GITHUB_PAT           - GitHub PAT for MCP github server
BRAVE_API_KEY        - Brave Search API key
```

**Workaround:** Use placeholder secrets (Option 3) - pods will start but not function

### Blocker 2: ArgoCD Application Manifest (bd-3l1)

**Status:** CLOSED (manifest needs to be created)

**Location:** `cluster-configuration/apexalgo-iad/argocd/botburrow-agents-application.yaml`

**Required Content:**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: botburrow-agents
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/jedarden/botburrow-agents.git
    targetRevision: main
    path: k8s/apexalgo-iad
  destination:
    server: https://kubernetes.default.svc
    namespace: botburrow-agents
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**Workaround:** None for ArgoCD deployment, but Option 3 bypasses via kubectl

---

## Recommendation Matrix

| Option | Best For | Time Required | Risk | Notes |
|--------|----------|---------------|------|-------|
| **Option 3** | Immediate unblocking | 30 min | Low | Requires cluster-admin RBAC grant |
| **Option 2** | Fast validation | 1-2 hours | Low | Waiting on human input |
| **Option 5** | Cautious rollout | 2-3 hours | Low | Iterative approach |
| **Option 4** | GitOps + speed | 1-2 hours | Medium | Two-phase secret update |
| **Option 1** | Production-ready | 2-4 hours | Medium | Original goal, most complete |

---

## Recommended Approach

### Short Term (Immediate)

**Use Option 3: Direct kubectl with Placeholder Secrets**

Rationale:
- Already has documented workflow (`DEPLOYMENT-SIMPLIFIED.md`)
- RBAC manifest exists (`devpod-observer-botburrow-agents-admin-rbac.yml`)
- Placeholder secrets manifest exists (`botburrow-agents-secrets-PLACEHOLDER.yml`)
- Fastest path to unblock development
- Can upgrade to ArgoCD GitOps later

### Long Term (Production)

**Migrate to Option 1: Full Coordinator Stack via ArgoCD**

Rationale:
- Production-ready architecture with leader election
- Proper GitOps workflow
- Easier long-term maintenance
- Scalable to production loads

---

## Next Steps by Option

### For Option 3 (Recommended - Short Term)

1. Request cluster-admin to apply: `k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml`
2. Apply placeholder secrets: `kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
3. Deploy minimal stack: `kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml`
4. Verify pods are running
5. Update with real secret values via cluster-admin

### For Option 1 (Long Term)

1. **Blocker:** Human provides secret values (bd-3qi9)
2. Create SealedSecret from template
3. Create ArgoCD Application manifest in cluster-configuration repo
4. Apply via ArgoCD
5. Verify deployment health

---

## Appendix: Existing Documentation References

- `k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md` - Minimal deployment guide
- `k8s/apexalgo-iad/DEPLOYMENT-SIMPLIFIED.md` - Simplified deployment guide
- `k8s/apexalgo-iad/kustomization.yaml` - Full ArgoCD deployment
- `k8s/apexalgo-iad/kustomization-minimal.yaml` - Minimal deployment
- `k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml` - RBAC grant for Option 3

---

**Research Completed:** 2026-02-08
**Research Bead:** bd-32a
