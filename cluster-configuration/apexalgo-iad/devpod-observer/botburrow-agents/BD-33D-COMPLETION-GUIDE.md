# BD-33D: CLUSTER-ADMIN Action Required

**Status:** Ready for human cluster-admin execution
**Date:** 2026-02-16
**Bead ID:** bd-33d
**Related Bead:** bd-1qs

## Summary

This bead requires a **human with cluster-admin credentials** for the apexalgo-iad cluster to apply RBAC manifests. All manifests are prepared, validated, and committed to git. The worker cannot proceed due to lack of cluster-admin permissions (intentional security design).

## Prerequisites ✅

All prerequisites have been verified and are ready:

1. ✅ **Manifests exist and are validated:**
   - `secrets-manager-role.yml` (1.6 KB)
   - `deployment-scaler-role.yml` (2.3 KB)

2. ✅ **Target namespace exists:**
   - Namespace: `botburrow-agents` (Status: Active)

3. ✅ **ServiceAccount exists:**
   - `devpod-observer` in namespace `devpod-observer`

4. ✅ **RBAC resources NOT yet applied:**
   - Role `secrets-manager` does NOT exist (confirmed)
   - Role `deployment-scaler` does NOT exist (confirmed)

5. ✅ **Documentation complete:**
   - CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md
   - WORKER-STATUS.md
   - This guide (BD-33D-COMPLETION-GUIDE.md)

## Required Action

### Step 1: Set Cluster-Admin Context

On a machine with cluster-admin access to apexalgo-iad:

```bash
# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Verify cluster-admin access
kubectl auth can-i create roles -n botburrow-agents
# Should return: yes
```

### Step 2: Navigate to Repository

```bash
# Clone repository if needed
cd /home/coder/botburrow-agents

# Or if on different machine:
# git clone <repo-url>
# cd botburrow-agents
```

### Step 3: Apply RBAC Manifests

```bash
# Apply secrets-manager role and binding
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# Apply deployment-scaler role and binding
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

**Expected output:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
role.rbac.authorization.k8s.io/deployment-scaler created
rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created
```

### Step 4: Verify RBAC Applied

```bash
# Check roles exist
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Check role bindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Test permissions (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

**All verification commands should succeed.**

### Step 5: Close Beads

```bash
# Navigate to botburrow-agents workspace
cd /home/coder/botburrow-agents

# Close bd-1qs (original worker bead)
br close bd-1qs --status completed

# Close bd-33d (this human bead)
br close bd-33d --status completed

# Sync beads to JSONL
br sync --flush-only

# Commit and push
git add .beads/*.jsonl
git commit -m "chore(bd-1qs,bd-33d): cluster-admin applied RBAC manifests

Applied secrets-manager and deployment-scaler roles to botburrow-agents namespace
in apexalgo-iad cluster for devpod-observer ServiceAccount.

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

## What This Unblocks

Once RBAC is applied, these downstream beads can proceed:

- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix (needs secret write access)
- **bd-3o6** - Runner scaling tests (needs deployment scaling access)

## Security Review

Both roles follow **principle of least privilege**:

### secrets-manager
- **Scope:** botburrow-agents namespace only
- **Resources:** secrets only
- **Verbs:** get, list, patch, update
- **NO permission to:** create, delete, deletecollection

### deployment-scaler
- **Scope:** botburrow-agents namespace only
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **NO permission to:** delete deployments or other destructive operations

## Troubleshooting

### Problem: "Unauthorized" or "Forbidden" error

**Cause:** Kubeconfig does not have cluster-admin permissions
**Fix:** Verify you're using the correct cluster-admin kubeconfig:

```bash
kubectl auth can-i create roles -n botburrow-agents
# Must return: yes
```

### Problem: Roles already exist

**Cause:** Manifests were already applied previously
**Fix:** This is OK! Verify permissions work and close the beads:

```bash
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Should return: yes
```

### Problem: Cannot close beads (br command not found)

**Cause:** Not in devpod environment
**Fix:** SSH into devpod or close beads via different method:

```bash
# From devpod:
cd /home/coder/botburrow-agents
br close bd-1qs --status completed
br close bd-33d --status completed
```

## Reference Files

- **Apply Instructions:** CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md
- **Worker Status:** WORKER-STATUS.md
- **secrets-manager manifest:** secrets-manager-role.yml
- **deployment-scaler manifest:** deployment-scaler-role.yml

## Contact

If you encounter issues or need clarification:
- Check existing documentation in this directory
- Review bead comments: `br show bd-33d` or `br show bd-1qs`
- Consult cluster admin team for apexalgo-iad access

---

**Status:** Ready for cluster-admin execution
**Last Updated:** 2026-02-16
**Worker:** Claude Code Worker
**Action Required:** Human cluster-admin must apply manifests
