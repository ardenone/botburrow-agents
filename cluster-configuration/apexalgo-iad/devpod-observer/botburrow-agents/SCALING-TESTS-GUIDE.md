# Runner Pool Scaling Tests - Access Guide

**Context:** bd-3o6 - Enable write permissions for runner scaling tests
**Related Bead:** bd-3qv - Test agent runner pool scaling
**Date:** 2026-02-15

## Problem Statement

The devpod-observer ServiceAccount has read-only permissions in apexalgo-iad cluster, preventing comprehensive scaling tests for the botburrow-agents runner pools. This guide provides two approaches:

1. **Immediate Solution:** Port-forward to Valkey for local testing
2. **Long-term Solution:** Grant deployment-scaler permissions via RBAC

---

## Option 1: Port-Forward Testing (Requires RBAC - See Option 2)

### Overview
Use kubectl port-forward to access the Valkey instance directly from the devpod, allowing tests to run locally while observing in-cluster behavior.

**⚠️ IMPORTANT:** Port-forward requires `pods/portforward` permission, which is **NOT** currently granted to devpod-observer. The deployment-scaler RBAC manifest (Option 2) includes this permission.

### Advantages
- ✅ Full control over test execution
- ✅ Can simulate work queue behavior
- ✅ No need to apply test resources to cluster

### Limitations
- ❌ **Requires pods/portforward permission** (included in deployment-scaler RBAC)
- ⚠️ Cannot test actual deployment scaling behavior
- ⚠️ Cannot verify HPA responses
- ⚠️ Network latency may differ from in-cluster
- ⚠️ Workaround rather than proper integration test

### Status
- ❌ **NOT CURRENTLY AVAILABLE** - Requires RBAC from Option 2 to be applied first

### Usage

#### Step 1: Start Port-Forward
```bash
# From devpod with apexalgo-iad kubeconfig
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Forward Valkey service to localhost
kubectl port-forward -n botburrow-agents svc/valkey 6379:6379 &
```

#### Step 2: Run Tests Against Localhost
```bash
# Set Valkey connection to localhost
export VALKEY_HOST=localhost
export VALKEY_PORT=6379

# Run scaling tests
cd /home/coder/botburrow-agents
python tests/scaling/test_runner_pool_scaling.py

# Or with pytest
pytest tests/scaling/test_runner_pool_scaling.py -v
```

#### Step 3: Observe In-Cluster Behavior
```bash
# In another terminal, watch pod scaling
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Watch runner pods scale
watch -n 2 'kubectl get pods -n botburrow-agents -l app.kubernetes.io/component=runner'

# Watch deployment replicas
kubectl get deployments -n botburrow-agents -w

# Check HPA status
kubectl get hpa -n botburrow-agents -w
```

#### Step 4: Cleanup
```bash
# Kill port-forward when done
pkill -f "port-forward.*valkey"
```

### Example Test Workflow

```bash
#!/bin/bash
# test-runner-scaling-portforward.sh

set -e

export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

echo "🚀 Starting Valkey port-forward..."
kubectl port-forward -n botburrow-agents svc/valkey 6379:6379 > /tmp/valkey-portforward.log 2>&1 &
PF_PID=$!
sleep 2

echo "✅ Port-forward active (PID: $PF_PID)"

echo "🧪 Running scaling tests against localhost:6379..."
export VALKEY_HOST=localhost
export VALKEY_PORT=6379

cd /home/coder/botburrow-agents
pytest tests/scaling/test_runner_pool_scaling.py -v --tb=short

echo "🧹 Cleaning up..."
kill $PF_PID

echo "✅ Tests complete!"
```

---

## Option 2: Deployment-Scaler RBAC (Long-term Solution)

### Overview
Grant the devpod-observer ServiceAccount minimal permissions to scale deployments and manage HPAs in the botburrow-agents namespace.

### Advantages
- ✅ Proper integration testing
- ✅ Can test actual deployment scaling
- ✅ Can verify HPA behavior
- ✅ Minimal permissions (only scaling operations)
- ✅ Maintains read-only for other resources

### Limitations
- ⚠️ Requires cluster-admin to apply manifests
- ⚠️ Still cannot apply new resources (pods, configmaps, etc.)

### RBAC Manifest

**File:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml`

The manifest grants:
- `deployments/scale` - patch/update
- `deployments` - get/list/watch
- `horizontalpodautoscalers` - get/list/watch/patch/update
- `pods` - get/list/watch
- `replicasets` - get/list/watch

### Application Process

**⚠️ REQUIRES HUMAN ACTION - Cluster Admin Access Needed**

This manifest must be applied by someone with cluster-admin access to apexalgo-iad cluster.

#### Option A: Apply via kubectl (from cluster-admin context)
```bash
# From a machine with cluster-admin access to apexalgo-iad
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

#### Option B: Apply via ArgoCD (if configured)
```bash
# Add manifest to ArgoCD-managed repository
# Commit to git and let ArgoCD sync
git add cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/
git commit -m "feat(bd-3o6): Add deployment-scaler RBAC for botburrow-agents testing"
git push origin main
```

#### Option C: Manual Application (for verification)
```yaml
# Copy/paste the YAML from deployment-scaler-role.yml
# Apply via Kubernetes dashboard or kubectl
```

### Verification

After RBAC is applied, verify from devpod:

```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Test scaling permission
kubectl scale deployment runner-exploration -n botburrow-agents --replicas=2

# Verify scale operation succeeded
kubectl get deployment runner-exploration -n botburrow-agents

# Check HPA access
kubectl get hpa -n botburrow-agents

# Test HPA patch permission
kubectl patch hpa runner-exploration-hpa -n botburrow-agents -p '{"spec":{"maxReplicas":5}}'
```

### Usage in Tests

Once RBAC is applied, tests can scale deployments directly:

```python
# tests/scaling/test_runner_pool_scaling.py

import subprocess
import os

def scale_deployment(name: str, replicas: int, namespace: str = "botburrow-agents"):
    """Scale a deployment using kubectl."""
    os.environ["KUBECONFIG"] = "/home/coder/.kube/apexalgo-iad.kubeconfig"

    cmd = [
        "kubectl", "scale", "deployment", name,
        "-n", namespace,
        f"--replicas={replicas}"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Failed to scale: {result.stderr}"

    return result.stdout

def test_runner_scaling_under_load():
    """Test that runner deployments scale appropriately under work queue load."""

    # Scale down to baseline
    scale_deployment("runner-exploration", replicas=1)

    # Inject work items into Valkey queue
    # ... (work queue injection code)

    # Wait for HPA to trigger scaling
    time.sleep(60)

    # Verify scaled up
    result = subprocess.run([
        "kubectl", "get", "deployment", "runner-exploration",
        "-n", "botburrow-agents",
        "-o", "jsonpath='{.status.replicas}'"
    ], capture_output=True, text=True)

    replicas = int(result.stdout.strip("'"))
    assert replicas > 1, "Deployment should have scaled up"
```

---

## Recommended Testing Workflow

**⚠️ UPDATED:** Port-forward also requires RBAC permissions (pods/portforward). Both testing approaches now require the deployment-scaler RBAC to be applied.

### Phase 1: Request RBAC Permissions (REQUIRED FOR ALL TESTING)
1. Submit deployment-scaler-role.yml for review ✅
2. Wait for cluster-admin to apply manifest ⏳
3. Verify permissions via kubectl ⏳

### Phase 2: Port-Forward Testing (Once RBAC Applied)
1. Use port-forward to run initial tests ⏳
2. Validate work queue behavior ⏳
3. Confirm test suite functionality ⏳
4. Document baseline metrics ⏳

### Phase 3: Integration Testing (Full Scaling Capabilities)
1. Run full scaling tests with deployment control ⏳
2. Test HPA behavior under varying loads ⏳
3. Validate autoscaling thresholds ⏳
4. Document production-ready scaling parameters ⏳

---

## Current Status

- ✅ **RBAC manifests created** - deployment-scaler-role.yml (includes pods/portforward)
- ✅ **Testing approaches documented** - Port-forward and direct scaling
- ⏳ **RBAC not yet applied** - Requires cluster-admin action
- ❌ **bd-3qv still blocked** - CANNOT proceed until RBAC is applied (port-forward requires permissions)

## Next Actions

### For Worker (Automated)
1. ✅ Create RBAC manifests
2. ✅ Document testing approaches
3. ✅ Commit to GitHub
4. ⏳ Wait for RBAC to be applied before proceeding with bd-3qv tests

### For Human (Manual)
1. Review deployment-scaler-role.yml manifest
2. Apply to apexalgo-iad cluster with cluster-admin credentials:
   ```bash
   kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
   ```
3. Notify workers that RBAC is applied (close bd-3o6 bead)

---

## Security Considerations

### Minimal Permissions
The deployment-scaler role grants **only** the permissions needed for scaling tests:
- No create/delete permissions
- No access to secrets or configmaps
- No cross-namespace access
- No cluster-wide permissions

### Scope Limitation
- **Namespace:** botburrow-agents only
- **Resources:** deployments/scale, HPAs, pods (read-only)
- **Verbs:** get, list, watch, patch, update (no create/delete)

### Alternative: Test-Runner ServiceAccount
If deployment-scaler permissions are insufficient, consider creating a dedicated test-runner ServiceAccount with broader permissions, isolated from devpod-observer.

---

## Troubleshooting

### Port-Forward Connection Refused
```bash
# Verify Valkey service exists
kubectl get svc -n botburrow-agents valkey

# Check Valkey pod is running
kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=valkey

# Test connection
kubectl port-forward -n botburrow-agents svc/valkey 6379:6379 &
redis-cli -h localhost -p 6379 PING
```

### RBAC Permission Denied
```bash
# Check if RoleBinding exists
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Check Role permissions
kubectl get role -n botburrow-agents deployment-scaler -o yaml

# Verify ServiceAccount exists
kubectl get sa -n devpod-observer devpod-observer
```

### Scaling Command Fails
```bash
# Check deployment exists
kubectl get deployment -n botburrow-agents

# Verify current replicas
kubectl get deployment runner-exploration -n botburrow-agents -o jsonpath='{.spec.replicas}'

# Check for HPA conflicts
kubectl get hpa -n botburrow-agents
# Note: HPA will override manual scaling - disable HPA first if testing manual scaling
```

---

## References

- **Original Issue:** bd-3qv (Test agent runner pool scaling)
- **Blocking Issue:** bd-3o6 (This document)
- **RBAC Manifest:** cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
- **CLAUDE.md:** Cross-cluster kubectl access documentation
