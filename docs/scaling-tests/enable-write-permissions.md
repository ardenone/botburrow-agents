# Enable Write Permissions for Runner Scaling Tests (bd-3o6)

## Problem Statement
The devpod-observer ServiceAccount in apexalgo-iad cluster has **read-only permissions** and cannot perform scaling operations needed for comprehensive runner pool scaling tests.

## Current Limitations
- ❌ Cannot `kubectl scale` deployments to test scaling behavior
- ❌ Cannot patch HPA configurations for autoscaling tests
- ❌ Cannot create RBAC resources (roles/rolebindings)
- ✅ Can observe resources, logs, and metrics

## Verified Status (2026-02-15)
```bash
# Test current permissions
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl auth can-i update deployments/scale -n botburrow-agents
# Result: no

kubectl auth can-i create roles -n botburrow-agents
# Result: no
```

## Solution Implemented
Created minimal RBAC manifests to grant **deployment scaling permissions only**:

### 1. Role: deployment-scaler
**File:** `cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-role.yml`

**Permissions granted:**
- `deployments/scale` - get, patch, update
- `replicasets/scale` - get, patch, update
- `deployments` - get, list, watch (read-only)
- `horizontalpodautoscalers` - get, list, watch, patch, update
- `pods` - get, list, watch (read-only, verify scaling)
- `events` - get, list, watch (read-only, debugging)

**Why these permissions:**
- Minimal permissions for scaling operations
- Read-only access maintained for most resources
- Sufficient for scaling tests without full admin access
- Does NOT allow creating/deleting resources

### 2. RoleBinding: devpod-observer-scaler
**File:** `cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-rolebinding.yml`

**Binds:**
- Role: `deployment-scaler` (botburrow-agents namespace)
- Subject: `devpod-observer` ServiceAccount (devpod-observer namespace)

## Required Human Action
**The devpod-observer ServiceAccount cannot apply these manifests itself** (read-only access). A human with cluster-admin access needs to:

### Option 1: Apply via kubectl (RECOMMENDED)
```bash
# From a machine with cluster-admin access to apexalgo-iad
kubectl apply -f cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-rolebinding.yml

# Verify permissions granted
kubectl auth can-i update deployments/scale -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
# Should return: yes
```

### Option 2: Deploy via ArgoCD
If these manifests should be managed by ArgoCD:

1. Add manifests to ArgoCD-managed repository
2. Create/update Application manifest to include botburrow-agents RBAC
3. Sync ArgoCD application

### Option 3: Alternative - Port-Forward Workaround
If granting write permissions is not desired, tests can run via port-forward:

```bash
# From devpod on ardenone-cluster
kubectl port-forward -n botburrow-agents svc/valkey 6379:6379 &

# Run tests against localhost
cd /home/coder/botburrow-agents
pytest tests/scaling/test_runner_pool_scaling.py
```

**Pros:**
- No cluster permissions needed
- Can run tests immediately

**Cons:**
- Cannot test actual in-cluster scaling behavior
- Network latency may affect results
- Workaround rather than proper solution

## Verification After Application
Once RBAC manifests are applied by human with cluster-admin access:

```bash
# From ardenone-cluster devpod
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

## Security Considerations
**Why this is safe:**
- ✅ Minimal permissions (only scaling, not create/delete)
- ✅ Namespace-scoped (botburrow-agents only)
- ✅ Cannot modify RBAC or escalate privileges
- ✅ Cannot create new resources or delete existing ones
- ✅ Read-only maintained for most resources
- ✅ Aligned with least-privilege principle

**What devpod-observer CANNOT do even after this change:**
- ❌ Create/delete deployments
- ❌ Modify RBAC (roles, rolebindings)
- ❌ Create/delete pods directly
- ❌ Access secrets or configmaps (unless separately granted)
- ❌ Escalate to cluster-admin

## Related Beads
- **bd-3o6** (HUMAN: Enable write permissions for runner scaling tests) - This bead
- **bd-3qv** (Test agent runner pool scaling) - Blocked by this bead

## Files Created
- `cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-role.yml`
- `cluster-configuration/apexalgo-iad/botburrow-agents/rbac/deployment-scaler-rolebinding.yml`
- `docs/scaling-tests/enable-write-permissions.md` (this file)

## Next Steps
1. **Human review and approval** of RBAC manifests
2. **Human application** of manifests to apexalgo-iad cluster
3. **Verification** of permissions from devpod
4. **Resume bd-3qv** to complete runner pool scaling tests
