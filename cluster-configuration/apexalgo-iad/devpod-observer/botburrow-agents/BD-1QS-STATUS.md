# BD-1QS Status: Ready for Cluster-Admin Execution

**Last Updated:** 2026-02-16
**Bead:** bd-1qs
**Type:** human
**Status:** IN_PROGRESS (awaiting cluster-admin)

## Summary

This bead requires a **human with cluster-admin credentials** for the apexalgo-iad cluster to apply RBAC manifests. All preparation work is complete.

## ✅ What's Ready

1. **Manifests Created and Committed**
   - `secrets-manager-role.yml` - Ready to apply
   - `deployment-scaler-role.yml` - Ready to apply
   - Both follow principle of least privilege

2. **Documentation Complete**
   - CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md (Step-by-step guide)
   - WORKER-STATUS.md (Worker verification results)
   - BD-1QS-STATUS.md (This file - current status)

3. **Verification Completed**
   - ✅ Target namespace exists: botburrow-agents
   - ✅ ServiceAccount exists: devpod-observer (in devpod-observer namespace)
   - ✅ RBAC resources do NOT exist yet (confirmed 2026-02-16)
   - ✅ Worker lacks permission to create RBAC (as expected)

## ❌ What's Blocking

**NO cluster-admin credentials available in devpod environment**

Available kubeconfigs:
- `/home/coder/.kube/apexalgo-iad.kubeconfig` - devpod-observer ServiceAccount (read-only)
- `/home/coder/.kube/config` - ardenone-cluster in-cluster ServiceAccount

Neither has permission to create RBAC resources in apexalgo-iad cluster.

## 🔧 Required Action

### For Human with Cluster-Admin Access

**Step 1: Apply the manifests**

```bash
# On machine with cluster-admin kubeconfig for apexalgo-iad
cd /home/coder/botburrow-agents

# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-cluster-admin.kubeconfig

# Apply both manifests
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

**Expected output:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
role.rbac.authorization.k8s.io/deployment-scaler created
rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created
```

**Step 2: Verify permissions work**

```bash
# Should show both roles exist
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Should show both bindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Should return "yes" (permission granted)
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

**Step 3: Close the bead**

```bash
# From devpod workspace
cd /home/coder/botburrow-agents
br close bd-1qs --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Applied secrets-manager and deployment-scaler roles to apexalgo-iad cluster
for devpod-observer ServiceAccount in botburrow-agents namespace.

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

## 🔓 What This Unblocks

Once RBAC is applied, these downstream beads can proceed:

- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## 🔒 Security Review

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update (NO delete, NO create)
- **Purpose:** Update existing secrets for configuration management

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **Purpose:** Scale deployments and manage autoscaling for testing
- **Limitation:** NO permission to delete or modify other resources

## 📋 Verification Checklist

Before closing bd-1qs, verify:

- [ ] Both Role resources created in botburrow-agents namespace
- [ ] Both RoleBinding resources created in botburrow-agents namespace
- [ ] `kubectl auth can-i get secrets` returns "yes"
- [ ] `kubectl auth can-i patch deployments/scale` returns "yes"
- [ ] Git commit pushed to GitHub
- [ ] Bead bd-1qs closed with status completed

## Alternative Approaches Considered

### ❌ Option 2: Grant devpod-observer permission to create RBAC
**Rejected** - Violates least privilege principle, enables privilege escalation attacks

### ❌ Option 3: Use ArgoCD to apply manifests
**Not immediate** - Requires ArgoCD application setup, adds complexity for one-time action

### ✅ Option 1: Manual application with cluster-admin (CURRENT APPROACH)
**Recommended** - Immediate resolution, minimal security risk, clear audit trail

## Next Steps

1. Human with cluster-admin access executes Step 1-3 above
2. Bead bd-1qs marked as completed
3. Downstream beads (bd-12r, bd-2jm, bd-3o6) automatically unblocked
4. Workers can proceed with RBAC-dependent tasks

**Status:** Awaiting cluster-admin action
