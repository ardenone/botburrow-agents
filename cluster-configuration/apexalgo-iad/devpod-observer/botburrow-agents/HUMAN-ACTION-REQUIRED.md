# 🚨 HUMAN ACTION REQUIRED - Apply RBAC Manifests

**Beads:** bd-1qs (worker bead), bd-33d (human bead)
**Priority:** HIGH (blocks bd-2jm and bd-3o6)
**Required Role:** cluster-admin access to apexalgo-iad cluster
**Estimated Time:** 2-5 minutes

## TL;DR - What You Need to Do

Apply two RBAC manifest files to grant devpod-observer ServiceAccount permissions in the `botburrow-agents` namespace.

## Quick Start (Copy-Paste)

```bash
# Set your cluster-admin kubeconfig for apexalgo-iad
export KUBECONFIG=/path/to/apexalgo-iad-cluster-admin.kubeconfig

# Navigate to manifests directory
cd /home/coder/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# Apply both manifests
kubectl apply -f secrets-manager-role.yml
kubectl apply -f deployment-scaler-role.yml

# Verify (should all return "yes")
kubectl auth can-i get secrets -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
kubectl auth can-i patch secrets -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
kubectl auth can-i patch deployments/scale -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
```

## Why This Is Needed

Workers cannot create RBAC resources (Roles/RoleBindings) because the devpod-observer ServiceAccount lacks cluster-level permissions. This is by design for security.

**Blocked Work:**
- ❌ bd-2jm - Hub API authentication fix (needs secret write access)
- ❌ bd-3o6 - Runner scaling tests (needs deployment scaling access)

## What These Manifests Grant

### secrets-manager-role.yml
✅ Read and update secrets in `botburrow-agents` namespace
✅ **NO** secret creation or deletion
✅ Scoped to single namespace only

### deployment-scaler-role.yml
✅ Scale deployments (testing purposes)
✅ Read pods, deployments, replicasets
✅ Manage HorizontalPodAutoscalers
✅ Port-forward to pods (Valkey access)
✅ **NO** deployment creation or deletion

## Security Review

**Safe to apply?** ✅ YES

- ✅ Least privilege - minimal permissions only
- ✅ Namespace-scoped (not cluster-wide)
- ✅ No resource creation/deletion
- ✅ No RBAC escalation risk
- ✅ Manifests tracked in Git
- ✅ Labeled with bead IDs for audit trail

## Expected Output

```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
role.rbac.authorization.k8s.io/deployment-scaler created
rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created
```

## Verification Commands

```bash
# Check roles were created
kubectl get role -n botburrow-agents secrets-manager deployment-scaler

# Check bindings were created
kubectl get rolebinding -n botburrow-agents

# Test permissions
kubectl auth can-i get secrets -n botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
# Should return: yes
```

## After You Apply

Close the beads to mark this work complete:

```bash
# From botburrow-agents repository
cd /home/coder/botburrow-agents

# Close both beads
br close bd-1qs --status completed
br close bd-33d --status completed

# Sync and commit
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs,bd-33d): cluster-admin applied RBAC manifests

Applied RBAC roles for devpod-observer in botburrow-agents namespace:
- secrets-manager (get/list/patch/update secrets)
- deployment-scaler (scale deployments, manage HPAs)

Unblocks: bd-12r, bd-2jm, bd-3o6

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

Workers will automatically resume blocked beads (bd-2jm, bd-3o6) once permissions are verified.

## Need Help?

See detailed instructions: `CLUSTER-ADMIN-INSTRUCTIONS.md` in this directory
