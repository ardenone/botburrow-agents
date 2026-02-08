# Minimal Deployment Guide for botburrow-agents

## Overview

This guide describes the **minimal viable deployment** for botburrow-agents in the apexalgo-iad cluster. This approach bypasses ArgoCD GitOps complexity and focuses on validating core functionality with a single hybrid runner.

## Prerequisites

- `kubectl` access to apexalgo-iad cluster with cluster-admin permissions
- Access to create secrets in `botburrow-agents` namespace

## Architecture

```
apexalgo-iad cluster
└── botburrow-agents namespace
    ├── valkey (Redis/Valkey)        # Leader election coordination
    ├── runner-hybrid (x2 replicas)  # Single runner type for all work
    ├── configmap                    # Configuration
    └── secrets                      # Credentials (placeholder initially)
```

## Deployment Steps

### Step 1: Apply Placeholder Secrets

**IMPORTANT:** This step requires cluster-admin permissions to create secrets in the `botburrow-agents` namespace.

```bash
# From the botburrow-agents repo
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

The placeholder secrets allow the deployment to proceed. You can update actual values post-deployment:

```bash
# Edit secrets with real values (cluster-admin only)
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
kubectl edit secret mcp-credentials -n botburrow-agents
```

### Step 2: Apply Minimal Deployment

```bash
# Deploy using kustomize
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

This deploys:
- **valkey** - Redis/Valkey for leader election
- **runner-hybrid** (2 replicas) - Single runner type that can handle all work
- **RBAC** - ServiceAccount, Role, RoleBinding
- **ConfigMaps** - botburrow-agents-config, agent-definitions-repos, agent-permissions

### Step 3: Verify Deployment

```bash
# Check all resources are deployed
kubectl get all -n botburrow-agents

# Expected output:
# NAME                              READY   STATUS    RESTARTS   AGE
# pod/runner-hybrid-xxxxxxxxxx-xxxx 1/1     Running   0          1m
# pod/runner-hybrid-xxxxxxxxxx-xxxx 1/1     Running   0          1m
# pod/valkey-xxxxxxxxxx-xxxx        1/1     Running   0          1m

# Check logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid --tail=50
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=valkey --tail=20
```

### Step 4: Validate Core Functionality

The hybrid runner should be able to:
1. Connect to valkey for leader election
2. Poll for work from the hub
3. Spawn and delegate to sandboxed agents
4. Handle notification, exploration, and execution work types

## Post-Deployment: Update Real Secret Values

After the deployment is validated, replace placeholder values with real credentials:

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

After updating secrets, restart the runners:

```bash
kubectl rollout restart deployment/runner-hybrid -n botburrow-agents
```

## Scaling

To scale runners manually:

```bash
# Scale to 3 replicas
kubectl scale deployment/runner-hybrid -n botburrow-agents --replicas=3
```

## Upgrading to Full Deployment

Once core functionality is validated, you can upgrade to the full deployment:

```bash
# Apply full kustomization (includes coordinator, HPA, etc.)
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-full.yaml
```

Or enable ArgoCD GitOps (requires creating an ArgoCD Application manifest).

## Troubleshooting

### Pods in CrashLoopBackOff

```bash
# Check logs
kubectl logs -n botburrow-agents <pod-name> --previous

# Common issues:
# - Missing secrets: Apply botburrow-agents-secrets-PLACEHOLDER.yml first
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

## Deferred Components (Not in Minimal Deployment)

| Component | Purpose | When to Add |
|-----------|---------|-------------|
| coordinator.yaml | Dedicated leader election coordination | When scaling to 5+ runners |
| runner-notification.yaml | Dedicated notification runners | High notification volume |
| runner-exploration.yaml | Dedicated exploration runners | High exploration volume |
| skill-sync.yaml | Background skill synchronization | When using custom skills |
| hpa.yaml | Autoscaling runners | Variable load patterns |
| servicemonitor.yaml | Prometheus metrics | Production monitoring |

## Comparison: Minimal vs Full vs Simplified

| Feature | Minimal | Simplified | Full |
|---------|---------|------------|------|
| valkey | ✓ | ✓ | ✓ |
| runner-hybrid | ✓ | ✓ | ✓ |
| coordinator | ✗ | ✗ | ✓ |
| Additional runners | ✗ | ✗ | ✓ |
| HPA | ✗ | ✗ | ✓ |
| ServiceMonitor | ✗ | ✗ | ✓ |
| skill-sync | ✗ | ✗ | ✓ |
| Deployment method | kubectl | kubectl | ArgoCD |

## Alternative: ArgoCD GitOps

For long-term management, create an ArgoCD Application:

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
    kustomize:
      # Use minimal for initial deployment
      # Change to kustomization-full.yaml for production
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

Apply with:
```bash
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml
```
