# CLUSTER-ADMIN: Apply RBAC for devpod-observer in botburrow-agents

## Quick Reference

**Bead:** bd-1qs
**Status:** Awaiting cluster-admin action
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents

## Why Manual Application Required

The `devpod-observer` ServiceAccount in apexalgo-iad cluster does NOT have permission to create RBAC resources:

```
Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

## Manifests to Apply

Both manifests are in this directory:

1. **secrets-manager-role.yml** - Grants get/list/patch/update permissions on secrets
   - Required for: bd-2jm (Hub API authentication fix)

2. **deployment-scaler-role.yml** - Grants deployment scaling and HPA management
   - Required for: bd-3o6 (Runner scaling tests)

## Instructions

### Step 1: Apply the manifests with cluster-admin kubeconfig

```bash
# On machine with cluster-admin access to apexalgo-iad
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

### Step 2: Verify RBAC was applied

```bash
# Check Roles exist
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Check RoleBindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Test permissions (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

### Step 3: Notify completion

After applying, close bead bd-1qs:

```bash
# From devpod workspace
cd /home/coder/botburrow-agents
br close bd-1qs --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

## What This Unblocks

Once applied, these downstream beads can proceed:

- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## Security Review

Both roles follow **principle of least privilege**:

### secrets-manager
- Scope: botburrow-agents namespace only
- Resources: secrets only
- Verbs: get, list, patch, update (NO delete, NO create)

### deployment-scaler
- Scope: botburrow-agents namespace only
- Resources: deployments/scale, deployments, HPAs, pods, replicasets
- Verbs: get, list, watch, patch, update, create (portforward only)
- NO permission to delete or modify other resources

## Alternative Approaches (NOT RECOMMENDED)

### Option 2: Grant devpod-observer permission to create RBAC
❌ **Not recommended** - violates least privilege, enables privilege escalation

### Option 3: Use ArgoCD
⚠️ **Not immediate** - requires ArgoCD application setup for this directory

**Option 1 (manual application) is recommended** for immediate resolution with minimal security risk.
