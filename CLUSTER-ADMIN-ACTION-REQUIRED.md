# CLUSTER-ADMIN ACTION REQUIRED: Hub API Authentication Fix

## Status
🔴 **BLOCKED** - Requires cluster-admin permissions to edit secrets in apexalgo-iad cluster

## Problem
The coordinator is experiencing continuous 401 Unauthorized errors when polling the Hub API at https://botburrow.ardenone.com.

**Root Cause:** Environment variable naming mismatch
- **Secret contains**: `HUB_API_KEY` (without BOTBURROW_ prefix)
- **Application expects**: `BOTBURROW_HUB_API_KEY` (with BOTBURROW_ prefix)

## Current Access Level
The devpod-observer ServiceAccount has **read-only** access and **cannot access secrets**:

```
Error from server (Forbidden): secrets "botburrow-agents-secrets" is forbidden: 
User "system:serviceaccount:devpod-observer:devpod-observer" cannot get resource 
"secrets" in API group "" in the namespace "botburrow-agents"
```

## Required Permissions
To apply this fix, you need:
1. **Cluster-admin** or **namespace-admin** role in apexalgo-iad cluster
2. **Secret edit permissions** in botburrow-agents namespace
3. **Access to Hub API key** (from botburrow-hub admin or https://botburrow.ardenone.com/admin)

## Quick Fix Options

### ✅ Option 1: Automated Fix Script (RECOMMENDED)

**Pros:**
- Automated and safe
- Validates existing values
- Prompts for Hub API key if missing
- Automatically restarts coordinator
- Shows verification logs

**Steps:**
```bash
# 1. Export kubeconfig with cluster-admin permissions
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Run the fix script
cd /home/coder/botburrow-agents
./scripts/fix-hub-auth.sh

# 3. The script will:
#    - Show current secret keys
#    - Ask for confirmation
#    - Prompt for Hub API key if needed
#    - Update secret with BOTBURROW_ prefixes
#    - Restart coordinator deployments
#    - Show verification logs
```

### ⚙️ Option 2: Manual kubectl edit

**Steps:**
```bash
# 1. Export kubeconfig with cluster-admin permissions
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Edit the secret
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# 3. Change key names (keep base64 values):
#    OLD → NEW
#    HUB_API_KEY → BOTBURROW_HUB_API_KEY
#    R2_ENDPOINT → BOTBURROW_R2_ENDPOINT
#    R2_ACCESS_KEY → BOTBURROW_R2_ACCESS_KEY
#    R2_SECRET_KEY → BOTBURROW_R2_SECRET_KEY

# 4. Restart coordinator
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents

# 5. Wait for restart
kubectl rollout status deployment coordinator -n botburrow-agents
kubectl rollout status deployment coordinator-git-sync -n botburrow-agents
```

### 🔒 Option 3: GitOps with SealedSecrets (Best for Production)

See detailed steps in `docs/hub-api-authentication-fix.md`

## Verification After Fix

```bash
# 1. Check coordinator logs (should see no 401 errors)
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50

# 2. Verify environment variable is set correctly
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY

# 3. Check all pods are running
kubectl get pods -n botburrow-agents | grep coordinator
```

## Documentation

- **Full fix guide**: `docs/hub-api-authentication-fix.md`
- **Automated script**: `scripts/fix-hub-auth.sh`
- **Updated placeholder**: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

## Related Beads

- **Original issue**: bd-q21 (HUMAN: Fix coordinator Hub API authentication (401 errors))
- **This action**: bd-2jm (CLUSTER-ADMIN: Apply Hub API authentication fix)

---

**Next Steps:**
1. Get cluster-admin kubeconfig for apexalgo-iad
2. Run `./scripts/fix-hub-auth.sh` (Option 1 - RECOMMENDED)
3. Verify coordinator logs show no 401 errors
4. Close this bead with `br close bd-2jm --status completed`
