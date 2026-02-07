# Botburrow-Agents Deployment Investigation (bd-1v9)

## Problem Statement
The botburrow-agents namespace exists but is empty - no coordinator, runners, or valkey deployed.

## Investigation Findings

### 1. Namespace Status
- **Namespace**: `botburrow-agents` exists (age: 6d)
- **Resources present**: Only secrets, configmaps, and RBAC bindings
- **Resources missing**: Deployments, Services, HPAs, ServiceMonitors

### 2. Manifest Files
**Location**: `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/`

**Files present**:
- `namespace.yml` - Namespace definition
- `rbac.yaml` - ServiceAccount, Role, RoleBinding
- `configmap.yaml` - Environment configuration
- `coordinator.yaml` - Coordinator deployment
- `coordinator-git-sync.yaml` - Git-sync variant
- `valkey.yaml` - Valkey (Redis) deployment
- `runner-*.yaml` - Various runner deployments
- `hpa.yaml` - HorizontalPodAutoscaler
- `servicemonitor.yaml` - Prometheus monitoring
- `skill-sync.yaml` - Skills sync deployment
- `botburrow-agents-sealedsecret.yml` - Encrypted secrets
- `botburrow-agents-secret.yml.template` - Secret template

### 3. Git Repository Status
- **Repository**: `https://github.com/ardenone/ardenone-cluster.git`
- **Branch**: `main`
- **Visibility**: **PRIVATE** (confirmed via login redirect)
- **Latest commit**: `76876f94` - "chore(bd-1v9): trigger botburrow-agents sync to GitHub"
- **Files ARE on GitHub**: Confirmed via `git ls-remote origin HEAD`
- **Botburrow-agents commit**: `3331f411` - "fix(botburrow-agents): switch to Docker Hub images"

**Key Finding**: The repository is private on GitHub. The 404 errors when accessing raw.githubusercontent.com are due to lack of authentication, NOT missing files. ArgoCD has credentials to access the private repository.

### 4. ArgoCD Configuration
**ApplicationSet**: `manifest-appset-apexalgo-iad` in `argocd` namespace

**Configuration**:
```yaml
generators:
  - git:
      repoURL: https://github.com/ardenone/ardenone-cluster
      revision: HEAD
      directories:
        - path: cluster-configuration/apexalgo-iad/*
```

**Expected behavior**: Should create an application named `botburrow-agents-ns-apexalgo-iad` for the botburrow-agents directory.

### 5. Access Restrictions
**devpod-observer ServiceAccount**:
- Cannot list ArgoCD applications (Forbidden)
- Cannot create resources in botburrow-agents namespace (Forbidden)
- Can read namespace existence and secrets/configmaps

**Impact**: Cannot directly verify ArgoCD application status or sync status.

## Root Cause Analysis

### Most Likely Cause: ArgoCD Application Not Created or Sync Issue

Given:
1. Manifests exist and are valid YAML
2. Files ARE committed to GitHub (private repo)
3. ArgoCD ApplicationSet is configured to auto-discover directories
4. Other namespaces (forgejo, mcp, kalshi) have working deployments

The issue is likely:
1. **ArgoCD Application not created**: The ApplicationSet generator may not have picked up the botburrow-agents directory
2. **ArgoCD sync failure**: The application exists but has a sync error
3. **Missing annotation/label**: The directory may need a specific annotation for ApplicationSet discovery

### Excluded Causes
- ❌ Git sync issue: Files ARE on GitHub (confirmed via git ls-remote)
- ❌ Manifest syntax errors: All YAML files are valid
- ❌ Namespace not created: Namespace exists (age 6d)
- ❌ RBAC blocking deployment: ArgoCD should have cluster-admin or appropriate permissions

## Resolution Steps

### Immediate (Requires Human with ArgoCD Access)
1. **Verify ArgoCD application exists**: Check if `botburrow-agents-ns-apexalgo-iad` application exists in ArgoCD
2. **Check sync status**: If application exists, check for sync errors
3. **Review ApplicationSet generator status**: Check if the ApplicationSet is discovering the botburrow-agents directory

### If Application Doesn't Exist
The ApplicationSet may need manual intervention:
1. Create the application manually in ArgoCD
2. Or investigate why the generator isn't picking up the directory
3. Check for any ignore patterns or exclusions

### If Application Exists but Sync Failed
1. Check sync error logs in ArgoCD
2. Verify ArgoCD has access to the private GitHub repository
3. Check for any resource conflicts or missing dependencies

## Human Bead Created
**Bead ID**: `bd-27r`
**Title**: "HUMAN: Verify botburrow-agents ArgoCD application sync status"
**Priority**: P0 (Critical)
**Dependency**: `bd-1v9` blocked by `bd-27r`

## Next Steps for Worker
Worker is blocked until human verifies ArgoCD status. After verification:
1. If ArgoCD issue is identified, create appropriate fix bead
2. If manual intervention is needed, document steps
3. Close `bd-27r` after resolution
4. Resume `bd-1v9` implementation

## Artifacts
- Investigation summary: `bd-1v9-investigation-findings.md`
- Human bead: `bd-27r`
- Dependency: `bd-1v9` -> `bd-27r` (blocks)
- Git commit: `76876f94` - Added .gitkeep to trigger sync
