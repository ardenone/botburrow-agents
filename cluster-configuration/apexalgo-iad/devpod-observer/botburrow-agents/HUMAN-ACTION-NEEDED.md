# HUMAN ACTION NEEDED: Apply RBAC to apexalgo-iad

**Bead:** bd-1qs
**Date:** 2026-02-16
**Status:** ⏳ Awaiting cluster-admin action

## Summary

The devpod workers have prepared RBAC manifests for the apexalgo-iad cluster but cannot apply them due to lack of cluster-admin permissions (intentional security boundary). A human with cluster-admin credentials for apexalgo-iad must apply these manifests.

## What's Ready

✅ **Manifests validated and committed:**
- `secrets-manager-role.yml` - Grants secrets access for Hub API fix (bd-2jm)
- `deployment-scaler-role.yml` - Grants deployment scaling for runner tests (bd-3o6)

✅ **Documentation complete:**
- `CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md` - Detailed step-by-step guide

✅ **Verification complete:**
- Confirmed RBAC resources do NOT exist in cluster yet (NotFound)
- Confirmed devpod lacks cluster-admin access (correct)

## Quick Apply (for cluster admin)

### Prerequisites
- Physical access to cluster-admin kubeconfig for apexalgo-iad
- kubectl CLI installed

### Commands

```bash
# 1. Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Navigate to manifest directory
cd /path/to/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# 3. Apply manifests
kubectl apply -f secrets-manager-role.yml
kubectl apply -f deployment-scaler-role.yml

# 4. Verify RBAC was created
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# 5. Test permissions (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

# 6. Close bead (from devpod)
br close bd-1qs --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Co-Authored-By: [Your Name] <[your-email]>"
git push origin main
```

## What This Unblocks

Once applied, these beads can proceed:
- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write)
- **bd-3o6** - Runner scaling tests (needs deployment scaling)

## Security Notes

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update (NO delete, NO create)

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **NO** delete or modify permissions on other resources

## Why Manual Application?

The devpod-observer ServiceAccount intentionally lacks cluster-admin permissions to prevent privilege escalation. This is a **correct security boundary**.

## Need Help?

See detailed instructions: `CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md`
