# Cluster-Admin: Apply RBAC Manifests for botburrow-agents Namespace

**Status:** ✅ MANIFESTS READY - AWAITING CLUSTER-ADMIN APPLICATION
**Date Created:** 2026-02-15
**Bead ID:** bd-1qs
**Related Beads:** bd-12r, bd-2jm, bd-3o6

## Overview

This directory contains RBAC manifests that grant the `devpod-observer` ServiceAccount minimal permissions to manage secrets and deployments in the `botburrow-agents` namespace on the apexalgo-iad cluster.

**CRITICAL:** These manifests require **cluster-admin level access** to apply, as the devpod-observer ServiceAccount does NOT have permission to create RBAC resources.

## Manifests Ready to Apply

### 1. secrets-manager-role.yml
**Purpose:** Grant read and update permissions for secrets
**Required for:** bd-2jm (Hub API authentication fix)
**Permissions:**
- `get`, `list`, `patch`, `update` on secrets in botburrow-agents namespace

### 2. deployment-scaler-role.yml
**Purpose:** Grant deployment scaling and HPA management permissions
**Required for:** bd-3o6 (Runner scaling tests)
**Permissions:**
- Scale deployments (`apps/deployments/scale`)
- Read deployment status
- Manage HorizontalPodAutoscalers
- Read pods and replicasets
- Port-forward to pods (for Valkey testing)

## Application Instructions

### Prerequisites
- Cluster-admin kubeconfig for apexalgo-iad cluster
- Access to this repository at commit: `main` (latest)

### Step 1: Apply RBAC Manifests

```bash
# From a machine with cluster-admin access to apexalgo-iad
cd /path/to/botburrow-agents

# Apply secrets manager role and binding
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# Apply deployment scaler role and binding
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

### Step 2: Verify Application

```bash
# Check that roles were created
kubectl get role -n botburrow-agents secrets-manager
kubectl get role -n botburrow-agents deployment-scaler

# Check that rolebindings were created
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Verify permissions (should return "yes")
kubectl auth can-i get secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch secrets -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer

kubectl auth can-i patch deployments/scale -n botburrow-agents \
  --as=system:serviceaccount:devpod-observer:devpod-observer
```

### Step 3: Notify Workers

Once applied, update this file:
1. Change status to: `✅ APPLIED - DATE: <application-date>`
2. Commit and push changes to main branch
3. Workers will automatically retry blocked beads (bd-12r, bd-2jm, bd-3o6)

## Security Rationale

### Why These Permissions Are Safe

1. **Principle of Least Privilege:**
   - Only minimal permissions required for specific tasks
   - Scoped to single namespace (botburrow-agents)
   - No cluster-wide access
   - No permission to create/delete resources (only read/update)

2. **Read-Only Where Possible:**
   - Deployment scaling uses `/scale` subresource (not full deployment write)
   - Secret updates are limited to `patch` and `update` (no create/delete)
   - All HPA operations are scoped to autoscaling group

3. **Auditable:**
   - All permissions documented in manifests
   - Labels track which bead requested permissions
   - ArgoCD manages manifests for GitOps workflow

4. **Temporary Use Case:**
   - Secrets management: One-time fix for bd-2jm
   - Scaling tests: Limited testing for bd-3o6
   - Can be revoked after testing completes

## Alternative: Revoke After Use

If these permissions are temporary, they can be removed after the blocking beads are resolved:

```bash
# After bd-2jm and bd-3o6 are completed
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

## Troubleshooting

### Permission Denied After Application

```bash
# Check rolebindings reference correct ServiceAccount
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager -o yaml | grep -A 3 subjects

# Should show:
# subjects:
# - kind: ServiceAccount
#   name: devpod-observer
#   namespace: devpod-observer
```

### Workers Still Report Forbidden Errors

```bash
# Verify kubectl-proxy pod is healthy (it caches RBAC for 5 minutes)
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get pods -n devpod-observer

# Restart kubectl-proxy to flush RBAC cache
kubectl rollout restart deployment/kubectl-proxy -n devpod-observer
```

## Related Documentation

- **RBAC Overview:** `/home/coder/.claude/CLAUDE.md` (Cross-Cluster kubectl Access)
- **Original Request:** Bead bd-12r (CLUSTER-ADMIN: Grant devpod-observer RBAC access)
- **Blocked Beads:** bd-2jm (Hub API fix), bd-3o6 (Scaling tests)
- **Kubectl-Proxy Status:** `cluster-configuration/apexalgo-iad/devpod-observer/KUBECTL-PROXY-STATUS.md`

## Change Log

| Date | Action | By | Notes |
|------|--------|-----|-------|
| 2026-02-15 | Manifests created | claude-code-worker | Bead bd-1qs - Ready for cluster-admin application |
| | | | Awaiting human with cluster-admin kubeconfig |
