# 🚨 ACTION REQUIRED: Apply Hub API Authentication Fix

**Status:** Ready for human action (requires cluster-admin)
**Priority:** High - Blocking end-to-end activation flow
**Estimated Time:** 5-10 minutes
**Date Created:** 2026-02-15

---

## Problem Summary

The coordinator deployment in **apexalgo-iad** cluster is experiencing continuous **401 Unauthorized errors** when polling the Hub API. This prevents the end-to-end activation flow from working.

**Current Error (continuous):**
```
[error] poll_error error="Client error '401 Unauthorized' for url
  'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'"
```

**Root Cause (Confirmed):**
- Secret contains: `HUB_API_KEY` (without BOTBURROW_ prefix)
- Application expects: `BOTBURROW_HUB_API_KEY` (with BOTBURROW_ prefix)

---

## ✅ RECOMMENDED: Automated Fix Script

### Prerequisites

1. **SSH access** to machine with cluster-admin kubeconfig for apexalgo-iad
2. **Valid Hub API key** - Get from:
   - Hub admin interface: https://botburrow.ardenone.com/admin
   - Or retrieve from existing botburrow-hub deployment

### Steps

```bash
# 1. SSH to machine with cluster-admin access
ssh user@your-admin-machine

# 2. Export cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 3. Verify connectivity
kubectl get pods -n botburrow-agents

# 4. Clone repo (if not already present)
git clone https://github.com/yourusername/botburrow-agents.git
cd botburrow-agents

# 5. Run automated fix script
./scripts/fix-hub-auth.sh
```

### What the Script Does

1. ✅ Shows current secret keys and values (first 20 chars)
2. ✅ Asks for confirmation before proceeding
3. ✅ Prompts for Hub API key if missing or placeholder
4. ✅ Updates secret with correct `BOTBURROW_` prefixes
5. ✅ Restarts coordinator deployments
6. ✅ Tails logs to verify fix (checks for 401 errors)

### Expected Output

```
=================================================================
Hub API Authentication Fix
=================================================================

Current secret keys (showing first 20 chars of values):
HUB_API_KEY: placeholder-update-m...
R2_ENDPOINT: https://s3.example....
...

Do you want to update the secret with BOTBURROW_ prefixes? (yes/no): yes

Updating secret...
✅ Secret updated successfully!

Updated keys:
BOTBURROW_HUB_API_KEY
BOTBURROW_R2_ACCESS_KEY
BOTBURROW_R2_ENDPOINT
BOTBURROW_R2_SECRET_KEY
FORGEJO_TOKEN
FORGEJO_USER
GITHUB_TOKEN
GITHUB_USER

Restart coordinator to apply changes? (yes/no): yes

Restarting coordinator deployments...
deployment.apps/coordinator restarted
deployment.apps/coordinator-git-sync restarted

Waiting for rollout to complete...
deployment "coordinator" successfully rolled out
deployment "coordinator-git-sync" successfully rolled out

✅ Coordinator restarted successfully!

Checking logs for 401 errors (will tail for 30 seconds)...
[info] poll_success assignments_count=0
[info] poll_success assignments_count=0

If you don't see 401 errors above, the fix is working! ✅
```

---

## Alternative: Manual kubectl edit

If you prefer manual editing:

```bash
# 1. Export kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Edit secret
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# 3. Change key names (keeping base64 values unchanged):
#    OLD → NEW
#    HUB_API_KEY → BOTBURROW_HUB_API_KEY
#    R2_ENDPOINT → BOTBURROW_R2_ENDPOINT
#    R2_ACCESS_KEY → BOTBURROW_R2_ACCESS_KEY
#    R2_SECRET_KEY → BOTBURROW_R2_SECRET_KEY

# 4. Save and exit

# 5. Restart coordinator
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents

# 6. Verify
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50
# Should see: [info] poll_success assignments_count=X
# Should NOT see: 401 Unauthorized errors
```

---

## Verification Steps

After applying the fix:

```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 1. Check environment variable is set
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
# Expected: BOTBURROW_HUB_API_KEY=your-actual-key

# 2. Check for 401 errors (should be NONE)
kubectl logs deployment/coordinator -n botburrow-agents --tail=50 | grep -i "401\|unauthorized"
# Expected: No output (no 401 errors)

# 3. Check for successful polling
kubectl logs deployment/coordinator -n botburrow-agents --tail=50 | grep poll_success
# Expected: [info] poll_success assignments_count=X

# 4. Verify all coordinator pods are healthy
kubectl get pods -n botburrow-agents | grep coordinator
# Expected: All pods Running and Ready (1/1 or 2/2)
```

---

## Files Involved

- **Automated fix script:** `scripts/fix-hub-auth.sh`
- **Comprehensive documentation:** `docs/hub-api-authentication-fix.md`
- **Updated placeholder:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Config definition:** `src/botburrow_agents/config.py` (env_prefix="BOTBURROW_")
- **Hub client:** `src/botburrow_agents/clients/hub.py` (uses settings.hub_api_key)

---

## Why This Happened

The `config.py` file specifies `env_prefix="BOTBURROW_"` which means **all environment variables must be prefixed with `BOTBURROW_`** to be recognized by the Settings model:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOTBURROW_",  # ← All env vars must start with BOTBURROW_
        ...
    )
    hub_api_key: str | None = Field(default=None, ...)  # Becomes BOTBURROW_HUB_API_KEY
```

---

## Long-term Solution (Optional)

Consider granting `devpod-observer` service account **secret edit permissions** in the `botburrow-agents` namespace to enable automated fixes from devpods:

```yaml
# Apply this to enable automated cluster-admin tasks from devpods
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

**Security Consideration:** This grants write access to secrets - evaluate based on your security requirements.

---

## Questions or Issues?

- **Bead ID:** bd-2sp (HUMAN: Apply Hub API auth fix)
- **Workspace:** /home/coder/botburrow-agents
- **Documentation:** `docs/hub-api-authentication-fix.md`
- **Fix Script:** `scripts/fix-hub-auth.sh`

---

## Next Steps After Fix

Once the fix is applied and verified:

1. ✅ Confirm 401 errors are gone
2. ✅ Test end-to-end activation flow
3. ✅ Update this bead status: `br close bd-2sp --status completed`
4. ✅ Commit changes: `git add . && git commit -m "docs: Mark Hub API auth fix as completed"`

---

**Status:** Waiting for human with cluster-admin access to apply fix
**Last Updated:** 2026-02-15
