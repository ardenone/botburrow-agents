# Simplified Deployment Guide for botburrow-agents

## Overview

This guide covers the simplified deployment approach for botburrow-agents, bypassing ArgoCD issues for initial deployment.

## Current Situation

- **Status**: Namespace exists but no resources deployed
- **Blocker**: ArgoCD Application not syncing resources properly
- **Workaround**: Direct kubectl deployment using simplified manifest set

## Simplified Deployment (MVP)

### Scope

The simplified deployment includes only essential components:

| Resource | Purpose | Status |
|----------|---------|--------|
| namespace | Namespace isolation | Already exists |
| rbac.yaml | ServiceAccount, Role, RoleBinding | Required |
| configmap.yaml | Application configuration | Required |
| valkey.yaml | Redis/Valkey for coordination | Required |
| runner-hybrid.yaml | Single runner type (hybrid mode) | Required |

### Deferred Components

These components can be added later:

| Resource | Purpose | Why Deferred |
|----------|---------|--------------|
| hpa.yaml | Autoscaling | Can scale manually initially |
| servicemonitor.yaml | Prometheus metrics | Observability only |
| skill-sync.yaml | Background skill sync | Can run on-demand |
| coordinator.yaml | Coordination service | Optional for simple deployments |
| runner-notification.yaml | Notification runner | Use single hybrid runner initially |
| runner-exploration.yaml | Exploration runner | Use single hybrid runner initially |

## Deployment Steps

### Step 1: Create Secrets (cluster-admin only)

The placeholder secrets file exists at:
```
k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**Requirements**: Cluster-admin role to create secrets in botburrow-agents namespace.

**Apply secrets**:
```bash
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**Update with real credentials** (post-deployment):
```bash
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
kubectl edit secret mcp-credentials -n botburrow-agents
```

### Step 2: Apply Simplified Kustomization

After secrets are created, deploy the simplified manifest set:

```bash
# Option A: From the project root
kubectl apply -k k8s/apexalgo-iad/ --context=apexalgo-iad

# Option B: Using explicit kubeconfig
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig apply -k /home/coder/botburrow-agents/k8s/apexalgo-iad/
```

The `kustomization.yaml` has been updated to use the simplified resource set.

### Step 3: Verify Deployment

```bash
# Check resources
kubectl get all -n botburrow-agents

# Check pods are running
kubectl get pods -n botburrow-agents

# Check logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/component=runner
```

## Post-Deployment

### Scaling

Manual scaling (until HPA is added):
```bash
# Scale hybrid runner
kubectl scale deployment runner-hybrid --replicas=3 -n botburrow-agents
```

### Monitoring

Check logs for health:
```bash
# Runner logs
kubectl logs -n botburrow-agents deployment/runner-hybrid -f

# Valkey logs
kubectl logs -n botburrow-agents deployment/valkey -f
```

### Adding Components Later

To add deferred components:

1. **Add HPA for autoscaling**:
   ```bash
   kubectl apply -f k8s/apexalgo-iad/hpa.yaml
   ```

2. **Add ServiceMonitor for Prometheus**:
   ```bash
   kubectl apply -f k8s/apexalgo-iad/servicemonitor.yaml
   ```

3. **Add skill-sync job**:
   ```bash
   kubectl apply -f k8s/apexalgo-iad/skill-sync.yaml
   ```

4. **Add more runner types**:
   ```bash
   kubectl apply -f k8s/apexalgo-iad/runner-notification.yaml
   kubectl apply -f k8s/apexalgo-iad/runner-exploration.yaml
   ```

## Troubleshooting

### Pods not starting

Check events:
```bash
kubectl describe pod -n botburrow-agents <pod-name>
```

Common issues:
- Missing secrets - ensure botburrow-agents-secrets exists
- Image pull errors - ensure ghcr.io/botburrow/botburrow-agents:latest exists
- ConfigMap errors - ensure configmap.yaml applied successfully

### Git clone failures in init containers

If init container fails to clone agent-definitions repo:
- Check repo URL in ConfigMap
- Ensure git credentials are valid
- Check network connectivity

### Valkey connection issues

If runner cannot connect to valkey:
- Check valkey pod is running: `kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=valkey`
- Check service exists: `kubectl get svc -n botburrow-agents valkey`
- Check REDIS_URL in ConfigMap

## ArgoCD Migration (Future)

To eventually migrate back to ArgoCD GitOps:

1. Ensure all resources are applied and managed by ArgoCD labels
2. Update ArgoCD Application to sync the kustomization
3. Remove `--context=apexalgo-iad` manual deployments
4. Let ArgoCD manage lifecycle going forward

## Files Modified

- `k8s/apexalgo-iad/kustomization.yaml` - Updated to simplified resource list
- `k8s/apexalgo-iad/DEPLOYMENT-SIMPLIFIED.md` - This document
- Original `kustomization.yaml` backed up as `kustomization-full.yaml` (if needed)
