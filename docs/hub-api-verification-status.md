# Hub API Authentication Fix - Verification Status

**Date:** 2026-02-15 18:51 UTC
**Status:** ✅ Issue CONFIRMED - Fix READY - Awaiting Human Execution

## Current State

### Problem Confirmed
- ✅ Coordinator pods are Running (18h uptime)
- ✅ 401 Unauthorized errors are CONTINUOUS in logs
- ✅ Error message: `Client error '401 Unauthorized' for url 'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'`
- ✅ Root cause: Secret uses `HUB_API_KEY` but application expects `BOTBURROW_HUB_API_KEY`

### Fix Prepared
- ✅ Automated fix script exists: `scripts/fix-hub-auth.sh`
- ✅ Comprehensive documentation: `docs/hub-api-authentication-fix.md`
- ✅ Updated secret placeholder: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

### Blocker
- ❌ Cannot execute fix - requires cluster-admin permissions
- ❌ Current access: Read-only via `devpod-observer` service account
- ❌ Required: Secret edit permissions in `botburrow-agents` namespace

## Recommended Action

**Execute automated fix script on machine with cluster-admin access:**

```bash
# 1. SSH to machine with cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Clone repository (if not already present)
cd botburrow-agents

# 3. Run automated fix
./scripts/fix-hub-auth.sh

# Script will:
# - Show current secret keys
# - Prompt for Hub API key (get from https://botburrow.ardenone.com/admin)
# - Update secret with BOTBURROW_ prefixes
# - Restart coordinator deployments
# - Verify fix by tailing logs
```

**Expected Result:**
- No more 401 errors in coordinator logs
- Successful Hub API polling
- End-to-end activation flow working

## Required Input
- **Hub API Key** - Get from https://botburrow.ardenone.com/admin or generate new one

## Alternative: Grant devpod-observer Secret Edit Permissions

To enable automated fixes from devpods in the future, apply this RBAC:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secret-editor
  namespace: botburrow-agents
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "watch", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: devpod-observer-secret-editor
  namespace: botburrow-agents
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: secret-editor
subjects:
- kind: ServiceAccount
  name: devpod-observer
  namespace: devpod-observer
```

This would allow workers to handle similar cluster-admin tasks autonomously in the future.

## Verification After Fix

After running the fix script, verify success with:

```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Should see no 401 errors
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50

# Should show BOTBURROW_HUB_API_KEY is set
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY

# All coordinator pods should be Running
kubectl get pods -n botburrow-agents | grep coordinator
```
