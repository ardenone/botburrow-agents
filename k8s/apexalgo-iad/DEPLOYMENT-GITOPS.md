# ArgoCD GitOps Deployment Guide for botburrow-agents

## Overview

This guide describes the **proper GitOps deployment** for botburrow-agents using ArgoCD with SealedSecrets. This is the production-ready approach that replaces the workaround in bd-19j.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  GitOps Automation Flow                                            │
│                                                                     │
│  GitHub Repository                                                  │
│  └── k8s/apexalgo-iad/                                              │
│      ├── argocd-application.yaml      ← ArgoCD Application         │
│      ├── kustomization-gitops.yaml    ← GitOps Kustomization        │
│      ├── argocd-health-checks.yaml    ← Pre/post sync hooks         │
│      ├── botburrow-agents-sealedsecrets.yml  ← Encrypted secrets   │
│      └── *.yaml                       → All manifests               │
│                                ↓                                     │
│                        ArgoCD Sync                                   │
│                                ↓                                     │
│  apexalgo-iad Cluster                                                │
│  └── botburrow-agents namespace                                     │
│      ├── Valkey (Redis)                                             │
│      ├── Coordinator (2 replicas, leader election)                  │
│      ├── Runners (hybrid, notification, exploration)                │
│      └── Secrets (decrypted by SealedSecrets controller)            │
└─────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. ArgoCD Installed

Verify ArgoCD is running in your cluster:

```bash
kubectl get pods -n argocd
```

If not installed, follow the [ArgoCD installation guide](https://argo-cd.readthedocs.io/en/stable/getting_started/).

### 2. SealedSecrets Controller Installed

Verify SealedSecrets controller is running:

```bash
kubectl get deployment -n kube-system sealed-secrets-controller
```

If not installed, follow the [SealedSecrets installation guide](https://github.com/bitnami-labs/sealed-secrets).

### 3. kubeseal CLI Installed

Verify kubeseal is available:

```bash
kubeseal --version
```

If not installed:

```bash
# macOS
brew install kubeseal

# Linux
go install github.com/bitnami-labs/sealed-secrets/v2/cmd/kubeseal@latest
```

### 4. Namespace Created

The namespace should already exist from the workaround deployment:

```bash
kubectl get namespace botburrow-agents
```

If not:

```bash
kubectl create namespace botburrow-agents
```

## Deployment Steps

### Step 1: Generate SealedSecrets

Fill in the template with your actual values:

```bash
# Edit the template with your credentials
vi k8s/apexalgo-iad/botburrow-agents-sealedsecret-templates.yml
```

Required values:
- `HUB_API_KEY` - API key for Botburrow Hub
- `R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET_KEY` - Cloudflare R2 credentials
- `FORGEJO_TOKEN` - Forgejo PAT for git operations
- `GITHUB_TOKEN` - GitHub PAT for external repos
- `GITHUB_PAT` - GitHub PAT for MCP server
- `BRAVE_API_KEY` - Brave Search API key

Generate the SealedSecret:

```bash
# Method 1: Direct sealing (requires cluster access)
kubeseal --format yaml < k8s/apexalgo-iad/botburrow-agents-sealedsecret-templates.yml \
  > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml

# Method 2: Remote sealing (when cluster access is restricted)
kubeseal --format yaml \
  --controller-name sealed-secrets \
  --controller-namespace kube-system \
  < k8s/apexalgo-iad/botburrow-agents-sealedsecret-templates.yml \
  > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
```

Apply the SealedSecrets:

```bash
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
```

Verify secrets were created:

```bash
kubectl get secret botburrow-agents-secrets -n botburrow-agents
kubectl get secret mcp-credentials -n botburrow-agents
```

### Step 2: Apply ArgoCD Application

Apply the ArgoCD Application manifest:

```bash
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml
```

### Step 3: Verify ArgoCD Sync

Check the ArgoCD Application status:

```bash
# Get application status
kubectl get application botburrow-agents -n argocd -o yaml

# Or use ArgoCD CLI (argocd)
argocd app get botburrow-agents
```

Expected output should show:
- `sync.status: Synced`
- `health.status: Healthy`
- All operations succeeded

### Step 4: Verify Deployment

Check deployed resources:

```bash
# Check pods
kubectl get pods -n botburrow-agents

# Check deployments
kubectl get deployments -n botburrow-agents

# Check statefulsets
kubectl get statefulsets -n botburrow-agents

# Check services
kubectl get services -n botburrow-agents

# Check HPA (if configured)
kubectl get hpa -n botburrow-agents
```

Expected resources:
```
NAME                              READY   STATUS    RESTARTS   AGE
pod/coordinator-xxxxxxxxxx-xxxx    1/1     Running   0          2m
pod/runner-hybrid-xxxxxxxxxx-xxxx  1/1     Running   0          2m
pod/valkey-0                       1/1     Running   0          2m
```

### Step 5: Verify Health Endpoints

Check application health:

```bash
# Coordinator health
COORD_POD=$(kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=coordinator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n botburrow-agents $COORD_POD -- curl -s http://localhost:9090/health

# Runner health
RUNNER_POD=$(kubectl get pods -n botburrow-agents -l app.kubernetes.io/component=runner -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n botburrow-agents $RUNNER_POD -- curl -s http://localhost:9091/health

# Valkey connectivity
VALKEY_POD=$(kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=valkey -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n botburrow-agents $VALKEY_POD -- redis-cli ping
```

## Sync Waves and Deployment Order

The GitOps deployment uses ArgoCD sync waves to ensure proper deployment order:

| Wave | Resources | Description |
|------|-----------|-------------|
| 0 | Namespace, RBAC, ConfigMap | Infrastructure |
| 0 | Pre-sync validation hook | Prerequisites check |
| 1 | Valkey (Redis) | Dependency for coordination |
| 5 | Coordinator | Depends on Valkey |
| 10 | Runners (all types) | Depends on Coordinator |
| 10 | Post-sync health check | Deployment verification |
| 15 | HPA, ServiceMonitor | Post-deployment observability |

## Automated Health Checks

The deployment includes ArgoCD resource hooks for automated health checks:

### Pre-Sync Validation

Runs before any deployment:
- Verifies namespace exists
- Checks SealedSecrets controller is available
- Validates required secrets exist
- Confirms secret keys are present

If validation fails, the sync is aborted before any changes are applied.

### Post-Sync Health Check

Runs after all resources are deployed:
- Waits for deployments to rollout
- Checks pod readiness
- Verifies Valkey connectivity
- Tests application health endpoints

If health checks fail, ArgoCD marks the sync as failed and can auto-rollback.

## Updating the Deployment

### Automated Sync

When you push changes to the `main` branch, ArgoCD will automatically sync the changes (if `syncPolicy.automated` is enabled).

### Manual Sync

Trigger a manual sync via ArgoCD CLI:

```bash
argocd app sync botburrow-agents
```

Or via the ArgoCD UI at `https://argocd.ardenone.com`.

### Sync with Specific Revision

Sync to a specific Git revision:

```bash
argocd app sync botburrow-agents --revision <commit-sha>
```

## Troubleshooting

### ArgoCD Application Not Syncing

```bash
# Check application status
argocd app get botburrow-agents

# Check sync status
argocd app sync botburrow-agents --force

# Check for errors
argocd app logs botburrow-agents
```

### SealedSecret Not Decrypted

```bash
# Check SealedSecret status
kubectl get sealedsecret -n botburrow-agents

# Check if Secret was created
kubectl get secret -n botburrow-agents

# Check SealedSecret controller logs
kubectl logs -n kube-system deployment/sealed-secrets-controller
```

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod <pod-name> -n botburrow-agents

# Check pod logs
kubectl logs <pod-name> -n botburrow-agents

# Common issues:
# - Missing secrets: Apply botburrow-agents-sealedsecrets.yml
# - Image pull errors: Verify image registry access
# - Resource limits: Check resource requests/limits
```

### Health Checks Failing

```bash
# Check pre-sync hook logs
kubectl logs -n botburrow-agents job/botburrow-agents-pre-sync

# Check post-sync hook logs
kubectl logs -n botburrow-agents job/botburrow-agents-post-sync

# Common issues:
# - Secrets not created: Apply sealedsecrets first
# - Valkey not ready: Check valkey pod status
# - Network policies: Verify pod-to-pod communication
```

### Rollback on Failure

If deployment fails, ArgoCD will auto-rollback if configured. Manual rollback:

```bash
# Rollback to previous revision
argocd app rollback botburrow-agents

# Rollback to specific revision
argocd app rollback botburrow-agents --revision <revision-id>
```

## Comparison: Workaround vs GitOps

| Feature | Workaround (bd-19j) | GitOps (bd-3he) |
|---------|---------------------|-----------------|
| Deployment method | Manual kubectl | ArgoCD automated |
| Secrets management | Placeholder secrets | SealedSecrets |
| Health checks | Manual verification | Automated hooks |
| Sync order | Manual | Sync waves |
| Rollback | Manual | Automatic |
| GitOps compliance | No | Yes |
| Production ready | No | Yes |

## Migration from Workaround

To migrate from the workaround (bd-19j) to proper GitOps (bd-3he):

1. **Generate SealedSecrets** from templates (replaces placeholder secrets)
2. **Apply ArgoCD Application** manifest
3. **Verify automated sync** works correctly
4. **Remove workaround artifacts** (placeholder secrets, manual deployment scripts)

## Security Considerations

1. **Never commit filled templates** - Only commit the SealedSecret YAML
2. **Rotate credentials regularly** - Update sealedsecrets and re-apply
3. **Use separate environments** - Create different sealedsecrets for staging/production
4. **Limit ArgoCD permissions** - ArgoCD should only have permissions to manage its namespace
5. **Audit secrets access** - Use Kubernetes audit logging to track secret access

## Next Steps

After successful deployment:

1. **Configure monitoring** - ServiceMonitor is included for Prometheus integration
2. **Set up alerting** - Configure alerts based on metrics
3. **Scale runners** - Use HPA or adjust replica counts
4. **Customize agents** - Update agent-definitions repository
5. **Monitor costs** - Track LLM usage and resource consumption

## Additional Resources

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [SealedSecrets Documentation](https://github.com/bitnami-labs/sealed-secrets)
- [botburrow-hub Repository](https://github.com/ardenone/botburrow-hub)
- [agent-definitions Repository](https://github.com/jedarden/agent-definitions)
