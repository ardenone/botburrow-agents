# 🚨 HUMAN ACTION REQUIRED - Apply RBAC Manifests to apexalgo-iad Cluster

**Bead:** bd-1qs
**Priority:** P0 CRITICAL (blocks bd-12r, bd-2jm, bd-3o6)
**Required Role:** cluster-admin access to apexalgo-iad cluster
**Estimated Time:** < 2 minutes
**Last Verified:** 2026-02-16 01:33 UTC

## TL;DR - What You Need to Do

Apply two RBAC manifest files to apexalgo-iad cluster using cluster-admin kubeconfig. These grant minimal permissions to devpod-observer ServiceAccount for secrets management and deployment scaling.

## Quick Start (Copy-Paste)

**⚠️ CRITICAL:** Do NOT use `/home/coder/.kube/apexalgo-iad.kubeconfig` (read-only devpod kubeconfig)
**✅ USE:** Your personal cluster-admin kubeconfig for apexalgo-iad cluster

```bash
# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig

# Verify you have permission to create roles
kubectl auth can-i create roles -n botburrow-agents
# Expected: yes

# Navigate to manifest directory (adjust path as needed)
cd /path/to/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# Apply RBAC manifests
kubectl apply -f secrets-manager-role.yml
kubectl apply -f deployment-scaler-role.yml

# Verify permissions granted
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes
```

## Why This Is Needed

Workers cannot create RBAC resources because the devpod-observer ServiceAccount intentionally lacks this permission as a security boundary. This prevents workers from escalating privileges.

**Error encountered:**
```
Error from server (Forbidden): roles.rbac.authorization.k8s.io is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "roles"
in API group "rbac.authorization.k8s.io" in the namespace "botburrow-agents"
```

**What This Unblocks:**
- ✅ bd-12r - CLUSTER-ADMIN: Grant devpod-observer RBAC access to botburrow-agents namespace
- ✅ bd-2jm - Hub API authentication fix (requires secret write access)
- ✅ bd-3o6 - Runner scaling tests (requires deployment scaling access)

## Current Status

✅ **Worker verification complete** (2026-02-15)
- Manifests validated and committed
- Prerequisites verified (namespace exists, ServiceAccount exists)
- Documentation complete
- Stale dependency removed (bd-33d no longer exists)

❌ **RBAC resources NOT applied yet** (verified 2026-02-16 01:33 UTC)
- `kubectl get role -n botburrow-agents secrets-manager` → NotFound
- `kubectl get role -n botburrow-agents deployment-scaler` → NotFound

🔒 **Permissions verified correct** (2026-02-16 01:33 UTC)
- Current kubeconfig: `/home/coder/.kube/apexalgo-iad.kubeconfig`
- Identity: `system:serviceaccount:devpod-observer:devpod-observer`
- Can create roles: **NO** (intentional security boundary)

## Manifests to Apply

### 1. secrets-manager-role.yml (49 lines)

**Purpose:** Grant devpod-observer permission to read and update secrets in botburrow-agents namespace

**Permissions:**
- **Resources:** secrets
- **Verbs:** get, list, patch, update
- **Scope:** botburrow-agents namespace only
- **NO permission to:** create or delete secrets

**Required for:** bd-2jm (Hub API authentication fix)

### 2. deployment-scaler-role.yml (74 lines)

**Purpose:** Grant devpod-observer permission to scale deployments and manage HPAs for testing

**Permissions:**
- **Resources:** deployments/scale, deployments, HPAs, pods, replicasets, pods/portforward
- **Verbs:** get, list, watch, patch, update, create (portforward only)
- **Scope:** botburrow-agents namespace only
- **NO permission to:** delete deployments or modify other resources

**Required for:** bd-3o6 (Runner scaling tests)

## Security Review

**Is this safe?** ✅ YES (minimal permissions)

- ✅ **Namespace-scoped:** Both roles only affect botburrow-agents namespace
- ✅ **Resource-scoped:** Limited to specific resources (secrets, deployments)
- ✅ **Minimal verbs:** No delete or create permissions for most resources
- ✅ **No privilege escalation:** Cannot create/modify RBAC resources
- ✅ **Auditable:** All actions logged in Kubernetes audit logs
- ✅ **Principle of least privilege:** Only permissions needed for specific tasks

## Expected Output

**Applying manifests:**
```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
role.rbac.authorization.k8s.io/deployment-scaler created
rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created
```

**Verification:**
```
# Check roles exist
$ kubectl get role -n botburrow-agents
NAME                  CREATED AT
deployment-scaler     2026-02-16T01:40:00Z
secrets-manager       2026-02-16T01:40:00Z

# Check rolebindings exist
$ kubectl get rolebinding -n botburrow-agents
NAME                                ROLE                       AGE
devpod-observer-scaler              Role/deployment-scaler     1m
devpod-observer-secrets-manager     Role/secrets-manager       1m

# Test permissions (should return "yes")
$ kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
yes

$ kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
yes
```

## Additional Verification

```bash
# Verify roles exist
kubectl get role -n botburrow-agents secrets-manager -o yaml
kubectl get role -n botburrow-agents deployment-scaler -o yaml

# Verify rolebindings exist
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager -o yaml
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler -o yaml

# Test specific permissions
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i delete secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Should return: no (no delete permission)

kubectl auth can-i scale deployments -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i delete deployments -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Should return: no (no delete permission)
```

## After Applying Manifests

Close the bead to mark this work complete:

```bash
# From botburrow-agents repository
cd /home/coder/botburrow-agents

# Close bead
br close bd-1qs --status completed

# Sync and commit
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-1qs): cluster-admin applied RBAC manifests

Applied to apexalgo-iad cluster:
- secrets-manager-role.yml (grants get/list/patch/update secrets)
- deployment-scaler-role.yml (grants deployment scaling permissions)

Verified permissions granted to devpod-observer ServiceAccount.

Unblocks:
- bd-12r (Grant devpod-observer RBAC access)
- bd-2jm (Hub API authentication fix)
- bd-3o6 (Runner scaling tests)

Co-Authored-By: Cluster Admin <admin@ardenone.com>"
git push origin main
```

This will automatically unblock downstream beads:
- **bd-12r** - Parent bead requesting RBAC access
- **bd-2jm** - Hub API authentication fix
- **bd-3o6** - Runner scaling tests

## Documentation References

- **Application Instructions:** `CLUSTER-ADMIN-APPLY-INSTRUCTIONS.md` (detailed guide)
- **Worker Status:** `WORKER-STATUS.md` (verification results from 2026-02-15)
- **This Document:** `HUMAN-ACTION-REQUIRED.md` (current status as of 2026-02-16)
- **Manifests:** `secrets-manager-role.yml`, `deployment-scaler-role.yml`
