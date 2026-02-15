# Bead bd-q21: Hub API Authentication Fix - Summary

**Status**: ✅ Root cause identified, fix documented, **BLOCKED on cluster-admin action**
**Blocker**: bd-2jm (CLUSTER-ADMIN: Apply Hub API authentication fix)
**Date**: 2026-02-15
**Worker**: claude-code

---

## Problem

The coordinator was experiencing continuous 401 Unauthorized errors when attempting to poll the Hub API for notifications:

```
[error] poll_error error="Client error '401 Unauthorized' for url
  'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'"
```

This prevented the end-to-end activation flow from working.

---

## Root Cause Analysis

**Environment variable naming mismatch between secret and application code:**

### Secret Configuration (INCORRECT)
```yaml
stringData:
  HUB_API_KEY: "api-key-value"      # ❌ Missing BOTBURROW_ prefix
  R2_ENDPOINT: "https://..."         # ❌ Missing BOTBURROW_ prefix
  R2_ACCESS_KEY: "access-key"        # ❌ Missing BOTBURROW_ prefix
  R2_SECRET_KEY: "secret-key"        # ❌ Missing BOTBURROW_ prefix
```

### Application Configuration (EXPECTED)
```python
# src/botburrow_agents/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOTBURROW_",  # All env vars MUST start with BOTBURROW_
        ...
    )

    hub_api_key: str | None = ...  # Reads from BOTBURROW_HUB_API_KEY
    r2_endpoint: str = ...          # Reads from BOTBURROW_R2_ENDPOINT
    r2_access_key: str = ...        # Reads from BOTBURROW_R2_ACCESS_KEY
    r2_secret_key: str = ...        # Reads from BOTBURROW_R2_SECRET_KEY
```

### Code Flow
```python
# src/botburrow_agents/clients/hub.py
async def _get_client(self) -> httpx.AsyncClient:
    headers = {"Content-Type": "application/json"}
    if self.settings.hub_api_key:  # ← This is None because BOTBURROW_HUB_API_KEY not set
        headers["Authorization"] = f"Bearer {self.settings.hub_api_key}"
    # Request sent WITHOUT Authorization header → 401 Unauthorized
```

---

## Solution Delivered

### 1. Fixed Secret Template
**File**: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

Changed from:
```yaml
stringData:
  HUB_API_KEY: "placeholder-update-me"
  R2_ENDPOINT: "https://..."
  # ... etc
```

To:
```yaml
stringData:
  # CRITICAL: Must use BOTBURROW_ prefix to match config.py env_prefix
  BOTBURROW_HUB_API_KEY: "placeholder-update-me"
  BOTBURROW_R2_ENDPOINT: "https://..."
  BOTBURROW_R2_ACCESS_KEY: "..."
  BOTBURROW_R2_SECRET_KEY: "..."
```

### 2. Comprehensive Fix Documentation
**File**: `docs/hub-api-authentication-fix.md`

Contains:
- Root cause analysis with code references
- Three solution options:
  1. **Automated script** (recommended)
  2. **Manual kubectl edit** (alternative)
  3. **GitOps with SealedSecrets** (production)
- Step-by-step instructions
- Verification procedures
- Prevention guidelines

### 3. Automated Fix Script
**File**: `scripts/fix-hub-auth.sh`

Features:
- ✅ Validates existing secret
- ✅ Migrates old keys to new names with BOTBURROW_ prefix
- ✅ Prompts for Hub API key if missing/placeholder
- ✅ Updates secret in cluster
- ✅ Restarts coordinator deployments
- ✅ Shows verification logs
- ✅ Confirms fix worked (no 401 errors)

Usage:
```bash
export KUBECONFIG=/path/to/apexalgo-iad.kubeconfig
cd /home/coder/botburrow-agents
./scripts/fix-hub-auth.sh
```

### 4. Human Bead Created
**Bead ID**: bd-2jm
**Type**: human
**Priority**: 0 (critical)
**Title**: CLUSTER-ADMIN: Apply Hub API authentication fix

This bead blocks bd-q21 and requires cluster-admin action to:
1. Get valid Hub API key from botburrow-hub admin
2. Run `./scripts/fix-hub-auth.sh` or manually update secret
3. Verify coordinator logs show no 401 errors
4. Test end-to-end flow

---

## Files Changed

```
✅ k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml (updated)
✅ docs/hub-api-authentication-fix.md (new)
✅ scripts/fix-hub-auth.sh (new)
✅ .beads/issues.jsonl (updated - dependency tracking)
```

---

## Commit

**Commit**: `ab88d7e`
**Message**: `fix(bd-q21): Fix Hub API authentication - add BOTBURROW_ prefix to env vars`
**Pushed to**: `origin/main`

---

## What Happens Next

### Immediate Next Step (BLOCKED - Requires Cluster-Admin)
**Bead**: bd-2jm
**Action Required**: Cluster administrator with kubectl access to `botburrow-agents` namespace in `apexalgo-iad` cluster must:

1. **Get Hub API Key**
   - Access botburrow-hub admin interface
   - Or retrieve from existing botburrow-hub deployment secrets

2. **Apply Fix** (choose one):
   - **Option 1 (Recommended)**: Run `./scripts/fix-hub-auth.sh`
   - **Option 2**: Manually update secret with `kubectl edit`
   - **Option 3**: Create SealedSecret for GitOps

3. **Verify Fix**
   ```bash
   # Should see NO 401 errors
   kubectl logs -f deployment/coordinator -n botburrow-agents

   # Should show BOTBURROW_HUB_API_KEY set
   kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
   ```

### After Fix Applied
Once bd-2jm is resolved:
- ✅ Coordinator will authenticate successfully with Hub API
- ✅ End-to-end activation flow will work
- ✅ bd-q21 can be closed as completed
- ✅ Parent bead bd-3qv (agent runner pool scaling) can proceed

---

## Technical Details

### Environment Variable Mapping

| Secret Key (OLD) | Secret Key (NEW) | Settings Field | Required |
|------------------|------------------|----------------|----------|
| `HUB_API_KEY` | `BOTBURROW_HUB_API_KEY` | `hub_api_key` | ✅ Yes |
| `R2_ENDPOINT` | `BOTBURROW_R2_ENDPOINT` | `r2_endpoint` | ✅ Yes |
| `R2_ACCESS_KEY` | `BOTBURROW_R2_ACCESS_KEY` | `r2_access_key` | ✅ Yes |
| `R2_SECRET_KEY` | `BOTBURROW_R2_SECRET_KEY` | `r2_secret_key` | ✅ Yes |
| `FORGEJO_USER` | `FORGEJO_USER` | N/A (init container) | No |
| `FORGEJO_TOKEN` | `FORGEJO_TOKEN` | N/A (init container) | No |
| `GITHUB_USER` | `GITHUB_USER` | N/A (init container) | No |
| `GITHUB_TOKEN` | `GITHUB_TOKEN` | N/A (init container) | No |

### Why This Happened

The `pydantic-settings` library's `env_prefix` configuration:
- Automatically prepends prefix to all field names when reading environment
- `hub_api_key` field → looks for `BOTBURROW_HUB_API_KEY` env var
- If not found, uses default value (`None`)
- Code path: `if self.settings.hub_api_key:` → False → no Authorization header

### Prevention for Future

1. ✅ **Template updated** - New secrets will have correct naming
2. 📝 **Documentation** - Clear explanation of env_prefix requirement
3. 🔍 **Consider**: Add startup validation in coordinator to fail fast if required env vars missing
4. 🔍 **Consider**: Add deployment health check that verifies Hub API connectivity

---

## Related Beads

- **bd-q21** (this bead): HUMAN: Fix coordinator Hub API authentication (401 errors) - OPEN (blocked by bd-2jm)
- **bd-2jm** (blocker): CLUSTER-ADMIN: Apply Hub API authentication fix - OPEN (requires human action)
- **bd-3qv** (parent): Test agent runner pool scaling - OPEN (waiting for bd-q21)

---

## Quick Reference

### For Cluster Admins
```bash
# Quick fix (recommended)
export KUBECONFIG=/path/to/apexalgo-iad.kubeconfig
cd /home/coder/botburrow-agents
./scripts/fix-hub-auth.sh

# Verify
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50
```

### For Developers
- **Secret template**: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Config definition**: `src/botburrow_agents/config.py`
- **Hub client**: `src/botburrow_agents/clients/hub.py`
- **Fix guide**: `docs/hub-api-authentication-fix.md`

### For Debugging
```bash
# Check current secret keys
kubectl get secret botburrow-agents-secrets -n botburrow-agents -o json | jq '.data | keys'

# Check coordinator env vars
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW

# Check coordinator logs
kubectl logs deployment/coordinator -n botburrow-agents --tail=100 | grep -i "401\|auth\|unauthorized"
```

---

## Lessons Learned

1. **Environment variable prefixes matter** - pydantic-settings env_prefix must match secret keys
2. **RBAC limitations** - devpod-observer can read pods/logs but not secrets or exec
3. **Long-poll errors are subtle** - 401 errors looked like connectivity issues initially
4. **Documentation is critical** - Comprehensive docs help cluster admins fix issues quickly
5. **Automation saves time** - Fix script reduces manual error and speeds resolution

---

## Status Summary

| Item | Status |
|------|--------|
| Root cause identified | ✅ Complete |
| Fix documented | ✅ Complete |
| Fix script created | ✅ Complete |
| Secret template updated | ✅ Complete |
| Changes committed & pushed | ✅ Complete |
| Human bead created | ✅ Complete (bd-2jm) |
| Dependency tracked | ✅ Complete (bd-q21 → bd-2jm) |
| **Fix applied to cluster** | ⏳ **PENDING (requires cluster-admin)** |
| **Verification** | ⏳ **PENDING (after fix applied)** |
| **End-to-end test** | ⏳ **PENDING (after fix applied)** |

---

## Contact & Support

- **Fix documentation**: `docs/hub-api-authentication-fix.md`
- **Bead tracking**: bd-q21 (this bead), bd-2jm (blocker)
- **Cluster**: apexalgo-iad
- **Namespace**: botburrow-agents
