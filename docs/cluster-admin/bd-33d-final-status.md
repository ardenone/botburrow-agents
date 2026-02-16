# Bead bd-33d: CLUSTER-ADMIN RBAC Application - Final Status

## Summary
✅ **All preparation complete** - Ready for cluster-admin to apply RBAC manifests

**Date:** 2026-02-16
**Worker:** Claude Code Worker
**Bead:** bd-33d (human bead for cluster-admin action)
**Related Worker Bead:** bd-1qs (worker prepared manifests, now awaiting application)

---

## What Needs to Be Done

You (the human with cluster-admin access) need to apply two RBAC manifest files to the `apexalgo-iad` cluster.

### Quick Commands

```bash
# Navigate to workspace
cd /home/coder/botburrow-agents

# Apply both manifests
export KUBECONFIG=<path-to-cluster-admin-kubeconfig>
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

### Verify Success

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

### Close Beads After Success

```bash
cd /home/coder/botburrow-agents

# Close both the worker bead and this human bead
br close bd-1qs --status completed
br close bd-33d --status completed
br sync --flush-only

# Commit the completion
git add .beads/*.jsonl
git commit -m "chore(bd-1qs,bd-33d): cluster-admin applied RBAC manifests

Applied secrets-manager and deployment-scaler roles to botburrow-agents namespace.
This unblocks bd-12r, bd-2jm, and bd-3o6.

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

---

## Why This Is Needed

The `devpod-observer` ServiceAccount (used by workers in devpods) does NOT have permission to create RBAC resources:

```
Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

This is correct security posture - RBAC creation should require cluster-admin privileges.

---

## What This Unblocks

Once these RBAC manifests are applied, the following beads can proceed:

1. **bd-12r** - Parent bead requesting RBAC access
2. **bd-2jm** - Hub API authentication fix (needs secret write access)
3. **bd-3o6** - Runner scaling tests (needs deployment scaling access)

---

## Security Review ✅

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update
- **NOT allowed:** delete, create
- **Purpose:** Allow workers to update configuration secrets (e.g., API tokens)

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments (read-only), HPAs, pods (read-only), replicasets (read-only)
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **NOT allowed:** delete
- **Purpose:** Allow workers to scale deployments for testing and enable port-forwarding

---

## Manifest Files

### 1. secrets-manager-role.yml

**Path:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`

**Contents:**
- Role: `secrets-manager` (namespace: botburrow-agents)
- RoleBinding: `devpod-observer-secrets-manager`
- Subject: `system:serviceaccount:devpod-observer:devpod-observer`

**Permissions:**
- Secrets: get, list, patch, update

### 2. deployment-scaler-role.yml

**Path:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml`

**Contents:**
- Role: `deployment-scaler` (namespace: botburrow-agents)
- RoleBinding: `devpod-observer-scaler`
- Subject: `system:serviceaccount:devpod-observer:devpod-observer`

**Permissions:**
- deployments/scale: get, patch, update
- deployments: get, list, watch (read-only)
- horizontalpodautoscalers: get, list, watch, patch, update
- pods: get, list, watch (read-only)
- pods/portforward: create, get
- replicasets: get, list, watch (read-only)

---

## Alternative Approaches (NOT RECOMMENDED)

### Option 2: Grant devpod-observer permission to create RBAC
❌ **Not recommended** - violates least privilege, enables privilege escalation

### Option 3: Use ArgoCD
⚠️ **Not immediate** - requires ArgoCD application setup for this directory

**Option 1 (manual application via cluster-admin) is recommended** for immediate resolution with minimal security risk.

---

## Worker Actions Completed ✅

1. ✅ Created both RBAC manifest files
2. ✅ Verified manifests follow least-privilege principles
3. ✅ Committed manifests to git
4. ✅ Created CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md
5. ✅ Created WORKER-STATUS.md for bd-1qs
6. ✅ Verified worker lacks RBAC creation permissions
7. ✅ Created this final status document for bd-33d
8. ✅ All documentation committed and pushed

---

## Next Action Required

**Human with cluster-admin access to apexalgo-iad must:**
1. Apply the two manifest files (commands above)
2. Verify success (verification commands above)
3. Close both beads and commit (closure commands above)

---

## Questions or Issues?

If you encounter any problems:

1. **Manifests fail to apply:** Check that the botburrow-agents namespace exists
   ```bash
   kubectl get namespace botburrow-agents
   ```

2. **Verification fails:** Check that devpod-observer ServiceAccount exists
   ```bash
   kubectl get serviceaccount -n devpod-observer devpod-observer
   ```

3. **Permission still denied:** Verify you're using cluster-admin kubeconfig
   ```bash
   kubectl auth can-i create roles -n botburrow-agents
   # Should return: yes
   ```

---

## Reference Documents

- **Application Instructions:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md`
- **Worker Status:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/WORKER-STATUS.md`
- **This Status:** `docs/cluster-admin/bd-33d-final-status.md`
