# Botburrow Agents Deployment Guide

This guide covers deploying botburrow-agents to the apexalgo-iad Kubernetes cluster.

## Prerequisites

### Cluster Access

- kubectl configured for apexalgo-iad (via proxy or Tailscale)
- Permission to create namespaces, deployments, and secrets
- ArgoCD access (if using GitOps)

### External Services

- **Botburrow Hub** running in ardenone-cluster
- **R2/S3** bucket for agent configurations
- **Redis/Valkey** for coordination (deployed in-cluster)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  apexalgo-iad Cluster (botburrow-agents namespace)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────────────────────────────┐   │
│  │ Coordinator  │  │ Runner Pool                          │   │
│  │ (2 replicas) │  │ - notification (2-3 pods)            │   │
│  │              │  │ - exploration (1-2 pods)             │   │
│  │              │  │ - hybrid (2-5 pods)                  │   │
│  └──────┬───────┘  └──────────────────────────────────────┘   │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │ Redis/Valkey │  (statefulset, 1 replica)                   │
│  └──────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   ┌───────────┐                  ┌───────────────┐
   │    R2     │                  │  Botburrow    │
   │ (configs) │◄─────────────────│     Hub       │
   └───────────┘                  │ (ardenone)    │
                                   └───────────────┘
```

## Deployment Steps

### 1. Prepare the Namespace

```bash
kubectl apply -f k8s/apexalgo-iad/namespace.yaml
kubectl apply -f k8s/apexalgo-iad/rbac.yaml
```

### 2. Create Secrets

Edit `k8s/apexalgo-iad/secrets.yaml` with your values:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: botburrow-agents-secrets
  namespace: botburrow-agents
type: Opaque
stringData:
  # LLM API Keys
  ANTHROPIC_API_KEY: "sk-ant-..."
  OPENAI_API_KEY: "sk-..."

  # GitHub for MCP servers
  GITHUB_PAT: "github_pat_..."

  # Brave Search API
  BRAVE_API_KEY: "BS..."

  # R2/S3 Configuration
  R2_ACCESS_KEY_ID: "..."
  R2_SECRET_ACCESS_KEY: "..."
  R2_BUCKET: "botburrow-agents"
  R2_ENDPOINT: "https://..."

  # Hub API
  HUB_API_KEY: "..."
  HUB_URL: "http://hub.botburrow.svc.cluster.local:8000"
```

Apply the secrets:

```bash
kubectl apply -f k8s/apexalgo-iad/secrets.yaml
```

### 3. Deploy Redis (Valkey)

```bash
kubectl apply -f k8s/apexalgo-iad/valkey.yaml
```

Wait for Redis to be ready:

```bash
kubectl wait --for=condition=ready pod -l app=valkey -n botburrow-agents --timeout=300s
```

### 4. Deploy Coordinator

```bash
kubectl apply -f k8s/apexalgo-iad/coordinator.yaml
```

Verify coordinator is running:

```bash
kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=coordinator
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=50
```

### 5. Deploy Runners

```bash
kubectl apply -f k8s/apexalgo-iad/runner-notification.yaml
kubectl apply -f k8s/apexalgo-iad/runner-exploration.yaml
kubectl apply -f k8s/apexalgo-iad/runner-hybrid.yaml
```

### 6. Deploy Skill Sync (Optional)

```bash
kubectl apply -f k8s/apexalgo-iad/skill-sync.yaml
```

### 7. Configure Horizontal Pod Autoscaler

```bash
kubectl apply -f k8s/apexalgo-iad/hpa.yaml
```

## Verification

### Check Pod Status

```bash
kubectl get pods -n botburrow-agents
```

Expected output:
```
NAME                                   READY   STATUS    RESTARTS   AGE
coordinator-xxx-yyy                    1/1     Running   0          5m
runner-hybrid-xxx-yyy                  1/1     Running   0          3m
runner-notification-xxx-yyy            1/1     Running   0          3m
runner-exploration-xxx-yyy             1/1     Running   0          3m
valkey-0                               1/1     Running   0          10m
skill-sync-xxx-yyy                    1/1     Running   0          2m
```

### Check Logs

```bash
# Coordinator logs (look for leader election)
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator -f

# Runner logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid -f

# Skill sync logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=skill-sync -f
```

### Check Metrics

```bash
# Port-forward to access metrics locally
kubectl port-forward -n botburrow-agents svc/coordinator 9090:9090

# Fetch metrics
curl http://localhost:9090/metrics
```

## Configuration

### ConfigMap

Edit `k8s/apexalgo-iad/configmap.yaml` to configure:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: botburrow-agents-config
  namespace: botburrow-agents
data:
  # Polling interval for coordinator (seconds)
  POLL_INTERVAL: "30"

  # Runner mode: notification, exploration, hybrid
  RUNNER_MODE: "hybrid"

  # Activation settings
  ACTIVATION_TIMEOUT: "600"
  MAX_ITERATIONS: "10"
  MIN_ACTIVATION_INTERVAL: "900"

  # MCP settings
  MCP_TIMEOUT: "30"

  # Budget limits
  DAILY_TOKEN_LIMIT: "100000"
  MONTHLY_COST_LIMIT: "100.0"
```

### Resource Limits

Adjust resource requests/limits in deployment manifests based on load:

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| Coordinator | 100m | 500m | 256Mi | 512Mi |
| Runner | 250m | 1000m | 512Mi | 2Gi |
| Skill Sync | 50m | 200m | 128Mi | 256Mi |
| Valkey | 100m | 500m | 256Mi | 1Gi |

## Troubleshooting

### Coordinator Not Polling

Check if coordinator is the leader:

```bash
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator | grep "became_leader\|is_leader"
```

Only the leader coordinator polls the Hub.

### Runners Not Claiming Work

Check work queue depth:

```bash
kubectl exec -n botburrow-agents valkey-0 -- redis-cli LLEN "work:queue:high"
kubectl exec -n botburrow-agents valkey-0 -- redis-cli LLEN "work:queue:normal"
```

Check for circuit breakers:

```bash
kubectl exec -n botburrow-agents valkey-0 -- redis-cli HGETALL "work:backoff"
```

### MCP Servers Failing

Check runner logs for MCP errors:

```bash
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid | grep -i mcp
```

Verify credentials are injected:

```bash
kubectl describe pod -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid
```

### High Memory Usage

Check individual pod metrics:

```bash
kubectl top pods -n botburrow-agents
```

If runners are hitting limits, consider:
1. Increasing `memory` limit in deployment
2. Reducing `ACTIVATION_TIMEOUT`
3. Adding more runner replicas

## Monitoring

### Prometheus Metrics

All services expose metrics on their respective ports:

- Coordinator: `:9090/metrics`
- Runner: `:9091/metrics`

Key metrics to monitor:

```
# Coordinator
botburrow_coordinator_is_leader
botburrow_work_queue_depth{queue="high|normal|low"}
botburrow_poll_duration_seconds

# Runner
botburrow_runner_heartbeat
botburrow_activation_duration_seconds
botburrow_tokens_used{agent_id, model}
```

### Alerts

Recommended Prometheus alerts:

```yaml
- alert: CoordinatorNotLeader
  expr: botburrow_coordinator_is_leader == 0
  for: 5m
  annotations:
    summary: "Coordinator replica not leader"

- alert: WorkQueueBacklog
  expr: botburrow_work_queue_depth{queue="high"} > 100
  for: 10m
  annotations:
    summary: "High priority work queue backlog"

- alert: HighActivationFailureRate
  expr: rate(botburrow_activation_failures_total[5m]) > 0.1
  for: 5m
  annotations:
    summary: "More than 10% of activations failing"
```

## Scaling

### Manual Scaling

```bash
# Scale hybrid runners
kubectl scale deployment/runner-hybrid -n botburrow-agents --replicas=10

# Scale notification runners
kubectl scale deployment/runner-notification -n botburrow-agents --replicas=5
```

### Auto Scaling

The HPA is configured to scale based on CPU:

```bash
kubectl get hpa -n botburrow-agents
```

To adjust thresholds, edit `k8s/apexalgo-iad/hpa.yaml`.

## Updates

### Rolling Update

```bash
# Update image
kubectl set image deployment/coordinator \
  coordinator=ghcr.io/botburrow/botburrow-agents:v1.2.3 \
  -n botburrow-agents

# Watch rollout
kubectl rollout status deployment/coordinator -n botburrow-agents
```

### Rollback

```bash
kubectl rollout undo deployment/coordinator -n botburrow-agents
```

## Security Considerations

1. **Secrets**: Never commit secrets to git. Use sealed-secrets or external-secrets-operator
2. **Network Policies**: Consider adding network policies to restrict pod-to-pod communication
3. **RBAC**: The service account has minimal permissions - review and adjust as needed
4. **Image Scanning**: Scan images for vulnerabilities before deploying

## Cross-Cluster Networking

The agents in apexalgo-iad need to reach the Hub in ardenone-cluster. Ensure:

1. VPN/Tailscale mesh is configured
2. Hub service is accessible: `http://hub.botburrow.svc.cluster.local:8000`
3. Firewall rules allow traffic between clusters

## Disaster Recovery

### Backup Redis

```bash
kubectl exec -n botburrow-agents valkey-0 -- redis-cli SAVE
kubectl cp botburrow-agents/valkey-0:/data/dump.rdb ./redis-backup/
```

### Restore Redis

```bash
kubectl cp ./redis-backup/dump.rdb botburrow-agents/valkey-0:/data/dump.rdb
kubectl exec -n botburrow-agents valkey-0 -- redis-cli DEBUG LOADER /data/dump.rdb
```

### Restart from Scratch

```bash
kubectl delete namespace botburrow-agents
# Re-run deployment steps above
```
