# Kubernetes Coordinator Leader Election Verification Plan

**Bead:** bd-1j7
**Status:** BLOCKED - Waiting for cluster-admin to apply secrets
**Blocker:** /home/coder workspace bead bd-psf5 (HUMAN: Apply botburrow-agents secrets)

## Summary

This document outlines the full Kubernetes verification plan for the coordinator leader election implementation. The local tests pass, but the Kubernetes deployment is blocked because required secrets don't exist in the apexalgo-iad cluster.

## Current Status

### Completed
- [x] Local leader election verification (fakeredis) - **PASSED**
- [x] Work queue deduplication verification - **PASSED**
- [x] Circuit breaker verification - **PASSED**
- [x] Analysis of deployment blockers

### Blocked
- [ ] Kubernetes deployment verification (blocked by missing secrets)
- [ ] Real leader election with Valkey
- [ ] Pod failover testing
- [ ] Work distribution verification

## Blockers

### Primary Blocker: Missing Secrets

The `botburrow-agents` namespace exists but is empty. Required secrets:
- `botburrow-agents-secrets` - Hub API, R2 storage, Git credentials
- `mcp-credentials` - MCP server API keys

**Human bead for resolution:** bd-psf5 in /home/coder workspace

**Quick resolution:**
```bash
# From cluster-admin context (not devpod):
kubectl apply -f /home/coder/botburrow-agents/k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

### Secondary Blocker: RBAC Permissions

The devpod-observer ServiceAccount has read-only permissions in botburrow-agents namespace.

**Human bead for resolution:** bd-3cpp in /home/coder workspace

**Quick resolution:**
```bash
kubectl apply -f /home/coder/botburrow-agents/k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml
```

## Verification Plan (Once Unblocked)

### Step 1: Deploy Coordinator Stack
```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Apply base resources (if not already deployed)
kubectl apply -k /home/coder/botburrow-agents/k8s/apexalgo-iad

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=coordinator -n botburrow-agents --timeout=120s
```

### Step 2: Verify Initial Deployment
```bash
# Check pods are running
kubectl get pods -n botburrow-agents

# Should see 2 coordinator replicas:
# coordinator-xxxxx-xxxxx   2/2     Running   0          30s
# coordinator-xxxxx-xxxxx   2/2     Running   0          30s
```

### Step 3: Verify Leader Election
```bash
# Check logs for leader election
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=50 | grep -i leader

# Expected output:
# - One pod logs "Became leader"
# - One pod logs "Not elected as leader"
# - Leader logs heartbeat messages
```

### Step 4: Test Leader Failover
```bash
# Identify the leader pod
LEADER_POD=$(kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=coordinator -o json | \
  jq -r '.items[] | select(.metadata.name | test("coordinator-.*")) | .metadata.name' | head -1)

# Delete the leader pod
kubectl delete pod -n botburrow-agents $LEADER_POD

# Watch the remaining pod take over leadership
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=20 -f | grep -i leader
```

### Step 5: Verify Work Queue Distribution
```bash
# Check Valkey for work queue state
VALKEY_POD=$(kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=valkey -o jsonpath='{.items[0].metadata.name}')

# Execute redis-cli in Valkey pod
kubectl exec -n botburrow-agents $VALKEY_POD -- redis-cli

# In redis-cli:
> LLEN work:queue:high     # Check queue lengths
> LLEN work:queue:normal
> LLEN work:queue:low
> HGETALL work:active      # Check active tasks
> GET coordinator:leader   # Verify leader key
> TTL coordinator:leader   # Check leader TTL (should be > 0)
```

### Step 6: Test Circuit Breaker
```bash
# Simulate a failing agent by adding it to backoff
VALKEY_POD=$(kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=valkey -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n botburrow-agents $VALKEY_POD -- redis-cli HSET work:backoff test-agent-999 $(date +%s)

# Try to enqueue work for the backed-off agent (should be rejected)
# Verify backoff expiration works
```

### Step 7: Verify No Duplicate Processing
```bash
# Monitor work queue processing
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=100 | grep -E "(Processing work|Already in active)"

# Expected: Each agent_id should only appear once in active tasks
# Duplicate enqueue attempts should be rejected
```

## Success Criteria

1. **Deployment**: All pods running and healthy
2. **Leader Election**: Exactly one leader at any time
3. **Failover**: New leader elected within 30 seconds of leader failure
4. **Work Distribution**: No duplicate processing, proper queue prioritization
5. **Circuit Breaker**: Failed agents are backed off and not re-enqueued

## Related Files

- `scripts/verify_leader_election.py` - Local verification script
- `src/botburrow_agents/coordinator/work_queue.py` - Work queue implementation
- `src/botburrow_agents/coordinator/main.py` - Coordinator entry point
- `k8s/apexalgo-iad/coordinator.yaml` - Kubernetes deployment manifest
- `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml` - Placeholder secrets

## Related Beads

- bd-1j7 - This bead (Full Kubernetes coordinator leader election verification)
- bd-psf5 - HUMAN: Apply botburrow-agents secrets (blocker)
- bd-3cpp - HUMAN: Grant devpod-observer RBAC (secondary blocker)
- bd-87d - Alternative: Local verification workaround (COMPLETED)
- bd-31k - Original verification bead (superseded by this one)

## Next Steps

1. **Human applies secrets** (bd-psf5)
2. **Human grants RBAC** (bd-3cpp)
3. **Worker resumes** this bead and executes verification plan
4. **Document results** in this file
5. **Close bead** when all tests pass
