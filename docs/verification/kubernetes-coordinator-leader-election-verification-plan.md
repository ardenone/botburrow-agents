# Kubernetes Coordinator Leader Election Verification Plan

**Bead:** bd-1j7
**Status:** VERIFICATION INCOMPLETE - Logs not showing leader election
**Date:** 2026-02-15
**Updated:** After initial verification attempt

## Summary

This document outlines the full Kubernetes verification plan for the coordinator leader election implementation. The local tests pass, and the Kubernetes deployment is running, but **leader election cannot be verified from logs** due to missing startup/info log messages.

**See:** `kubernetes-coordinator-verification-results.md` for detailed findings.

## Current Status (2026-02-15)

### Completed
- [x] Local leader election verification (fakeredis) - **PASSED**
- [x] Work queue deduplication verification - **PASSED**
- [x] Circuit breaker verification - **PASSED**
- [x] Analysis of deployment blockers
- [x] Kubernetes deployment exists - **2/2 replicas running**
- [x] Valkey operational - **Active connections confirmed**

### Incomplete - Cannot Verify
- [⚠️] Leader election in Kubernetes logs - **NO LOG MESSAGES**
- [⚠️] Metrics endpoint access - **RBAC BLOCKED**
- [ ] Real leader election with Valkey - **NEEDS REDIS CLI ACCESS**
- [ ] Pod failover testing - **NEEDS DELETE PERMISSION**
- [ ] Work distribution verification - **NEEDS REDIS CLI ACCESS**

## Current Blockers

### Primary Blocker: Missing Leader Election Logs

**Issue:** Coordinator pods are running but logs don't show:
- No "coordinator_starting" messages
- No "became_leader" messages
- No "not_leader" messages
- Only ERROR logs visible (401 Unauthorized from Hub API)

**Possible Causes:**
1. **Image version mismatch** - Deployed image is `ronaldraygun/botburrow-agents:latest` not `ardenone/botburrow-agents:latest`
2. **Log filtering** - INFO level logs may be filtered before reaching pod logs
3. **Old code version** - Deployed image may not contain leader election code

**Resolution Options:**
1. Verify image contains leader election code
2. Enable DEBUG logging via environment variable
3. Rebuild and push fresh image
4. Check image build date and commit

### Secondary Blocker: RBAC Permissions (For Full Verification)

**Missing Permissions:**
- Cannot access service proxy endpoints (metrics at :9090)
- Cannot exec into pods (Redis CLI access)
- Cannot delete pods (failover testing)

**Human bead:** bd-3q9 (CLOSED but RoleBinding not actually applied)

**Quick resolution:**
```bash
kubectl apply -f /home/coder/botburrow-agents/k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml
```

### Tertiary Blocker: Image Version Uncertainty

**Current State:**
- Manifest specifies: `ardenone/botburrow-agents:latest`
- Deployed pods use: `ronaldraygun/botburrow-agents:latest`

**Questions:**
1. Is ronaldraygun/botburrow-agents the correct image?
2. When was it last built?
3. Does it contain leader election code?

**Resolution:**
1. Check image provenance
2. Verify image contains current code
3. Consider rebuilding and pushing to ardenone/botburrow-agents

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
