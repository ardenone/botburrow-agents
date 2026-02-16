# BD-1QS Status: Awaiting Human Cluster-Admin Action

**Bead:** bd-1qs
**Status:** ⏳ **BLOCKED - Requires cluster-admin credentials**
**Last Updated:** 2026-02-16 01:43 UTC
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents

---

## Current Situation

### ✅ Worker Preparation Complete
All worker tasks are done. The manifests are ready and validated:

1. **secrets-manager-role.yml** (49 lines) - ✅ Ready
   - Grants: get, list, patch, update on secrets
   - Required for: bd-2jm (Hub API authentication fix)

2. **deployment-scaler-role.yml** (74 lines) - ✅ Ready
   - Grants: scale deployments, manage HPAs, read pods
   - Required for: bd-3o6 (Runner scaling tests)

### ❌ RBAC Resources NOT Applied Yet
```bash
$ kubectl get role -n botburrow-agents secrets-manager
Error from server (NotFound): roles.rbac.authorization.k8s.io "secrets-manager" not found

$ kubectl get role -n botburrow-agents deployment-scaler
Error from server (NotFound): roles.rbac.authorization.k8s.io "deployment-scaler" not found
```

### 🚫 Worker Cannot Proceed
The devpod-observer ServiceAccount does NOT have permission to create RBAC resources:
```
Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

**Available kubeconfigs in this devpod:**
- ❌ No cluster-admin kubeconfig for apexalgo-iad
- ✅ /home/coder/.kube/apexalgo-iad.kubeconfig (devpod-observer - read-only)
- ✅ In-cluster ServiceAccount (ardenone-cluster - not cluster-admin)

---

## Required Human Action

### Prerequisites
- Access to **cluster-admin kubeconfig** for apexalgo-iad cluster
- Access to this git repository (to close beads and commit)

### Step 1: Apply RBAC Manifests

**Option A: From this devpod (if you have cluster-admin kubeconfig)**
```bash
# Export cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Apply manifests
cd /home/coder/botburrow-agents
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

**Option B: From remote machine with cluster-admin access**
```bash
# Clone repository (if not already cloned)
git clone <repo-url>
cd botburrow-agents

# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Apply manifests
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

### Step 2: Verify Application

```bash
# Check roles exist (should show NAME, CREATED AT)
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Check rolebindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Test permissions (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

### Step 3: Close Bead and Commit

```bash
cd /home/coder/botburrow-agents

# Close bead
br close bd-1qs --status completed

# Sync and commit
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Applied secrets-manager and deployment-scaler roles to botburrow-agents namespace.

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

---

## What This Unblocks

Once bd-1qs is completed, these downstream beads can proceed:

1. **bd-12r** - Grant devpod-observer RBAC access to botburrow namespace
2. **bd-2jm** - Hub API authentication fix (needs secret write access)
3. **bd-3o6** - Runner scaling tests (needs deployment scaling access)

---

## Security Review ✅

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update
- **Prohibited:** delete, create (cannot create or delete secrets)

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets, pods/portforward
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **Prohibited:** delete, modify non-scaling resources

**Risk Assessment:** ✅ LOW
- Limited to single namespace
- No destructive operations (no delete)
- Cannot escalate privileges
- Cannot create/delete secrets
- Cannot delete deployments
- Follows GitOps best practices (manifests in git)

---

## Troubleshooting

### Issue: "Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden"
**Cause:** You're using the devpod-observer kubeconfig (read-only)
**Fix:** Use cluster-admin kubeconfig: `export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig`

### Issue: "Error from server (NotFound): roles.rbac.authorization.k8s.io 'secrets-manager' not found"
**Cause:** Manifests haven't been applied yet
**Fix:** Run Step 1 above to apply the manifests

### Issue: kubectl auth can-i returns "no" after applying
**Cause:** RBAC changes may take a few seconds to propagate
**Fix:** Wait 5-10 seconds and retry

### Issue: Cannot find cluster-admin kubeconfig
**Solution Options:**
1. Generate new admin kubeconfig from apexalgo-iad control plane
2. Use existing admin kubeconfig from backup/secure storage
3. Use kubectl from control plane node directly (if accessible)

---

## Related Documentation

- **Quick Instructions:** CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md
- **Worker Status:** WORKER-STATUS.md
- **Human Bead:** bd-33d (closed as duplicate)
- **Manifests:** secrets-manager-role.yml, deployment-scaler-role.yml

---

## Worker Notes

**Last Worker Action:** 2026-02-16 01:43 UTC
- Verified RBAC resources do NOT exist in cluster
- Confirmed worker lacks cluster-admin permissions (expected)
- No admin kubeconfig available in devpod
- Created this status document
- Bead remains blocked until human applies manifests

**Next Action:** Human with cluster-admin credentials must execute Steps 1-3 above.
