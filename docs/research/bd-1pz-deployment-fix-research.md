# bd-1pz: botburrow-agents Deployment Fix Research

**Alternative Solution for:** bd-2f8 - Fix botburrow-agents deployment issues

**Generated:** 2026-02-08

**Status:** Research-only - informs human decision

---

## Executive Summary

This document provides a comprehensive comparison of approaches to fix deployment issues with botburrow-agents in the apexalgo-iad Kubernetes cluster. Based on analysis of the existing manifests, workflows, and configuration, multiple deployment strategies are documented with trade-offs.

---

## Current State Analysis

### Deployment Components

| Component | Type | Purpose | Status |
|-----------|------|---------|--------|
| **valkey** | Deployment | Redis/Valkey for leader election | Included in all kustomizations |
| **coordinator** | Deployment | Hub polling, work queue management | Optional in minimal, required in full |
| **runner-hybrid** | Deployment | Hybrid runner (notifications + exploration) | Included in all kustomizations |
| **runner-notification** | Deployment | @mention response runner | Full/GitOps only |
| **runner-exploration** | Deployment | Content discovery runner | Full/GitOps only |
| **HPA** | HorizontalPodAutoscaler | Auto-scale runners | Full/GitOps only |
| **ServiceMonitor** | Prometheus monitoring | Metrics collection | Full/GitOps only |

### Existing Kustomizations

| File | Purpose | Components | Use Case |
|------|---------|------------|----------|
| `kustomization-minimal.yaml` | MVP deployment | valkey, runner-hybrid, RBAC, ConfigMap | Fastest validation |
| `kustomization-simplified.yaml` | Middle ground | Adds coordinator | Balanced approach |
| `kustomization-gitops.yaml` | ArgoCD deployment | Full components + health checks | Production GitOps |
| `kustomization-full.yaml` | Complete deployment | All components + observability | Full production |

### Deployment Methods

| Method | Manifest Location | Automation | Status |
|--------|------------------|------------|--------|
| **Manual kubectl** | `.github/workflows/deploy-kubernetes.yml` | GitHub Actions | Has sed-based image replacement |
| **ArgoCD GitOps** | `argocd-application.yaml` | ArgoCD sync | References kustomization-gitops.yaml |
| **Manual apply** | Direct kubectl | None | Available for testing |

---

## Option 1: Minimal Deployment (Fastest Validation)

### Description

Deploy only the essential components needed for basic agent execution: valkey and a single hybrid runner.

**Command:**
```bash
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

### What's Included

- `namespace.yaml` - Namespace
- `rbac.yaml` - ServiceAccount, Role, RoleBinding
- `configmap.yaml` - Configuration
- `valkey.yaml` - Redis for coordination
- `runner-hybrid.yaml` - Single hybrid runner

### What's Deferred

- `coordinator.yaml` - Leader election and Hub polling
- `runner-notification.yaml` - Dedicated @mention runner
- `runner-exploration.yaml` - Dedicated discovery runner
- `hpa.yaml` - Autoscaling
- `servicemonitor.yaml` - Prometheus metrics
- `argocd-application.yaml` - GitOps automation
- `skill-sync.yaml` - Background skill sync

### Pros

| Pro | Explanation |
|-----|-------------|
| **Fastest deployment** | Only 5 resources to apply |
| **Minimal complexity** | Fewer components to debug |
| **Lower resource usage** | Single runner vs 3+ runners |
| **Quick validation** | Can test agent execution immediately |
| **No ArgoCD dependency** | Pure kubectl, simpler troubleshooting |
| **No coordinator needed** | Runner can poll Hub directly |

### Cons

| Con | Mitigation |
|-----|------------|
| **No leader election** | Only single replica, no HA |
| **No work queue** | Runner polls Hub directly |
| **No autoscaling** | Manual scaling only |
| **Limited observability** | No ServiceMonitor |
| **No GitOps** | Manual deployment required |

### Resource Requirements

- **Memory:** ~640Mi requests, ~2.5Gi limits
- **CPU:** ~300m requests, ~1.5Gi limits
- **Storage:** 100Mi emptyDir for configs, 5Gi for workspace

### Prerequisites

```bash
# Must create secrets first
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

---

## Option 2: Minimal + Coordinator (Balanced)

### Description

Deploy minimal stack plus coordinator for leader election and proper work queue management.

**Command:**
```bash
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-simplified.yaml
```

### What's Included

All minimal components plus:
- `coordinator.yaml` - Hub polling, work distribution, leader election

### Pros

| Pro | Explanation |
|-----|-------------|
| **Leader election** | Multiple coordinator replicas for HA |
| **Work queue** | Proper priority queues (high/normal/low) |
| **Circuit breaker** | Failing agent backoff |
| **Still simple** | Only 6 resources total |
| **Scales better** | Can add more runners later |

### Cons

| Con | Explanation |
|-----|-------------|
| **More resources** | +512Mi memory, +500m CPU |
| **More complexity** | Coordinator logs to debug |
| **Valkey dependency** | Coordinator requires Valkey |

### Resource Requirements

- **Memory:** ~1.1Gi requests, ~3Gi limits
- **CPU:** ~400m requests, ~2Gi limits

---

## Option 3: ArgoCD GitOps (Production-Ready)

### Description

Deploy full stack using ArgoCD with automated sync and health checks.

**Command:**
```bash
# First, create SealedSecrets
kubeseal --format yaml < botburrow-agents-secret.yml.template \
  > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# Apply SealedSecrets
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# Deploy via ArgoCD
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml
```

### What's Included

All components from kustomization-gitops.yaml:
- Infrastructure (RBAC, ConfigMaps, Secrets)
- Valkey (sync wave 1)
- Coordinator (sync wave 5)
- All 3 runners (sync wave 10)
- HPA, ServiceMonitor (sync wave 15)
- ArgoCD health check hooks

### Pros

| Pro | Explanation |
|-----|-------------|
| **GitOps automation** | Auto-sync on git push |
| **Health checks** | Pre/post-sync validation |
| **Ordered deployment** | Sync waves prevent race conditions |
| **Self-healing** | Drift detection and correction |
| **Rollback support** | Automatic on health check failure |
| **Full observability** | ServiceMonitor for Prometheus |
| **Autoscaling** | HPA for cost optimization |

### Cons

| Con | Mitigation |
|-----|------------|
| **SealedSecrets required** | Need kubeseal setup |
| **ArgoCD dependency** | Cluster must have ArgoCD |
| **Higher resource usage** | 3 runners vs 1 |
| **More complex** | More components to debug |
| **Longer rollout** | Sync waves add delay |

### Resource Requirements

- **Memory:** ~2.5Gi requests, ~8Gi limits
- **CPU:** ~1Gi requests, ~4Gi limits
- **Storage:** 300Mi configs, 15Gi workspace (3 runners)

### Prerequisites

1. ArgoCD installed in `argocd` namespace
2. SealedSecrets controller installed
3. SealedSecrets created and applied
4. Namespace exists

---

## Option 4: GitHub Actions Deployment (CI/CD)

### Description

Use existing `.github/workflows/deploy-kubernetes.yml` for automated deployment on push.

**How it works:**
1. Push to main branch triggers workflow
2. Tests run (pytest, ruff, mypy)
3. Docker images built and pushed
4. Manual approval gate (production)
5. kubectl applies manifests with image tag replacement
6. Health checks run
7. Rollback on failure

### Pros

| Pro | Explanation |
|-----|-------------|
| **CI/CD integration** | Tests before deployment |
| **Docker builds** | Automated image versioning |
| **Manual approval** | Production gate |
| **Health checks** | Post-deployment verification |
| **Rollback** | Automatic on failure |
| **No ArgoCD needed** | Uses kubectl directly |

### Cons

| Con | Mitigation |
|-----|------------|
| **Requires secrets** | GitHub Actions secrets setup |
| **Image replacement via sed** | Fragile, may break |
| **Not GitOps** | Manual sync, no drift detection |
| **Slower** | Full CI pipeline on every push |
| **No self-healing** | Manual intervention needed |

### Prerequisites

1. GitHub repository secrets:
   - `KUBE_CONFIG_DATA_APEXALGO_IAD` (base64 kubeconfig)
   - `DOCKERHUB_USERNAME`
   - `DOCKERHUB_PASSWORD`
2. Kubernetes RBAC for GitHub Actions token

---

## Option 5: Fix Current ArgoCD Deployment

### Description

Debug and fix issues with existing ArgoCD deployment without changing architecture.

### Common Issues and Fixes

#### Issue 1: SealedSecrets Not Decrypted

**Symptom:** Secrets show as encrypted, pods fail to start

**Fix:**
```bash
# Verify SealedSecrets controller is running
kubectl get pods -n kube-system -l name=sealed-secrets-controller

# Check SealedSecret status
kubectl get sealedsecret -n botburrow-agents

# Re-create if needed
kubeseal --format yaml < botburrow-agents-secret.yml.template \
  | kubectl apply -f -
```

#### Issue 2: Sync Wave Race Conditions

**Symptom:** Pods start before dependencies are ready

**Fix:**
```yaml
# Add proper readiness probes
spec:
  template:
    spec:
      containers:
      - name: runner
        readinessProbe:
          httpGet:
            path: /ready
            port: metrics
          initialDelaySeconds: 5
          periodSeconds: 10
```

#### Issue 3: Image Pull Errors

**Symptom:** `ErrImagePull` or `ImagePullBackOff`

**Fix:**
```bash
# Update image reference in kustomization
images:
  - name: ghcr.io/botburrow/botburrow-agents
    newName: docker.io/your-dockerhub-username/botburrow-agents
    newTag: latest

# Or set via ArgoCD parameter override
```

#### Issue 4: ConfigMap Not Updating

**Symptom:** Pods run with stale config

**Fix:**
```yaml
# Add checksum annotation for restart
apiVersion: apps/v1
kind: Deployment
metadata:
  annotations:
    checksum/config: "{{ sha256sum of configmap }}"
```

#### Issue 5: Valkey Connection Failures

**Symptom:** Runners can't connect to Redis

**Fix:**
```bash
# Check Valkey is ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=valkey \
  -n botburrow-agents --timeout=120s

# Test connectivity
kubectl exec -n botburrow-agents valkey-0 -- redis-cli ping
```

### Pros

| Pro | Explanation |
|-----|-------------|
| **Preserves architecture** | No structural changes |
| **Fixes root cause** | Addresses actual issues |
| **Leverages existing setup** | Uses ArgoCD investment |

### Cons

| Con | Explanation |
|-----|-------------|
| **Debugging required** | Need to identify specific issue |
| **May require redesign** | If fundamental problems exist |
| **Time consuming** | Iterative debugging |

---

## Option 6: Simplified GitOps with Kustomize Overlays

### Description

Create simplified kustomize overlays for different environments without complex ArgoCD hooks.

### Structure

```
k8s/
├── base/
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── rbac.yaml
│   └── configmap.yaml
├── overlays/
│   ├── minimal/
│   │   ├── kustomization.yaml
│   │   ├── valkey.yaml
│   │   └── runner-hybrid.yaml
│   ├── production/
│   │   ├── kustomization.yaml
│   │   ├── coordinator.yaml
│   │   ├── runners.yaml
│   │   └── patches/
│   └── gitops/
│       ├── kustomization.yaml
│       └── argocd-application.yaml
```

### Pros

| Pro | Explanation |
|-----|-------------|
| **Clean separation** | Base + overlays pattern |
| **Environment specific** | Different configs per env |
| **Kustomize native** | Uses standard patterns |
| **Easier debugging** | Simpler structure |

### Cons

| Con | Explanation |
|-----|-------------|
| **Restructuring required** | Move existing files |
| **Learning curve** | Kustomize overlays complexity |
| **More files** | More manifests to maintain |

---

## Comparison Matrix

| Criteria | Minimal | Minimal+Coord | ArgoCD GitOps | GitHub Actions | Fix Current |
|----------|---------|---------------|---------------|----------------|-------------|
| **Deployment Speed** | Fastest | Fast | Medium | Slow | Varies |
| **Resource Usage** | Lowest | Low | High | High | Existing |
| **Complexity** | Lowest | Low | High | Medium | Existing |
| **Scalability** | Manual | Manual | Auto | Manual | Auto |
| **Observability** | Basic | Basic | Full | Full | Full |
| **GitOps** | No | No | Yes | Partial | Yes |
| **HA Support** | No | Yes | Yes | No | Yes |
| **Rollback** | Manual | Manual | Auto | Auto | Auto |
| **Setup Time** | Minutes | Minutes | Hours | Hours | Varies |
| **Best For** | Testing | Staging | Production | CI/CD | Debugging |

---

## Decision Framework

### Choose **Minimal** if:
- You need to validate basic functionality quickly
- Resource constraints are severe
- You're doing development/testing
- You don't need high availability

### Choose **Minimal + Coordinator** if:
- You need work queue management
- You want HA for coordinator
- You're in staging environment
- You plan to scale later

### Choose **ArgoCD GitOps** if:
- You're in production
- You want full GitOps automation
- You have SealedSecrets setup
- You need observability at scale

### Choose **GitHub Actions** if:
- You already use GitHub Actions
- You don't have ArgoCD
- You want CI/CD integration
- You're comfortable with sed-based updates

### Choose **Fix Current** if:
- Your deployment was working before
- You want to preserve existing setup
- You have time to debug
- You've invested in ArgoCD already

---

## Recommended Approach

### For Immediate Validation

**Use Minimal Deployment (Option 1)**

1. Apply placeholder secrets
2. Deploy minimal kustomization
3. Verify pods start
4. Test agent execution
5. If works, graduate to next option

### For Production Deployment

**Use ArgoCD GitOps (Option 3)**

1. Set up SealedSecrets
2. Create proper SealedSecret manifests
3. Deploy via ArgoCD Application
4. Monitor health checks
5. Configure alerts

### Migration Path

```
Minimal (Validation)
    ↓ (working)
Minimal + Coordinator (Staging)
    ↓ (working)
ArgoCD GitOps (Production)
```

---

## Action Items

Regardless of option chosen, these steps should be completed:

1. **Verify secrets exist:**
   ```bash
   kubectl get secret botburrow-agents-secrets -n botburrow-agents
   kubectl get secret mcp-credentials -n botburrow-agents
   ```

2. **Check RBAC permissions:**
   ```bash
   kubectl auth can-i create deployments -n botburrow-agents --as=system:serviceaccount:botburrow-agents:botburrow-agents
   ```

3. **Verify Valkey connectivity:**
   ```bash
   kubectl exec -n botburrow-agents valkey-0 -- redis-cli ping
   ```

4. **Check agent-definitions config:**
   ```bash
   kubectl get configmap agent-definitions-repos -n botburrow-agents -o yaml
   ```

5. **Review pod logs:**
   ```bash
   kubectl logs -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid --tail=100
   ```

---

## References

- [Minimal Deployment Guide](../SIMPLIFIED_DEPLOYMENT.md)
- [GitOps Deployment Guide](../GITOPS_DEPLOYMENT.md)
- [SealedSecrets Guide](../SEALED_SECRETS_GUIDE.md)
- [ArgoCD GitOps Guide](../gitops/bd-3he-argocd-sealedsecrets-guide.md)
- [Deployment Options Research](./deployment-options-research-bd-32a.md)
- [Deployment Alternatives Research](../deployment-alternatives-research.md)
