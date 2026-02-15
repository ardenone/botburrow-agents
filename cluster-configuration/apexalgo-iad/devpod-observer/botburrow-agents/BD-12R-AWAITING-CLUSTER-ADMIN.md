# bd-12r: RBAC Grant Status - Awaiting Cluster-Admin

**Date:** 2026-02-15
**Bead:** bd-12r
**Status:** ⏸️ BLOCKED - Awaiting cluster-admin intervention
**Human Bead:** bd-1qs

## Summary

The RBAC manifests to grant devpod-observer ServiceAccount access to the botburrow-agents namespace have been **created and committed** but **cannot be applied** by the worker due to insufficient permissions. The devpod-observer ServiceAccount does not have permission to create RBAC resources (Roles/RoleBindings).

## Current Status

✅ **Completed:**
- RBAC manifests created: `secrets-manager-role.yml` and `deployment-scaler-role.yml`
- Manifests follow least-privilege principles
- Manifests committed to Git repository

❌ **Blocked:**
- Cannot apply manifests due to RBAC permission error
- Requires cluster-admin access to apexalgo-iad cluster

## Error Encountered

```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl apply -f secrets-manager-role.yml

Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

## Human Intervention Required

**Human Bead Created:** bd-1qs
**Title:** CLUSTER-ADMIN: Apply RBAC manifests for devpod-observer in botburrow-agents namespace
**Priority:** P0 (Critical)

**Action Needed:** A human with cluster-admin access to apexalgo-iad cluster must apply the RBAC manifests manually.

## Manifests Ready to Apply

### 1. secrets-manager-role.yml
**Purpose:** Grant devpod-observer permission to manage secrets in botburrow-agents namespace
**Required for:** bd-2jm (Hub API authentication fix)
**Permissions:**
- `get`, `list`, `patch`, `update` on secrets

### 2. deployment-scaler-role.yml
**Purpose:** Grant devpod-observer permission to scale deployments and manage HPAs
**Required for:** bd-3o6 (Runner scaling tests)
**Permissions:**
- `get`, `patch`, `update` on deployments/scale
- `get`, `list`, `watch` on deployments, pods, replicasets
- `get`, `list`, `watch`, `patch`, `update` on horizontalpodautoscalers
- `create`, `get` on pods/portforward

## Application Instructions (for cluster-admin)

```bash
# Apply RBAC manifests to apexalgo-iad cluster
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml

# Verify RBAC permissions are granted
kubectl auth can-i get secrets -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected output: yes

kubectl auth can-i patch secrets -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected output: yes

kubectl auth can-i patch deployments -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected output: yes
```

## Verification Commands (for worker after application)

```bash
# From devpod (worker context)
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Test secret access (should succeed after RBAC applied)
kubectl get secret -n botburrow-agents botburrow-agents-secrets

# Verify can-i permissions
kubectl auth can-i get secrets -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
kubectl auth can-i patch secrets -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
kubectl auth can-i patch deployments -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
```

## Dependencies

**This bead blocks:**
- bd-2jm - Hub API authentication fix (needs secret write access)
- bd-3o6 - Runner scaling tests (needs deployment scaling access)

**This bead depends on:**
- bd-1qs - Human cluster-admin application of RBAC manifests

## Related Files

- **RBAC Manifests:**
  - `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`
  - `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml`

- **Documentation:**
  - `cluster-configuration/apexalgo-iad/devpod-observer/KUBECTL-PROXY-RESOLUTION-2026-02-15.md`
  - `/home/coder/.claude/CLAUDE.md` (cross-cluster kubectl access section)

## Next Steps

1. ✅ Worker has created human bead bd-1qs requesting cluster-admin intervention
2. ⏳ Human with cluster-admin access applies RBAC manifests to apexalgo-iad
3. ⏳ Human responds to bd-1qs confirming manifests are applied
4. ⏳ bd-12r automatically unblocked when bd-1qs is resolved
5. ⏳ Worker verifies RBAC access and closes bd-12r
6. ⏳ Blocked beads (bd-2jm, bd-3o6) can proceed

## Timeline

- **22:46 UTC:** RBAC manifests creation attempted
- **22:46 UTC:** Permission denied - devpod-observer cannot create RBAC resources
- **22:46 UTC:** Human bead bd-1qs created for cluster-admin intervention
- **22:47 UTC:** Dependency added: bd-12r depends on bd-1qs
- **22:48 UTC:** Status documentation created
- **⏳ Awaiting:** Human cluster-admin application of manifests

## Security Considerations

- **Least Privilege:** Manifests grant minimal permissions required for specific tasks
- **Namespace Scoped:** All permissions are limited to botburrow-agents namespace only
- **Auditable:** All RBAC changes are tracked in Git with bead references
- **No Privilege Escalation:** devpod-observer cannot modify its own RBAC permissions
