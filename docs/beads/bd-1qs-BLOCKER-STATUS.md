# BD-1QS: BLOCKER STATUS - Cluster-Admin Credentials Required

**Bead ID:** bd-1qs
**Status:** ❌ BLOCKED - Requires cluster-admin credentials
**Date:** 2026-02-16
**Worker:** Claude Code Worker

## Current Situation

This bead **cannot be completed by a worker** with devpod-observer credentials. Cluster-admin access to apexalgo-iad cluster is required.

### What Was Attempted

1. ✅ Verified manifests exist and are valid
   - `secrets-manager-role.yml` (49 lines)
   - `deployment-scaler-role.yml` (74 lines)

2. ✅ Verified RBAC resources do NOT exist in cluster:
   ```bash
   $ kubectl get role -n botburrow-agents secrets-manager
   Error from server (NotFound): roles.rbac.authorization.k8s.io "secrets-manager" not found

   $ kubectl get role -n botburrow-agents deployment-scaler
   Error from server (NotFound): roles.rbac.authorization.k8s.io "deployment-scaler" not found
   ```

3. ❌ Attempted to apply manifests with devpod-observer credentials:
   ```bash
   $ kubectl apply -f secrets-manager-role.yml
   Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
   User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
   in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
   ```

### Why This Blocker Exists

**Security by Design:** The devpod-observer ServiceAccount intentionally does NOT have permission to create RBAC resources. This prevents privilege escalation and follows the principle of least privilege.

### Available Kubeconfigs

Worker only has access to:
- `/home/coder/.kube/apexalgo-iad.kubeconfig` - devpod-observer ServiceAccount (read-only)
- Default in-cluster ServiceAccount - ardenone-cluster (not apexalgo-iad)

**No cluster-admin kubeconfig is available in this environment.**

## Resolution Options

### Option 1: Human with Cluster-Admin Access (REQUIRED)

A human with cluster-admin credentials for apexalgo-iad must:

```bash
# On machine with cluster-admin kubeconfig
cd /home/coder/botburrow-agents
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Apply manifests
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml

# Verify success
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

# Close bead
cd /home/coder/botburrow-agents
br close bd-1qs --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

### Option 2: Mount Cluster-Admin Kubeconfig (Alternative)

If cluster-admin kubeconfig can be mounted into the devpod environment:

```bash
# Copy cluster-admin kubeconfig to devpod
# Then worker can apply manifests
```

⚠️ **Security Risk:** Mounting cluster-admin credentials into devpod increases attack surface. Option 1 is recommended.

## Downstream Impact

These beads are **blocked** waiting for bd-1qs:
- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## Documentation References

- **Complete Instructions:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md`
- **Worker Verification:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/WORKER-STATUS.md`
- **Human Bead (closed as duplicate):** bd-33d

## Worker Conclusion

**Worker cannot proceed.** This bead remains open until a human with cluster-admin access to apexalgo-iad applies the RBAC manifests.

**Next Action:** Human intervention required.
