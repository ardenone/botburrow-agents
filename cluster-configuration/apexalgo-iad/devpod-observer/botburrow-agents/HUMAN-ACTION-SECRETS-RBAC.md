# 🚨 HUMAN ACTION REQUIRED: Apply Secrets-Manager RBAC

**Bead:** bd-12r - Grant devpod-observer RBAC access to botburrow namespace
**Status:** Waiting for cluster-admin to apply RBAC manifest
**Date Created:** 2026-02-15
**Blocks:** bd-2jm (Hub API authentication fix)

---

## What Needs to Be Done

Apply the secrets-manager RBAC manifest to the **apexalgo-iad** cluster to grant the devpod-observer ServiceAccount permission to read and update secrets in the botburrow-agents namespace.

## Why This Is Needed

- **Current State:** devpod-observer has read-only access to monitoring and devpod-observer namespaces
- **Problem:** Cannot apply Hub API authentication fix (bd-2jm) - needs to edit botburrow-agents-secrets
- **Solution:** Grant minimal secrets read/write permissions via RBAC
- **Scope:** botburrow-agents namespace only
- **Permissions:** secrets (get, list, patch, update)

---

## Quick Apply (Recommended)

### Prerequisites
- Cluster-admin access to apexalgo-iad cluster
- kubectl configured with admin context

### Commands

```bash
# Clone or navigate to botburrow-agents repository
cd /path/to/botburrow-agents

# Apply the RBAC manifest
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# Verify role was created
kubectl get role -n botburrow-agents secrets-manager

# Verify rolebinding was created
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
```

### Expected Output

```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
```

---

## Verification

After applying, verify the permissions work from devpod:

```bash
# From devpod with apexalgo-iad kubeconfig
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Test secret read permission
kubectl get secret -n botburrow-agents botburrow-agents-secrets

# Should succeed with output showing secret metadata
# NAME                       TYPE     DATA   AGE
# botburrow-agents-secrets   Opaque   X      XXd

# Test secret patch permission (dry-run to avoid changes)
kubectl patch secret -n botburrow-agents botburrow-agents-secrets \
  --type='json' -p='[{"op": "test", "path": "/data", "value": {}}]' \
  --dry-run=server

# Should succeed or show existing data structure
```

---

## What This Grants

The secrets-manager role grants these permissions **in botburrow-agents namespace only**:

### Read Permissions
- `secrets` → get, list

### Write Permissions
- `secrets` → patch, update

### What This Does NOT Grant
- ❌ Create new secrets
- ❌ Delete secrets
- ❌ Access to other namespaces
- ❌ Access to other resource types (configmaps, deployments, etc.)
- ❌ Cluster-wide permissions

---

## Security Review

### Minimal Scope
- **Namespace:** botburrow-agents only
- **Subject:** devpod-observer ServiceAccount only
- **Verbs:** No create/delete permissions
- **Resources:** Only secrets (read + update)

### Risk Assessment
- **Risk Level:** Medium (secrets access)
- **Blast Radius:** Limited to botburrow-agents namespace secrets
- **Reversibility:** Can be removed with `kubectl delete -f secrets-manager-role.yml`
- **Use Case:** Configuration management for Hub API authentication

### Justification
- Required for fixing Hub API authentication (bd-2jm)
- Enables devpod workers to update application configuration
- No create/delete - cannot add new secrets or remove existing ones
- Aligns with existing deployment-scaler RBAC pattern

### Recommended Action
✅ **APPROVE** - Necessary for Hub API fix, minimal scope, no destructive permissions

---

## Alternative: Manual Application

If you prefer to review the manifest first:

```bash
# View the manifest
cat cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# Copy/paste into Kubernetes dashboard or kubectl
# Then apply manually
```

---

## Post-Application Actions

### 1. Verify Access Works
```bash
# From devpod
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get secret -n botburrow-agents botburrow-agents-secrets -o yaml
```

### 2. Notify Workers
Once applied, unblock bd-12r:

```bash
cd /home/coder/botburrow-agents
br close bd-12r --status completed
```

### 3. Unblock bd-2jm
The Hub API fix can now proceed:

```bash
# bd-2jm will automatically become available once bd-12r is closed
# Worker will pick it up and apply the Hub API authentication patch
```

---

## Error from Current State

**Before RBAC Application:**
```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl get secret -n botburrow-agents botburrow-agents-secrets
Error from server (Forbidden): secrets "botburrow-agents-secrets" is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot get resource
"secrets" in API group "" in the namespace "botburrow-agents"
```

**After RBAC Application (Expected):**
```bash
$ kubectl get secret -n botburrow-agents botburrow-agents-secrets
NAME                       TYPE     DATA   AGE
botburrow-agents-secrets   Opaque   4      14d
```

---

## Troubleshooting

### Error: "forbidden: User cannot create resource"
- Cause: Not using cluster-admin context
- Fix: Switch to admin kubeconfig for apexalgo-iad

### Error: "namespaces 'botburrow-agents' not found"
- Cause: Wrong cluster context
- Fix: Verify you're targeting apexalgo-iad cluster
  ```bash
  kubectl config current-context
  kubectl get namespaces | grep botburrow
  ```

### Verification Fails: "forbidden: cannot get secrets"
- Cause: RoleBinding subject mismatch
- Fix: Verify devpod-observer ServiceAccount exists in devpod-observer namespace:
  ```bash
  kubectl get sa -n devpod-observer devpod-observer
  ```

### Verification Fails: "forbidden: cannot patch secrets"
- Cause: RoleBinding not applied or incorrect role permissions
- Fix: Check if role and rolebinding exist:
  ```bash
  kubectl get role -n botburrow-agents secrets-manager -o yaml
  kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager -o yaml
  ```

---

## Rollback

If you need to remove these permissions:

```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

---

## Related Documentation

- **Manifest Location:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml`
- **Related Bead (Blocked):** bd-2jm (Hub API authentication fix)
- **Related Bead (Current):** bd-12r (Grant RBAC access)
- **Discovery Document:** `cluster-configuration/apexalgo-iad/devpod-observer/KUBECTL-PROXY-RESOLUTION-2026-02-15.md`
- **Similar RBAC Example:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/HUMAN-ACTION-APPLY-RBAC.md`

---

## Questions?

If you have concerns about granting secrets access:

1. **Scope:** Only botburrow-agents namespace (not cluster-wide)
2. **Verbs:** No create/delete (cannot add/remove secrets)
3. **Subject:** Only devpod-observer ServiceAccount
4. **Purpose:** Configuration management for Hub API authentication
5. **Precedent:** Similar pattern used for deployment-scaler RBAC (bd-3o6)

---

**Status:** ⏳ Waiting for human to apply manifest
**Next Step:** Once applied, bd-2jm can proceed with Hub API authentication fix
