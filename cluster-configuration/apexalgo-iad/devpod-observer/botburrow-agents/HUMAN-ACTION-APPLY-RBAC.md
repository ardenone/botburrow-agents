# 🚨 HUMAN ACTION REQUIRED: Apply Deployment-Scaler RBAC

**Bead:** bd-3o6 - Enable write permissions for runner scaling tests
**Status:** Waiting for cluster-admin to apply RBAC manifest
**Date Created:** 2026-02-15

---

## What Needs to Be Done

Apply the deployment-scaler RBAC manifest to the **apexalgo-iad** cluster to grant the devpod-observer ServiceAccount permission to scale deployments in the botburrow-agents namespace.

## Why This Is Needed

- **Current State:** devpod-observer has read-only access
- **Problem:** Cannot test runner pool scaling behavior (bd-3qv)
- **Solution:** Grant minimal scaling permissions via RBAC
- **Scope:** botburrow-agents namespace only
- **Permissions:** deployment/scale, HPA management (read + patch)

---

## Quick Apply (Recommended)

### Prerequisites
- Cluster-admin access to apexalgo-iad cluster
- kubectl configured with admin context

### Commands

```bash
# Clone or navigate to botburrow-agents repository
cd /path/to/botburrow-agents

# Apply the RBAC manifest
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml

# Verify role was created
kubectl get role -n botburrow-agents deployment-scaler

# Verify rolebinding was created
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler
```

### Expected Output

```
role.rbac.authorization.k8s.io/deployment-scaler created
rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created
```

---

## Verification

After applying, verify the permissions work from devpod:

```bash
# From devpod with apexalgo-iad kubeconfig
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Test scaling permission (scale to current replica count - no-op)
kubectl scale deployment runner-exploration -n botburrow-agents --replicas=1

# Should succeed with output:
# deployment.apps/runner-exploration scaled
```

---

## What This Grants

The deployment-scaler role grants these permissions **in botburrow-agents namespace only**:

### Write Permissions (Scaling & Testing)
- `deployments/scale` → patch, update
- `horizontalpodautoscalers` → patch, update
- `pods/portforward` → create, get (for kubectl port-forward to Valkey)

### Read Permissions (Verification)
- `deployments` → get, list, watch
- `horizontalpodautoscalers` → get, list, watch
- `pods` → get, list, watch
- `replicasets` → get, list, watch

### What This Does NOT Grant
- ❌ Create/delete deployments
- ❌ Create/delete pods
- ❌ Access to secrets or configmaps
- ❌ Cross-namespace access
- ❌ Cluster-wide permissions

---

## Security Review

### Minimal Scope
- **Namespace:** botburrow-agents only
- **Subject:** devpod-observer ServiceAccount only
- **Verbs:** No create/delete permissions
- **Resources:** Only scaling-related operations

### Risk Assessment
- **Risk Level:** Low
- **Blast Radius:** Limited to botburrow-agents namespace
- **Reversibility:** Can be removed with `kubectl delete -f deployment-scaler-role.yml`

### Recommended Action
✅ **APPROVE** - Minimal permissions for testing purposes

---

## Alternative: Manual Application

If you prefer to review the manifest first:

```bash
# View the manifest
cat cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml

# Copy/paste into Kubernetes dashboard or kubectl
# Then apply manually
```

---

## Post-Application Actions

### 1. Notify Workers
Once applied, update bead bd-3o6:

```bash
cd /home/coder/botburrow-agents
br update bd-3o6 --add-label rbac-applied
br close bd-3o6 --status completed
```

### 2. Unblock bd-3qv
The scaling tests can now proceed:

```bash
br dep remove bd-3qv --depends-on bd-3o6
```

---

## Troubleshooting

### Error: "forbidden: User cannot create resource"
- Cause: Not using cluster-admin context
- Fix: Switch to admin kubeconfig for apexalgo-iad

### Error: "namespaces 'botburrow-agents' not found"
- Cause: Wrong cluster context
- Fix: Verify you're targeting apexalgo-iad cluster

### Verification Fails: "forbidden: cannot scale deployment"
- Cause: RoleBinding subject mismatch
- Fix: Verify devpod-observer ServiceAccount exists in devpod-observer namespace:
  ```bash
  kubectl get sa -n devpod-observer devpod-observer
  ```

---

## Rollback

If you need to remove these permissions:

```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

---

## Questions?

- **Manifest Location:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml`
- **Full Guide:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/SCALING-TESTS-GUIDE.md`
- **Related Bead:** bd-3qv (Test agent runner pool scaling)

---

**Status:** ⏳ Waiting for human to apply manifest
