# Duplicate Bead Resolution: bd-33d

## Summary
**bd-33d** has been closed as a duplicate of **bd-1qs**.

## Details

### Original Bead: bd-1qs (P0)
- **Title:** CLUSTER-ADMIN: Apply RBAC manifests for devpod-observer in botburrow-agents namespace
- **Status:** Open, awaiting cluster-admin action
- **Created:** First (original request)
- **Documentation:** Complete (CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md, WORKER-STATUS.md)

### Duplicate Bead: bd-33d (P1)
- **Title:** CLUSTER-ADMIN: Apply RBAC manifests to apexalgo-iad cluster
- **Status:** Closed (duplicate)
- **Created:** Later (duplicate request for same task)
- **Reason for duplicate:** bd-33d references bd-1qs in its description as "Original Bead"

## Why bd-33d Was Closed

Both beads requested the exact same action:
1. Apply `secrets-manager-role.yml` to apexalgo-iad cluster
2. Apply `deployment-scaler-role.yml` to apexalgo-iad cluster
3. Verify RBAC permissions work
4. Close the bead after completion

## Canonical Bead for This Task

**Use bd-1qs** for tracking this cluster-admin task.

## Next Steps

When you apply the RBAC manifests with cluster-admin credentials:

1. **Apply manifests:**
   ```bash
   kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
   kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
   ```

2. **Verify success:**
   ```bash
   kubectl get role -n botburrow-agents secrets-manager deployment-scaler
   kubectl auth can-i get secrets -n botburrow-agents \
     --as=system:serviceaccount:devpod-observer:devpod-observer
   ```

3. **Close bd-1qs (not bd-33d):**
   ```bash
   cd /home/coder/botburrow-agents
   br close bd-1qs
   br sync --flush-only
   git add .beads/*.jsonl
   git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

   Co-Authored-By: Cluster Admin <admin@ardenone.com>"
   git push origin main
   ```

## References
- Instructions: `CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md`
- Worker Status: `WORKER-STATUS.md`
- Manifests: `secrets-manager-role.yml`, `deployment-scaler-role.yml`
