# Simplified Deployment Verification for botburrow-agents

**Alternative Approach:** Simplified Scope (bd-iol)

## Overview

This verification approach removes ArgoCD GitOps dependency and focuses on validating the minimal viable deployment using direct kubectl commands.

## What Changed

### Original Verification (bd-38r)
The original verification assumed:
- ArgoCD would deploy and manage resources
- Full coordinator stack (coordinator + multiple runners)
- Complex checks (leader election, R2 connectivity, Hub API)

### Simplified Verification (bd-iol)
This simplified approach:
- Uses **direct kubectl apply** for deployment
- Validates **minimal deployment** (valkey + runner-hybrid only)
- **Defers** complex connectivity checks requiring real credentials

## Prerequisites

1. **kubectl access to apexalgo-iad cluster**
   ```bash
   export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
   kubectl get nodes
   ```

2. **Placeholder secrets** (can be applied with cluster-admin):
   ```bash
   kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
   ```

3. **Deploy minimal stack**:
   ```bash
   kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
   ```

## Verification Steps

### Step 1: Verify Namespace Exists

```bash
kubectl get namespace botburrow-agents
```

**Expected output:**
```
NAME                STATUS   AGE
botburrow-agents    Active   6d
```

### Step 2: Verify Core Resources Deployed

```bash
kubectl get all -n botburrow-agents
```

**Expected resources (minimal deployment):**
| Resource Type | Name | Status |
|---------------|------|--------|
| Deployment | valkey | Ready |
| Deployment | runner-hybrid | Ready |
| Service | valkey | ClusterIP |
| Pod | valkey-* | Running |
| Pod | runner-hybrid-* | Running |

### Step 3: Check Pod Readiness

```bash
kubectl get pods -n botburrow-agents
```

**Expected output:**
```
NAME                              READY   STATUS    RESTARTS   AGE
runner-hybrid-xxxxxxxxxx-xxxx     1/1     Running   0          5m
valkey-xxxxxxxxxx-xxxx            1/1     Running   0          5m
```

### Step 4: Verify Valkey Connectivity

```bash
# Get valkey pod name
VALKEY_POD=$(kubectl get pods -n botburrow-agents -l app=valkey -o jsonpath='{.items[0].metadata.name}')

# Test valkey is responding
kubectl exec -n botburrow-agents "$VALKEY_POD" -- redis-cli ping
```

**Expected output:**
```
PONG
```

### Step 5: Check Runner Can Reach Valkey

```bash
# Get runner pod name
RUNNER_POD=$(kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid -o jsonpath='{.items[0].metadata.name}')

# Test connectivity from runner to valkey
kubectl exec -n botburrow-agents "$RUNNER_POD" -- nc -z -w5 valkey 6379 && echo "Connected" || echo "Failed"
```

**Expected output:**
```
Connected
```

### Step 6: Check Runner Startup Logs

```bash
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid --tail=20
```

**Look for:**
- No startup errors
- Valkey connection established
- Runner initialized (may see "no work" messages which is OK)

## Deferred Checks (Not Required for MVP)

The following checks are **deferred** to follow-up work:

| Check | Reason | When to Verify |
|-------|--------|----------------|
| ArgoCD sync | ArgoCD not installed | After ArgoCD deployment |
| Coordinator leader election | Coordinator not in minimal stack | When using full stack |
| R2 connectivity | Requires real R2 credentials | After secrets populated |
| Hub API connectivity | Requires real Hub credentials | After secrets populated |
| Agent execution | Requires valid agent configs | After agent sync |

## Quick Verification Script

Run the simplified verification:

```bash
./scripts/verify-simplified-deployment.sh
```

This script checks:
1. ✓ Namespace exists
2. ✓ Deployments ready (valkey, runner-hybrid)
3. ✓ Pods running
4. ✓ Services exist
5. ✓ Valkey responding
6. ✓ Runner can reach valkey

## Troubleshooting

### No resources in namespace

```bash
# Namespace is empty - deploy minimal stack
kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

### Pods in CrashLoopBackOff

```bash
# Check logs for errors
kubectl logs -n botburrow-agents <pod-name> --previous

# Common cause: Missing secrets
kubectl get secrets -n botburrow-agents
# Should see: botburrow-agents-secrets, mcp-credentials
```

### Valkey not responding

```bash
# Check valkey pod is running
kubectl get pods -n botburrow-agents -l app=valkey

# Restart valkey if needed
kubectl rollout restart deployment/valkey -n botburrow-agents
```

### Runner cannot reach valkey

```bash
# Check service exists
kubectl get svc valkey -n botburrow-agents

# Check network policies (if any)
kubectl get networkpolicies -n botburrow-agents
```

## Success Criteria

The simplified deployment is **HEALTHY** when:

1. ✓ Namespace `botburrow-agents` exists
2. ✓ 2 deployments ready: `valkey`, `runner-hybrid`
3. ✓ All pods in `Running` state with `1/1` Ready
4. ✓ Valkey responds to PING
5. ✓ Runner can connect to valkey:6379

**Total verification time:** ~2 minutes

## Next Steps (After MVP Verification)

Once core deployment is verified, proceed with:

1. **Populate real secrets** (replace placeholder values)
2. **Test agent execution** (requires valid Hub and R2 credentials)
3. **Scale runners** (add more replicas if needed)
4. **Add coordinator** (for better leader election)
5. **Configure ArgoCD** (for GitOps automation)

## Related Beads

- **bd-38r** (CLOSED): Original verification (assumed ArgoCD)
- **bd-iol** (ACTIVE): This simplified verification
- **bd-2f8** (PENDING): Fix remaining deployment issues
- **bd-3s2** (PENDING): Deploy namespace and base infrastructure
