# CLUSTER-ADMIN: Apply RBAC Manifests for devpod-observer

**Bead:** bd-1qs (CLUSTER-ADMIN: Apply RBAC manifests for devpod-observer in botburrow-agents namespace)
**Date:** 2026-02-15
**Cluster:** apexalgo-iad
**Required Access:** cluster-admin or equivalent RBAC creation privileges

## Overview

The devpod-observer ServiceAccount needs RBAC permissions to manage resources in the `botburrow-agents` namespace. However, the ServiceAccount lacks permission to create RBAC resources (Roles/RoleBindings), which requires cluster-admin intervention.

## Why This Is Needed

This RBAC configuration enables:
1. **bd-2jm** - Hub API authentication fix (requires secret read/write access)
2. **bd-3o6** - Runner scaling tests (requires deployment scaling access)

## Prerequisites

✅ **Verified:**
- Namespace `botburrow-agents` exists (Active, 14 days old)
- ServiceAccount `devpod-observer` exists in `devpod-observer` namespace (32 days old)
- No existing RBAC resources conflict with these manifests

## Manifests to Apply

Two RBAC manifest files are ready in this directory:

### 1. `secrets-manager-role.yml`
**Purpose:** Grant read/write access to secrets in `botburrow-agents` namespace

**Permissions:**
- `get`, `list`, `patch`, `update` on secrets

**Use Case:** Allows devpod-observer to update Hub API authentication secrets (bd-2jm)

### 2. `deployment-scaler-role.yml`
**Purpose:** Grant deployment scaling permissions for testing

**Permissions:**
- Scale deployments (`deployments/scale`)
- Read deployments, pods, replicasets (verification)
- Manage HorizontalPodAutoscalers
- Port-forward to pods (Valkey access)

**Use Case:** Enables runner scaling tests and performance verification (bd-3o6)

## Application Instructions

### Option 1: Apply Both Manifests (Recommended)

```bash
# Ensure you have cluster-admin kubeconfig for apexalgo-iad cluster
export KUBECONFIG=/path/to/apexalgo-iad-cluster-admin.kubeconfig

# Navigate to manifests directory
cd /home/coder/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents

# Apply both RBAC manifests
kubectl apply -f secrets-manager-role.yml
kubectl apply -f deployment-scaler-role.yml

# Expected output:
# role.rbac.authorization.k8s.io/secrets-manager created
# rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
# role.rbac.authorization.k8s.io/deployment-scaler created
# rolebinding.rbac.authorization.k8s.io/devpod-observer-scaler created
```

### Option 2: Apply Individually

If you want to apply manifests separately:

```bash
# Apply secrets-manager role only
kubectl apply -f secrets-manager-role.yml

# Apply deployment-scaler role only
kubectl apply -f deployment-scaler-role.yml
```

## Verification

After applying the manifests, verify the RBAC permissions were granted correctly:

```bash
# Set kubeconfig (if not already set)
export KUBECONFIG=/path/to/apexalgo-iad-cluster-admin.kubeconfig

# Verify Roles were created
kubectl get role -n botburrow-agents secrets-manager deployment-scaler

# Expected output:
# NAME                 CREATED AT
# secrets-manager      2026-02-15T22:XX:XXZ
# deployment-scaler    2026-02-15T22:XX:XXZ

# Verify RoleBindings were created
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager devpod-observer-scaler

# Expected output:
# NAME                              ROLE                      AGE
# devpod-observer-secrets-manager   Role/secrets-manager      XXs
# devpod-observer-scaler            Role/deployment-scaler    XXs

# Test secret access permissions
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

kubectl auth can-i patch secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

# Test deployment scaling permissions
kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes

kubectl auth can-i get pods -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: yes
```

## Post-Application Steps

After successfully applying the manifests:

1. **Notify the worker** that created bd-1qs (update bead status if possible)
2. **Verify from devpod** (optional):
   ```bash
   # From a devpod with apexalgo-iad kubeconfig
   export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
   kubectl get secret -n botburrow-agents botburrow-agents-secrets
   # Should succeed without "Forbidden" error
   ```

3. **Unblock dependent beads:**
   - bd-12r - Grant devpod-observer RBAC access (this bead's parent)
   - bd-2jm - Hub API authentication fix (can now proceed)
   - bd-3o6 - Runner scaling tests (can now proceed)

## Rollback (If Needed)

To remove the RBAC permissions:

```bash
# Delete both manifests
kubectl delete -f secrets-manager-role.yml
kubectl delete -f deployment-scaler-role.yml

# Or delete resources individually
kubectl delete role secrets-manager -n botburrow-agents
kubectl delete rolebinding devpod-observer-secrets-manager -n botburrow-agents
kubectl delete role deployment-scaler -n botburrow-agents
kubectl delete rolebinding devpod-observer-scaler -n botburrow-agents
```

## Security Considerations

✅ **Least Privilege:**
- Both roles grant minimal permissions scoped to specific resources
- No cluster-wide permissions (ClusterRole)
- No ability to create/delete resources (only read/update)
- No secret creation permission (only update existing secrets)

✅ **Audit Trail:**
- Manifests are tracked in Git
- Labeled with bead IDs for traceability
- Annotations document purpose and context

✅ **Limited Scope:**
- Permissions restricted to `botburrow-agents` namespace only
- No cross-namespace access
- No escalation risk (cannot create RBAC resources)

## Troubleshooting

### Error: "namespaces botburrow-agents not found"
**Solution:** Create the namespace first:
```bash
kubectl create namespace botburrow-agents
```

### Error: "serviceaccounts devpod-observer not found"
**Solution:** Verify ServiceAccount exists:
```bash
kubectl get serviceaccount -n devpod-observer devpod-observer
```
If missing, check cluster-configuration/apexalgo-iad/devpod-observer/ for ServiceAccount manifest.

### Error: "role already exists"
**Solution:** Update instead of create:
```bash
kubectl apply -f secrets-manager-role.yml --force
```

### Permissions still denied after applying
**Solution:** Verify RoleBinding references correct ServiceAccount:
```bash
kubectl get rolebinding devpod-observer-secrets-manager -n botburrow-agents -o yaml
```
Check that `subjects[0].name` is `devpod-observer` and `subjects[0].namespace` is `devpod-observer`.

## Contact

If you have questions or encounter issues:
- **Bead:** bd-1qs
- **Worker:** claude-code-worker
- **Workspace:** /home/coder/botburrow-agents
- **Git Repo:** botburrow-agents (GitHub)

## Status Tracking

- [ ] Manifests reviewed by cluster-admin
- [ ] Manifests applied to apexalgo-iad cluster
- [ ] Verification tests passed
- [ ] Dependent beads notified/unblocked
