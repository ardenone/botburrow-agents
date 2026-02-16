# HUMAN ACTION REQUIRED: Apply RBAC Manifests

**Bead:** bd-1qs
**Status:** Ready for cluster-admin execution
**Date:** 2026-02-16
**Cluster:** apexalgo-iad

## Summary

This bead requires a **human with cluster-admin credentials** for the apexalgo-iad cluster to apply RBAC manifests. All preparation work is complete - only the final application step requires elevated privileges.

## Why Human Intervention Required

The devpod-observer ServiceAccount (used by Claude Code workers) correctly **does NOT have cluster-admin access**. This is proper security design. Creating RBAC resources (Roles/RoleBindings) requires cluster-admin privileges.

## What's Ready ✅

1. **Manifests validated and committed:**
   - `secrets-manager-role.yml` (48 lines)
   - `deployment-scaler-role.yml` (73 lines)

2. **Documentation complete:**
   - CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md
   - WORKER-STATUS.md
   - This file (HUMAN-ACTION-REQUIRED.md)

3. **Prerequisites verified:**
   - Target namespace `botburrow-agents` exists
   - ServiceAccount `devpod-observer` exists in `devpod-observer` namespace
   - RBAC resources do NOT exist yet (verified NotFound)

## Instructions for Human

### Step 1: Obtain cluster-admin kubeconfig

You need a kubeconfig with cluster-admin access to the **apexalgo-iad** cluster.

### Step 2: Apply the manifests

```bash
# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Navigate to repository
cd /home/coder/botburrow-agents

# Apply both manifests
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

### Step 3: Verify the RBAC was applied

```bash
# Check roles exist
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Check rolebindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Verify permissions (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

### Step 4: Close the bead

```bash
cd /home/coder/botburrow-agents
br close bd-1qs --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Applied secrets-manager-role and deployment-scaler-role to apexalgo-iad cluster.
DevPod-observer ServiceAccount now has minimal RBAC permissions in botburrow-agents namespace.

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

## What This Unblocks 🔓

Once applied, workers can proceed with:

- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## Security Review ✅

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update
- **NO permission to:** delete secrets, create secrets, access other resources

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **NO permission to:** delete deployments, modify other resources

## Alternative: Use kubectl-proxy with admin credentials

If you have SSH access to a machine with admin credentials for apexalgo-iad:

```bash
# On machine with admin access
ssh admin@apexalgo-iad-admin-host

# Apply manifests
cd /path/to/botburrow-agents
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

## Questions?

See the detailed instructions in:
- `CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md` - Complete step-by-step guide
- `WORKER-STATUS.md` - Current verification status

---

**Status:** READY FOR HUMAN CLUSTER-ADMIN ACTION
**Last Updated:** 2026-02-16
**Worker:** Claude Code Agent (verified all prerequisites)
