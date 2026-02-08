# ArgoCD Deployment Workaround (bd-cni)

**Date:** 2026-02-08
**Bead:** bd-cni (Alternative: Use workaround approach)
**Related:** bd-1v9 (Fix botburrow-agents deployment via ArgoCD)
**Status:** Implemented

## Problem Statement

The ArgoCD ApplicationSet `manifest-appset-apexalgo-iad` is not deploying resources for the `botburrow-agents` namespace. The namespace exists (created by ArgoCD) but contains zero resources - no deployments, services, or other components.

### Root Cause (from bd-1v9 investigation)

1. **Namespace exists** with ArgoCD tracking-id annotation
2. **No resources deployed** - `kubectl get all -n botburrow-agents` returns empty
3. **Manifests valid** - All YAML files pass `kubectl apply --dry-run=client`
4. **Git repo synced** - Files are committed to GitHub
5. **ArgoCD access blocked** - Cannot verify application status due to RBAC

### Hypothesis

The ArgoCD Application `botburrow-agents-ns-apexalgo-iad` either:
- Was never created by the ApplicationSet generator
- Exists but has a sync error preventing resource deployment
- Has a health check failure preventing sync completion

## Workaround Approach

**Bypass ArgoCD entirely and deploy via kubectl directly.**

This workaround:
- Uses the existing `kustomization-minimal.yaml` for minimal viable deployment
- Deploys via `kubectl apply -k` instead of ArgoCD GitOps
- Can be migrated to ArgoCD later once the sync issue is resolved

### Why This Works

1. **No ArgoCD dependency** - Direct kubectl deployment is reliable
2. **Manifests already valid** - All YAML files tested and working
3. **Minimal components** - Only deploys what's needed for MVP
4. **Reversible** - Can clean up and migrate to ArgoCD later

## Implementation

### New Script: `scripts/deploy-workaround.sh`

The deployment script handles:
1. Pre-flight checks (kubeconfig, cluster connectivity, manifest files)
2. Applying placeholder secrets
3. Deploying minimal components via kustomize
4. Verification and health checks

### Usage

```bash
# Deploy with default kubeconfig
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh

# Deploy with custom kubeconfig
./scripts/deploy-workaround.sh --kubeconfig /path/to/kubeconfig

# Dry run to see what would be deployed
./scripts/deploy-workaround.sh --dry-run

# Show help
./scripts/deploy-workaround.sh --help
```

## What Gets Deployed

The minimal deployment includes:

| Component | Purpose | Replicas |
|-----------|---------|----------|
| valkey | Redis/Valkey for leader election | 1 |
| runner-hybrid | Single runner for all work types | 2 |
| RBAC | ServiceAccount, Role, RoleBinding | - |
| ConfigMaps | Configuration, agent repos, permissions | - |
| Secrets | Placeholder credentials | - |

### Deferred Components

These can be added later after validation:
- coordinator.yaml (not required for simple deployments)
- runner-notification.yaml (use hybrid runner initially)
- runner-exploration.yaml (use hybrid runner initially)
- skill-sync.yaml (run on-demand)
- hpa.yaml (manual scaling works initially)
- servicemonitor.yaml (observability only)

## Step-by-Step Deployment

### Prerequisites

1. **kubectl access** to apexalgo-iad cluster with cluster-admin or namespace-admin permissions
2. **Kubeconfig** configured for apexalgo-iad cluster

### Step 1: Run the Deployment Script

```bash
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh
```

### Step 2: Verify Deployment

```bash
# Check all resources
kubectl get all -n botburrow-agents

# Expected output:
# NAME                                  READY   STATUS    RESTARTS   AGE
# pod/runner-hybrid-xxxxxxxxxx-xxxx     1/1     Running   0          1m
# pod/runner-hybrid-xxxxxxxxxx-xxxx     1/1     Running   0          1m
# pod/valkey-xxxxxxxxxx-xxxx            1/1     Running   0          1m

# NAME                     TYPE        CLUSTER-IP      PORT(S)    AGE
# service/runner-hybrid    ClusterIP   10.xx.xx.xx     9091/TCP   1m
# service/valkey           ClusterIP   10.xx.xx.xx     6379/TCP   1m

# NAME                             READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/runner-hybrid    2/2     2            2           1m
# deployment.apps/valkey           1/1     1            1           1m
```

### Step 3: Update Placeholder Secrets

```bash
# Edit botburrow-agents-secrets
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# Required keys to update:
# - HUB_API_KEY: Get from botburrow-hub admin
# - R2_ENDPOINT: Cloudflare R2 endpoint
# - R2_ACCESS_KEY: Cloudflare R2 access key
# - R2_SECRET_KEY: Cloudflare R2 secret key
# - FORGEJO_TOKEN: Forgejo PAT for git operations
# - GITHUB_TOKEN: GitHub PAT for external repos

# Edit mcp-credentials
kubectl edit secret mcp-credentials -n botburrow-agents

# Required keys to update:
# - GITHUB_PAT: GitHub PAT for MCP github server
# - BRAVE_API_KEY: Brave Search API key
```

### Step 4: Restart Runners to Pick Up New Secrets

```bash
kubectl rollout restart deployment/runner-hybrid -n botburrow-agents
```

### Step 5: Verify Health

```bash
# Check logs
kubectl logs -f -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid

# Port-forward to test health endpoint
kubectl port-forward -n botburrow-agents deployment/runner-hybrid 8080:9091

# In another terminal:
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

## Post-Deployment Operations

### Scaling Runners

```bash
# Scale to 3 replicas
kubectl scale deployment runner-hybrid -n botburrow-agents --replicas=3
```

### Adding Optional Components

```bash
# Deploy full set (coordinator, additional runners, HPA, etc.)
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-full.yaml
```

## ArgoCD Reconciliation Options

After the workaround deployment, you have two options for long-term management:

### Option 1: Continue with kubectl (Recommended initially)

- Manage changes via git + kubectl
- No ArgoCD sync issues to worry about
- Simpler operational model

### Option 2: Migrate to ArgoCD

1. **Fix the ArgoCD sync issue** - Requires ArgoCD access to debug why resources weren't deploying
2. **Create an ArgoCD Application** - Point to the botburrow-agents repository
3. **Let ArgoCD take over** - It will detect existing resources and manage them

```yaml
# Example ArgoCD Application (to be created after fixing sync issue)
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
    kustomize:
      buildOption: --kustomize=kustomization-minimal.yaml
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

## Troubleshooting

### Pods Not Starting

```bash
# Check logs
kubectl logs -n botburrow-agents <pod-name> --previous

# Common issues:
# - Missing secrets: Ensure botburrow-agents-secrets-PLACEHOLDER.yml was applied
# - Invalid config: Check ConfigMap values
# - Valkey connection: Ensure valkey pod is running
```

### Runner Not Polling for Work

```bash
# Check if runner can reach hub
kubectl exec -n botburrow-agents <runner-pod> -- curl -I https://hub.botburrow.internal

# Check HUB_API_KEY in secret
kubectl get secret botburrow-agents-secrets -n botburrow-agents -o jsonpath='{.data.HUB_API_KEY}' | base64 -d
```

### Git Clone Fails in Init Container

```bash
# Check if repo URL is accessible
kubectl exec -n botburrow-agents <runner-pod> -- git ls-remote https://github.com/jedarden/agent-definitions.git

# Check agent-definitions-repos ConfigMap
kubectl get configmap agent-definitions-repos -n botburrow-agents -o yaml
```

## Follow-Up Work

A follow-up bead should be created to:
1. **Investigate ArgoCD sync issue** - Requires ArgoCD admin access to debug why ApplicationSet isn't deploying resources
2. **Create proper ArgoCD Application** - Once the root cause is identified
3. **Migrate from kubectl to ArgoCD** - If desired for GitOps workflow

## References

- Original bead: bd-1v9 - Fix botburrow-agents deployment via ArgoCD
- Investigation findings: `/home/coder/botburrow-agents/argocd-investigation-findings.md`
- Minimal deployment: `/home/coder/botburrow-agents/k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md`
- Pre-flight check script: `/home/coder/botburrow-agents/scripts/preflight-check.sh`
- Deployment script: `/home/coder/botburrow-agents/scripts/deploy-workaround.sh`

## Success Criteria

- [x] Deployment script created and tested
- [x] Documentation written
- [ ] Deployment executed and verified
- [ ] Secrets updated with real values
- [ ] Runners polling for work successfully
- [ ] Follow-up bead created for ArgoCD resolution
