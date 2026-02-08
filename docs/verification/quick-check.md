# botburrow-agents Quick Verification Guide

**Simplified verification for bead bd-yct**

## Prerequisites

1. **kubectl access to apexalgo-iad cluster** from devpod on ardenone-cluster
2. **Namespace deployed**: `botburrow-agents` must exist

## Quick Verification

### Option 1: Run the verification script

```bash
cd /home/coder/botburrow-agents
./scripts/verify-deployment.sh
```

### Option 2: Manual checks

```bash
# Set kubeconfig
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
NAMESPACE=botburrow-agents

# 1. Check namespace exists
kubectl get namespace $NAMESPACE

# 2. Check pods are running
kubectl get pods -n $NAMESPACE

# 3. Check services
kubectl get svc -n $NAMESPACE

# 4. Check Valkey health
kubectl exec -n $NAMESPACE valkey-0 -- redis-cli ping

# 5. Check coordinator leader election
kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=coordinator --tail=50 | grep -i leader
```

## Expected Results

### If Deployment is Healthy

```
✓ Namespace: botburrow-agents exists
✓ Pods: coordinator, runner-* all Running
✓ Services: coordinator, skill-sync configured
✓ Valkey: PONG response
✓ Coordinator: Leader election active
```

### If Namespace Not Deployed

```
✗ Namespace: botburrow-agents not found
```

**Action required:**
```bash
kubectl --kubeconfig=$KUBECONFIG apply -k /home/coder/botburrow-agents/k8s/apexalgo-iad/
```

## Troubleshooting

### Pods not Running

```bash
# Check pod status
kubectl describe pod -n $NAMESPACE <pod-name>

# Check logs
kubectl logs -n $NAMESPACE <pod-name>
```

### Valkey Not Responding

```bash
# Check Valkey pod
kubectl get pods -n $NAMESPACE -l app=valkey

# Restart Valkey if needed
kubectl rollout restart statefulset/valkey -n $NAMESPACE
```

### Coordinator Issues

```bash
# Check for leader election
kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=coordinator --tail=100 | grep -i leader

# Check work queue
kubectl exec -n $NAMESPACE valkey-0 -- redis-cli LLEN "work:queue:high"
```

## Dependencies

The full verification (from original bead bd-38r) requires:

- ✅ **bd-1v9**: Fix botburrow-agents deployment via ArgoCD
- ✅ **bd-1x8**: Create SealedSecret for botburrow-agents from template
- ✅ **bd-2hq**: Fix kustomization.yaml to remove secrets.yaml reference

If any of these are not complete, the namespace may not deploy.

## Related Documentation

- [Full Deployment Guide](../deployment/deployment.md)
- [Troubleshooting](../operations/troubleshooting.md)
- [Architecture](../notes/architecture.md)
