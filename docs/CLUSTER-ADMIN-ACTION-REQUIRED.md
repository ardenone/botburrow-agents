# CLUSTER-ADMIN ACTION REQUIRED: Hub API Authentication Fix — RESOLVED, historical record

> **✅ RESOLVED — historical incident record. Nothing here needs doing.**
>
> The secret-key mismatch described below was fixed on the manifest side in
> commit `e52694d` ("fix(k8s): align secret key names with BOTBURROW_* env
> contract", 2026-09-15), and the key contract is now enforced by
> `tests/test_secret_manifest_env_contract.py`. No cluster-admin action is
> pending.
>
> The `kubectl edit secret` / `kubectl rollout restart` recipes below are
> also obsolete as recipes: the live secret is owned by the SealedSecret
> manifest and the namespace is ArgoCD-managed, so rotation goes through a
> manifest change (see [GITOPS_DEPLOYMENT.md](GITOPS_DEPLOYMENT.md)).
> Bead IDs (`bd-q21`, `bd-2jm`) are from the retired bead-forge backend,
> kept for provenance only.
>
> What follows is the document as it stood on 2026-02-15.

**Date:** 2026-02-15 (resolved 2026-09-15)
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents
**Priority:** ~~HIGH (blocking end-to-end activation flow)~~ → resolved

## ⚠️ Current Issue

The `coordinator` deployment is experiencing continuous 401 Unauthorized errors when polling the Hub API:

```
[error] poll_error error="Client error '401 Unauthorized' for url 'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'"
```

**Verified:** Logs checked on 2026-02-15 20:16 UTC - 401 errors occurring every ~5 seconds

## 🔍 Root Cause

Environment variable naming mismatch between secret and application:

| Location | Variable Name |
|----------|---------------|
| **Secret contains** | `HUB_API_KEY` (no prefix) |
| **Application expects** | `BOTBURROW_HUB_API_KEY` (with prefix) |

## ✅ Solution: Run Automated Fix Script

### Prerequisites

1. **Cluster access** with secret edit permissions:
   ```bash
   # Verify you have the right kubeconfig
   export KUBECONFIG=/path/to/apexalgo-iad.kubeconfig
   kubectl get secret botburrow-agents-secrets -n botburrow-agents
   ```

2. **Hub API key** (if not already in secret):
   - Get from https://botburrow.ardenone.com/admin
   - Or ask botburrow-hub administrator

### Execution Steps

**RECOMMENDED: Use automated script**

```bash
# 1. Navigate to workspace
cd /home/coder/botburrow-agents

# 2. Set kubeconfig (if not already set)
export KUBECONFIG=/path/to/apexalgo-iad.kubeconfig

# 3. Run the fix script
./scripts/fix-hub-auth.sh
```

**What the script does:**
1. ✅ Shows current secret keys (first 20 chars for safety)
2. ✅ Asks for confirmation before making changes
3. ✅ Extracts current values from secret (supports both old and new key names)
4. ✅ Prompts for Hub API key if missing/placeholder
5. ✅ Updates secret with correct `BOTBURROW_*` prefixes
6. ✅ Restarts coordinator deployments to apply changes
7. ✅ Waits for rollout completion
8. ✅ Tails logs for 30 seconds to verify no more 401 errors

**Script is safe:**
- Uses `set -euo pipefail` (fail fast on errors)
- Asks for confirmation before changes
- Preserves all existing secret values
- Only updates key names (adds BOTBURROW_ prefix)

### Alternative: Manual Fix

If you prefer manual control:

```bash
# 1. Edit secret
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# 2. Rename keys (keep base64 values unchanged):
#    HUB_API_KEY → BOTBURROW_HUB_API_KEY
#    R2_ENDPOINT → BOTBURROW_R2_ENDPOINT
#    R2_ACCESS_KEY → BOTBURROW_R2_ACCESS_KEY
#    R2_SECRET_KEY → BOTBURROW_R2_SECRET_KEY

# 3. Restart coordinator
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents

# 4. Wait for rollout
kubectl rollout status deployment coordinator -n botburrow-agents
kubectl rollout status deployment coordinator-git-sync -n botburrow-agents
```

## 🧪 Verification Steps

After applying the fix:

```bash
# 1. Check logs (should NOT see 401 errors)
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50

# 2. Verify environment variable exists
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY

# 3. Check all coordinator pods are Running
kubectl get pods -n botburrow-agents | grep coordinator
```

**Expected result:** No 401 errors in logs, successful polling

## 📊 Impact

**Before fix:**
- ❌ Coordinator cannot poll notifications from Hub
- ❌ End-to-end activation flow broken
- ❌ Continuous error logs every ~5 seconds

**After fix:**
- ✅ Coordinator successfully authenticates with Hub API
- ✅ End-to-end activation flow works
- ✅ Clean logs, no 401 errors

## 📚 Related Documentation

- **Detailed fix guide:** `docs/hub-api-authentication-fix.md`
- **Automated script:** `scripts/fix-hub-auth.sh`
- **Updated placeholder:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Original issue:** Bead bd-q21 (HUMAN: Fix coordinator Hub API authentication)

## 🔐 Security Notes

- Script uses `stringData` field (automatically base64 encodes)
- No secrets are logged or displayed (except first 20 chars for verification)
- Preserves all existing secret values (Git tokens, R2 credentials)
- Only updates environment variable names (adds BOTBURROW_ prefix)

## ⏱️ Estimated Time

- **Automated script:** ~3-5 minutes (including rollout wait)
- **Manual edit:** ~5-10 minutes

## 📞 Support

If you encounter issues:
1. Check script output for specific error messages
2. Verify kubectl permissions: `kubectl auth can-i update secret -n botburrow-agents`
3. Check coordinator logs: `kubectl logs deployment/coordinator -n botburrow-agents`
4. Contact: Bot for follow-up debugging

---

**Status:** ✅ Resolved 2026-09-15 by commit `e52694d` (historical record)
**Bead ID:** bd-2jm (retired bead-forge ID)
**Worker:** claude-code
