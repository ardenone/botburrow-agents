# BD-2JM: Cluster-Admin Action Required

**Status:** ⚠️ BLOCKED - Requires cluster-admin privileges
**Created:** 2026-02-15
**Bead:** bd-2jm (CLUSTER-ADMIN: Apply Hub API authentication fix)
**Worker:** claude-code

## Summary

The Hub API authentication fix has been **fully prepared and verified**, but execution is **blocked by RBAC permissions**. The devpod-observer ServiceAccount has **read-only access** and cannot modify secrets in the `botburrow-agents` namespace.

## What Was Verified

✅ **kubectl access to apexalgo-iad cluster** - Working
✅ **Fix script exists** - `/home/coder/botburrow-agents/scripts/fix-hub-auth.sh`
✅ **Coordinator pods are running** - 2/2 coordinator pods, 2/2 coordinator-git-sync pods
❌ **Secret access** - Forbidden (requires cluster-admin)

## Required Action (Cluster-Admin Only)

A user with **cluster-admin** privileges on the **apexalgo-iad** cluster must execute the fix.

### Option 1: Use Automated Fix Script (RECOMMENDED)

```bash
# On a machine with cluster-admin kubeconfig for apexalgo-iad
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig
cd /home/coder/botburrow-agents
./scripts/fix-hub-auth.sh
```

**What the script does:**
1. Shows current secret keys
2. Extracts existing values (HUB_API_KEY, R2_*, FORGEJO_*, GITHUB_*)
3. Prompts for Hub API key if needed
4. Recreates secret with BOTBURROW_ prefixes
5. Restarts coordinator deployments
6. Shows logs to verify no 401 errors

### Option 2: Manual kubectl Commands

```bash
# Set kubeconfig with cluster-admin access
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Get current secret to extract values
kubectl get secret botburrow-agents-secrets -n botburrow-agents -o yaml > /tmp/secret-backup.yml

# Edit the secret
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# In the editor, rename the base64 keys (keep the values):
# HUB_API_KEY → BOTBURROW_HUB_API_KEY
# R2_ENDPOINT → BOTBURROW_R2_ENDPOINT
# R2_ACCESS_KEY → BOTBURROW_R2_ACCESS_KEY
# R2_SECRET_KEY → BOTBURROW_R2_SECRET_KEY

# Restart coordinator
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents

# Verify
kubectl rollout status deployment coordinator -n botburrow-agents
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50
```

## Verification After Fix

After applying the fix, verify:

```bash
# Check logs (should see no 401 errors)
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50

# Check environment variable is set
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY

# All coordinator pods should be Running
kubectl get pods -n botburrow-agents | grep coordinator
```

Expected results:
- ✅ No `401 Unauthorized` errors in logs
- ✅ `BOTBURROW_HUB_API_KEY` environment variable exists
- ✅ All coordinator pods in `Running` state

## Root Cause

**Environment variable naming mismatch:**
- **Secret contains:** `HUB_API_KEY` (without BOTBURROW_ prefix)
- **Application expects:** `BOTBURROW_HUB_API_KEY` (with BOTBURROW_ prefix)

This causes the coordinator to poll the Hub API without authentication, resulting in continuous 401 errors.

## RBAC Constraints

The devpod-observer ServiceAccount has:
- ✅ Read access to pods, deployments, services in botburrow-agents namespace
- ❌ **No access to secrets** in botburrow-agents namespace (security boundary)

This is intentional security design - secrets require cluster-admin or specific RoleBinding.

## Related Files

- **Fix script:** `scripts/fix-hub-auth.sh`
- **Documentation:** `docs/hub-api-authentication-fix.md`
- **Secret placeholder:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Original bead:** bd-q21 (HUMAN: Fix coordinator Hub API authentication (401 errors))

## Next Steps

1. **Cluster-admin** executes Option 1 or Option 2 above
2. Verify coordinator logs show no 401 errors
3. Test end-to-end flow with a notification
4. Update bead bd-2jm status to `completed`

## Additional Context

**Current cluster state (as of 2026-02-15):**

```
NAME                                    READY   STATUS    RESTARTS   AGE
coordinator-644b76d7bd-89trf            1/1     Running   0          19h
coordinator-644b76d7bd-pwlft            1/1     Running   0          19h
coordinator-git-sync-79db4b749c-4dz6d   2/2     Running   0          19h
coordinator-git-sync-79db4b749c-sbl4p   2/2     Running   0          19h
```

All coordinator pods are running, but experiencing 401 errors when polling the Hub API.
