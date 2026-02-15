# 🚨 HUMAN ACTION REQUIRED - Apply RBAC Manifests for Scaling Tests

## Summary
**Bead:** bd-3o6 (HUMAN: Enable write permissions for runner scaling tests)
**Status:** Ready for human review and application
**Urgency:** Blocking bd-3qv (Test agent runner pool scaling)

## What Was Prepared
I've created minimal RBAC manifests to grant the devpod-observer ServiceAccount **deployment scaling permissions only** in the botburrow-agents namespace of apexalgo-iad cluster.

### Files Created
1. `cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-role.yml`
   - Grants minimal scaling permissions (deployments/scale, HPAs)
   - Read-only for deployments, pods, events

2. `cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-rolebinding.yml`
   - Binds deployment-scaler role to devpod-observer ServiceAccount

3. `docs/scaling-tests/enable-write-permissions.md`
   - Complete documentation and verification steps

## Why I Cannot Apply Myself
The devpod-observer ServiceAccount has **read-only permissions** and cannot create RBAC resources:

```bash
kubectl auth can-i create roles -n botburrow-agents
# Result: no

kubectl auth can-i create rolebindings -n botburrow-agents
# Result: no
```

## Required Human Action

### Step 1: Review Manifests
Review the RBAC manifests for security:
- ✅ Namespace-scoped (botburrow-agents only)
- ✅ Minimal permissions (only scaling, no create/delete)
- ✅ Cannot modify RBAC or escalate privileges
- ✅ Read-only maintained for most resources

### Step 2: Apply Manifests
**From a machine with cluster-admin access to apexalgo-iad:**

```bash
# Apply RBAC manifests
kubectl apply -f cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-rolebinding.yml

# Verify permissions granted
kubectl auth can-i update deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Should return: yes
```

### Step 3: Verify from Devpod
**From ardenone-cluster devpod (after Step 2):**

```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Test scaling permissions
kubectl auth can-i update deployments/scale -n botburrow-agents
# Should return: yes

# Test actual scaling
kubectl scale deployment/runner-exploration --replicas=2 -n botburrow-agents
kubectl get deployment/runner-exploration -n botburrow-agents
# Should show 2 replicas

# Scale back
kubectl scale deployment/runner-exploration --replicas=1 -n botburrow-agents
```

### Step 4: Update Bead Status
Once verified:

```bash
cd /home/coder/botburrow-agents
br close bd-3o6 --status completed --note "RBAC manifests applied and verified"
```

## Alternative Option (If Write Permissions Not Desired)
If granting write permissions is not acceptable, tests can run via port-forward:

```bash
# From devpod on ardenone-cluster
kubectl port-forward -n botburrow-agents svc/valkey 6379:6379 &

# Run tests against localhost
cd /home/coder/botburrow-agents
pytest tests/scaling/test_runner_pool_scaling.py
```

**Trade-offs:**
- ✅ No cluster permissions needed
- ❌ Cannot test actual in-cluster scaling behavior
- ❌ Network latency may affect results

## Security Impact Assessment

### What devpod-observer CAN do after this change:
- ✅ Scale deployments up/down in botburrow-agents namespace
- ✅ Modify HPA settings for autoscaling tests
- ✅ Read deployment, pod, and event resources

### What devpod-observer CANNOT do:
- ❌ Create/delete deployments or pods
- ❌ Modify RBAC (roles, rolebindings)
- ❌ Access secrets or configmaps
- ❌ Escalate to cluster-admin
- ❌ Affect other namespaces

### Risk Level: **LOW**
- Namespace-scoped permissions
- No resource creation/deletion capability
- No privilege escalation paths
- Aligned with least-privilege principle

## Related Beads
- **bd-3o6** - This bead (HUMAN: Enable write permissions for runner scaling tests)
- **bd-3qv** - Blocked by this (Test agent runner pool scaling)

## Questions or Concerns?
If you have questions about the RBAC manifests or prefer a different approach, please:
1. Review `docs/scaling-tests/enable-write-permissions.md` for full details
2. Update bd-3o6 with your decision
3. Consider the port-forward alternative if write permissions are not acceptable
