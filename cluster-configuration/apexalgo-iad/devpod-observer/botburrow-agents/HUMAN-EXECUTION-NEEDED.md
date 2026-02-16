# HUMAN EXECUTION REQUIRED: Apply RBAC Manifests

**Bead:** bd-1qs
**Date:** 2026-02-16
**Status:** ✅ Ready for human execution

## TL;DR - What You Need To Do

Apply two RBAC manifests to **apexalgo-iad cluster** using **cluster-admin credentials**:

```bash
# Set your cluster-admin kubeconfig for apexalgo-iad
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Navigate to botburrow-agents repo
cd /path/to/botburrow-agents

# Apply the manifests
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml

# Verify (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

## Why Manual Application Is Required

The devpod's `devpod-observer` ServiceAccount **intentionally lacks** permission to create RBAC resources (following security best practices). Only a human with cluster-admin credentials can apply these manifests.

**Error when worker attempted to apply:**
```
Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

## What These Manifests Do

### 1. secrets-manager-role.yml
- **Purpose:** Allow devpod-observer to read/update secrets in botburrow-agents namespace
- **Permissions:** get, list, patch, update (NO delete, NO create)
- **Unblocks:** bd-2jm (Hub API authentication fix)

### 2. deployment-scaler-role.yml
- **Purpose:** Allow devpod-observer to scale deployments for testing
- **Permissions:** Scale deployments, manage HPAs, read pods/replicasets
- **Unblocks:** bd-3o6 (Runner scaling tests)

Both roles follow **principle of least privilege** and are scoped to the `botburrow-agents` namespace only.

## Security Review ✅

**Verified by workers:**
- ✅ Manifests follow least-privilege principles
- ✅ No delete permissions granted
- ✅ Scoped to single namespace (botburrow-agents)
- ✅ ServiceAccount is in separate namespace (devpod-observer)
- ✅ No cluster-wide permissions

## After Applying

Once you've successfully applied the manifests and verified permissions, close the bead:

```bash
# From the devpod (or via br CLI)
cd /home/coder/botburrow-agents
br close bd-1qs --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Applied secrets-manager-role.yml and deployment-scaler-role.yml
to apexalgo-iad cluster with cluster-admin credentials.

Unblocks: bd-12r, bd-2jm, bd-3o6

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

## Downstream Impact

Completing this task unblocks:
- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## Files Ready for Application

Both manifests are committed and ready:
- `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml` (48 lines)
- `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml` (73 lines)

## Questions?

See detailed documentation:
- `CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md` - Full step-by-step guide
- `WORKER-STATUS.md` - Worker verification results

---

**Status:** READY FOR HUMAN EXECUTION
**Next Action:** Apply manifests with cluster-admin kubeconfig
