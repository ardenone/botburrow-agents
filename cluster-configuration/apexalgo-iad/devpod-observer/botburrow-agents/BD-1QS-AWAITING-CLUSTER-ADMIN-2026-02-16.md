# BD-1QS: Awaiting Cluster-Admin Action

**Date:** 2026-02-16
**Bead:** bd-1qs
**Status:** ⏳ AWAITING CLUSTER-ADMIN
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents

## Summary

This bead **CANNOT be completed by workers** because it requires **cluster-admin credentials** to apply RBAC manifests. All worker tasks are complete.

## Verification Status (2026-02-16)

### ✅ Worker Tasks Complete
- [x] RBAC manifests exist: `secrets-manager-role.yml`, `deployment-scaler-role.yml`
- [x] Manifests committed to git
- [x] Documentation complete (CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md, WORKER-STATUS.md)
- [x] Worker verification complete
- [x] Human bead bd-33d created (marked duplicate, closed)

### ❌ Cluster-Admin Tasks Required
- [ ] RBAC roles NOT applied yet (confirmed NotFound)
- [ ] Worker lacks permission to create roles (kubectl auth can-i: no)
- [ ] Requires human with cluster-admin kubeconfig for apexalgo-iad

## What Cluster-Admin Must Do

### Step 1: Apply RBAC Manifests

```bash
# Set cluster-admin kubeconfig for apexalgo-iad
export KUBECONFIG=/path/to/apexalgo-iad-cluster-admin.kubeconfig

# Apply manifests
cd /home/coder/botburrow-agents
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

### Step 2: Verify RBAC Applied

```bash
# Should show both roles exist
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Should show both bindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Should return "yes"
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

### Step 3: Close Bead

```bash
cd /home/coder/botburrow-agents
br close bd-1qs --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

## Quick Reference

📄 **Full Instructions:** cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md
📄 **Worker Status:** cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/WORKER-STATUS.md
📄 **BD-33D Guide:** cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/BD-33D-COMPLETION-GUIDE.md

## What This Unblocks

Once RBAC is applied, these beads can proceed:
- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## Security Review ✅

Both roles follow **principle of least privilege**:

**secrets-manager:**
- Scope: botburrow-agents namespace only
- Resources: secrets only
- Verbs: get, list, patch, update (NO delete, NO create)

**deployment-scaler:**
- Scope: botburrow-agents namespace only
- Resources: deployments/scale, deployments, HPAs, pods, replicasets
- Verbs: get, list, watch, patch, update, create (portforward only)
- NO permission to delete or modify other resources

## Worker Conclusion

**Workers cannot proceed.** This bead requires human cluster-admin action.

**Next Action:** Human with cluster-admin kubeconfig for apexalgo-iad must execute Step 1-3 above.
