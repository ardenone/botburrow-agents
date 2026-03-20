# GitOps Deployment Guide for botburrow-agents

**Status:** Implemented (bd-3he)
**Date:** 2026-02-08
**Approach:** GitHub Actions + kubectl (Self-hosted GitOps without ArgoCD)

## Overview

This document describes the GitOps deployment solution for botburrow-agents. Since ArgoCD is not installed in the apexalgo-iad cluster, we've implemented a self-contained GitOps workflow using GitHub Actions that provides:

- Automated deployment on push to main branch
- SealedSecret integration for secure credentials
- Health checks and automated rollback on failure
- Manual approval gate for production deployments
- Full deployment verification

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GitOps Deployment Flow                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Developer Pushes Code                                              │
│     └─→ GitHub Repository (main branch)                                │
│                                                                         │
│  2. GitHub Actions Triggered                                           │
│     ├─→ Build & Test                                                   │
│     ├─→ Build Docker Images                                            │
│     ├─→ Push to Docker Hub                                             │
│     └─→ Wait for Manual Approval (production)                          │
│                                                                         │
│  3. Deploy to Kubernetes                                               │
│     ├─→ Configure kubectl (using kubeconfig secret)                    │
│     ├─→ Apply Kubernetes manifests                                     │
│     ├─→ Update image tags                                              │
│     └─→ Wait for rollout                                               │
│                                                                         │
│  4. Health Checks                                                      │
│     ├─→ Verify pod readiness                                           │
│     ├─→ Check health endpoints (/health, /ready)                       │
│     ├─→ Verify Valkey connectivity                                    │
│     └─→ Check logs for errors                                         │
│                                                                         │
│  5. Rollback on Failure                                               │
│     └─→ kubectl rollout undo deployment                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. Kubernetes Cluster Access

You need a valid kubeconfig for the apexalgo-iad cluster. The kubeconfig should be stored as a GitHub Actions secret.

**Generate the base64-encoded kubeconfig:**

```bash
# From a machine with cluster access
cat ~/.kube/config | base64 -w 0
```

**Add to GitHub repository secrets:**

1. Go to repository Settings → Secrets and variables → Actions
2. Add new secret: `KUBE_CONFIG_DATA_APEXALGO_IAD`
3. Paste the base64-encoded kubeconfig

### 2. Container Registry (GHCR)

CI/CD pushes images to GitHub Container Registry (GHCR). No manual secrets are needed — authentication uses the automatic `GITHUB_TOKEN` provided by GitHub Actions.

Image: `ghcr.io/ardenone/botburrow-agents`

### 3. SealedSecret Controller (Optional but Recommended)

For secure secrets management, install the SealedSecret controller:

```bash
# From cluster-admin context
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml
```

## Deployment Workflow

### Automatic Deployment (Push to Main)

```bash
# Make changes to code or manifests
git add .
git commit -m "feat: add new feature"
git push origin main

# GitHub Actions will:
# 1. Run tests
# 2. Build Docker images
# 3. Wait for manual approval
# 4. Deploy to Kubernetes
# 5. Run health checks
```

### Manual Deployment (Workflow Dispatch)

```bash
# Via GitHub UI:
# 1. Go to Actions tab
# 2. Select "Deploy to Kubernetes" workflow
# 3. Click "Run workflow"
# 4. Select options:
#    - environment: production or staging
#    - skip_health_checks: true (for initial deployment)
# 5. Click "Run workflow"
```

### Local Deployment (kubectl)

For testing or emergency deployments:

```bash
# Deploy from local machine
kubectl apply -f k8s/apexalgo-iad/namespace.yaml
kubectl apply -f k8s/apexalgo-iad/rbac.yaml
kubectl apply -f k8s/apexalgo-iad/configmap.yaml
kubectl apply -f k8s/apexalgo-iad/valkey.yaml
kubectl apply -f k8s/apexalgo-iad/coordinator.yaml
kubectl apply -f k8s/apexalgo-iad/runner-hybrid.yaml
kubectl apply -f k8s/apexalgo-iad/runner-notification.yaml
kubectl apply -f k8s/apexalgo-iad/runner-exploration.yaml
kubectl apply -f k8s/apexalgo-iad/hpa.yaml
```

## Secrets Management

### Option 1: SealedSecret (Recommended for Production)

SealedSecrets allow you to commit encrypted secrets to Git while keeping them secure.

**Generate a SealedSecret:**

```bash
# 1. Fill in the secret template
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
# Edit /tmp/botburrow-agents-secret.yml with real values

# 2. Create SealedSecret
kubeseal --format=yaml --controller-namespace=sealed-secrets \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# 3. Commit to Git
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret for botburrow-agents"
git push origin main

# The SealedSecret controller will automatically decrypt and create the Secret
```

**Required secret keys:**

| Key | Description | Source |
|-----|-------------|--------|
| `HUB_API_KEY` | Botburrow Hub authentication | Generate at hub.botburrow.com |
| `R2_ENDPOINT` | Cloudflare R2 storage | Cloudflare dashboard |
| `R2_ACCESS_KEY` | R2 access credentials | Cloudflare dashboard |
| `R2_SECRET_KEY` | R2 secret credentials | Cloudflare dashboard |
| `FORGEJO_USER` | Forgejo username | Your Forgejo account |
| `FORGEJO_TOKEN` | Forgejo PAT | Generate in Forgejo settings |
| `GITHUB_USER` | GitHub username | Your GitHub account |
| `GITHUB_TOKEN` | GitHub PAT | Generate in GitHub settings |

### Option 2: Placeholder Secrets (For Testing)

For initial deployment or testing, use placeholder secrets:

```bash
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**⚠️ WARNING:** Placeholder secrets should be replaced with real values before production use.

### Updating Secrets

**Option 1: Edit in-place (not recommended for production):**

```bash
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
```

**Option 2: Re-create with new values:**

```bash
# Create new secret
kubectl create secret generic botburrow-agents-secrets -n botburrow-agents \
  --from-literal=HUB_API_KEY="new-value" \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart deployments to pick up new secrets
kubectl rollout restart deployment/coordinator -n botburrow-agents
kubectl rollout restart deployment/runner-hybrid -n botburrow-agents
```

**Option 3: Create new SealedSecret (recommended):**

```bash
# Update template and regenerate
kubeseal --format=yaml --controller-namespace=sealed-secrets \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# Commit and push
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "feat: update SealedSecret"
git push origin main
```

## Health Checks

The deployment workflow includes automated health checks:

### 1. Pod Readiness

```bash
# Wait for all pods to be ready
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/part-of=botburrow \
  -n botburrow-agents --timeout=300s
```

### 2. Health Endpoints

All services expose health endpoints:

```bash
# Coordinator health
kubectl exec -n botburrow-agents <coordinator-pod> -- \
  curl http://localhost:9090/health

# Runner health
kubectl exec -n botburrow-agents <runner-pod> -- \
  curl http://localhost:9091/health
```

### 3. Valkey Connectivity

```bash
# Check Valkey is responding
kubectl exec -n botburrow-agents valkey-0 -- redis-cli ping
# Expected: PONG
```

### 4. Manual Verification Script

```bash
# Run comprehensive verification
./scripts/verify-gitops-deployment.sh --namespace botburrow-agents
```

## Rollback Procedures

### Automatic Rollback

The GitHub Actions workflow automatically rolls back if health checks fail:

```yaml
# From deploy-kubernetes.yml
- name: Rollback on failure
  if: failure() && steps.health_check.outcome == 'failure'
  run: |
    kubectl rollout undo deployment/coordinator -n botburrow-agents
    kubectl rollout undo deployment/runner-hybrid -n botburrow-agents
```

### Manual Rollback

```bash
# Rollback to previous revision
kubectl rollout undo deployment/coordinator -n botburrow-agents
kubectl rollout undo deployment/runner-hybrid -n botburrow-agents
kubectl rollout undo deployment/runner-notification -n botburrow-agents
kubectl rollout undo deployment/runner-exploration -n botburrow-agents

# Check rollback status
kubectl rollout status deployment/coordinator -n botburrow-agents
```

### Rollback to Specific Revision

```bash
# View deployment history
kubectl rollout history deployment/coordinator -n botburrow-agents

# Rollback to specific revision
kubectl rollout undo deployment/coordinator -n botburrow-agents --to-revision=3
```

## Monitoring and Troubleshooting

### View Deployment Status

```bash
# Check all resources
kubectl get all -n botburrow-agents

# Check deployments
kubectl get deployments -n botburrow-agents

# Check pods
kubectl get pods -n botburrow-agents

# Check services
kubectl get services -n botburrow-agents

# Check HPA
kubectl get hpa -n botburrow-agents
```

### View Logs

```bash
# Follow coordinator logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator -f

# Follow runner logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/component=runner -f

# Check Valkey logs
kubectl logs -n botburrow-agents valkey-0

# Check specific pod logs
kubectl logs -n botburrow-agents <pod-name> --tail=100
```

### Debug Pod Issues

```bash
# Describe pod to see events
kubectl describe pod -n botburrow-agents <pod-name>

# Check pod status
kubectl get pods -n botburrow-agents -o wide

# Check resource usage
kubectl top pods -n botburrow-agents
```

### Common Issues

**Pods stuck in ImagePullBackOff:**

```bash
# Check image name and tag
kubectl get deployment coordinator -n botburrow-agents -o jsonpath='{.spec.template.spec.containers[0].image}'

# Verify image exists in Docker Hub
# Update if needed
kubectl set image deployment/coordinator \
  coordinator=docker.io/<username>/botburrow-agents:<tag> \
  -n botburrow-agents
```

**Pods stuck in CrashLoopBackOff:**

```bash
# Check logs for errors
kubectl logs -n botburrow-agents <pod-name> --previous

# Check for missing secrets
kubectl describe pod -n botburrow-agents <pod-name>
```

**Secrets not mounted:**

```bash
# Verify secrets exist
kubectl get secrets -n botburrow-agents

# Describe deployment to check secret references
kubectl describe deployment coordinator -n botburrow-agents
```

## Scaling

### Manual Scaling

```bash
# Scale deployments
kubectl scale deployment coordinator --replicas=3 -n botburrow-agents
kubectl scale deployment runner-hybrid --replicas=5 -n botburrow-agents
```

### Auto Scaling (HPA)

The HPA automatically scales based on CPU usage:

```yaml
# From k8s/apexalgo-iad/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: runner-hybrid-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: runner-hybrid
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## CI/CD Integration

The deployment workflow integrates with the existing CI/CD pipeline:

1. **Build**: `.github/workflows/ci-cd.yml` - Runs tests and builds images
2. **Deploy**: `.github/workflows/deploy-kubernetes.yml` - Deploys to Kubernetes
3. **Verify**: `scripts/verify-gitops-deployment.sh` - Verifies deployment health

## Comparison with ArgoCD

| Feature | This Solution (GitHub Actions) | ArgoCD |
|---------|-------------------------------|--------|
| **Installation Required** | No (uses GitHub Actions) | Yes (cluster install) |
| **GitOps Support** | Yes (push-to-deploy) | Yes (native) |
| **Automated Sync** | Yes (on push) | Yes (continuous) |
| **Health Checks** | Yes (custom) | Yes (built-in) |
| **Rollback** | Yes (manual/auto) | Yes (auto) |
| **Multi-cluster** | Yes (with config) | Yes (native) |
| **Secrets Management** | SealedSecrets | SealedSecrets |
| **Complexity** | Low | Medium |
| **Resource Usage** | None (GitHub-hosted) | Cluster resources |

## Migration to ArgoCD (Future)

If ArgoCD is installed in the future, migration is straightforward:

1. Install ArgoCD in apexalgo-iad cluster
2. Create Application manifest for botburrow-agents
3. Disable GitHub Actions deployment workflow
4. ArgoCD will automatically sync manifests from Git

## References

- [GitHub Actions Deploy Workflow](.github/workflows/deploy-kubernetes.yml)
- [Kubernetes Manifests](../k8s/apexalgo-iad/)
- [SealedSecret Documentation](https://github.com/bitnami-labs/sealed-secrets)
- [Workaround Summary](../k8s/apexalgo-iad/WORKARSUMMARY-argocd-bypass.md)

## Summary

This GitOps solution provides:

✅ Automated deployment on push to main
✅ Secure secrets management with SealedSecrets
✅ Health checks and automated rollback
✅ Manual approval for production
✅ Full deployment verification
✅ Zero cluster resource overhead (GitHub-hosted)

The solution is production-ready and can be easily migrated to ArgoCD in the future if desired.
