# BD-33D: Human Action Required - RBAC Application Status

## Summary
🚨 **AWAITING HUMAN WITH CLUSTER-ADMIN ACCESS**

This bead (bd-33d) is a **human-action bead** that requires cluster-admin credentials for the apexalgo-iad cluster. Automated workers cannot complete this task.

## What Workers Have Verified (2026-02-15)

### ✅ All Preparations Complete
1. **Manifest files ready:**
   - `secrets-manager-role.yml` - exists and committed
   - `deployment-scaler-role.yml` - exists and committed

2. **Documentation ready:**
   - `CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md` - step-by-step guide
   - `WORKER-STATUS.md` - worker verification status

3. **RBAC status confirmed:**
   - Both roles do NOT exist in cluster (expected)
   - Worker has devpod-observer access only (read-only)
   - Worker CANNOT create RBAC resources (requires cluster-admin)

### ❌ Blocker: No Cluster-Admin Access
```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl auth can-i create roles -n botburrow-agents
no
```

## What Human Must Do

### Prerequisites
- Cluster-admin kubeconfig for apexalgo-iad cluster
- Access to this repository: `/home/coder/botburrow-agents`

### Step 1: Apply Manifests
```bash
# From repository root
cd /home/coder/botburrow-agents

# Apply RBAC manifests with cluster-admin kubeconfig
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

### Step 2: Verify Application Success
```bash
# Check roles exist
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Check bindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Verify permissions (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

### Step 3: Close Beads
```bash
# Close the worker bead (bd-1qs)
br close bd-1qs --status completed

# Close this human-action bead (bd-33d)
br close bd-33d --status completed

# Sync and commit
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs,bd-33d): cluster-admin applied RBAC manifests

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

## What This Unblocks

Once RBAC is applied, these beads can proceed:
- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## Security Review ✅

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update (NO delete, NO create)

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **NO permission** to delete or modify other resources

## Alternative Approaches (Not Recommended)

### Option 2: Grant devpod-observer RBAC creation permission
❌ **Not recommended** - violates least privilege, enables privilege escalation

### Option 3: Use ArgoCD
⚠️ **Not immediate** - requires ArgoCD application setup

**Option 1 (manual application) is recommended** for immediate resolution.

## Related Files
- **Instructions:** CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md
- **Worker Status:** WORKER-STATUS.md
- **Manifest 1:** secrets-manager-role.yml
- **Manifest 2:** deployment-scaler-role.yml

## Worker Conclusion
Automated worker cannot proceed. This bead requires human intervention with cluster-admin access. All preparations are complete and ready for human execution.

**Next Action:** Human with cluster-admin kubeconfig for apexalgo-iad must execute Steps 1-3 above.
