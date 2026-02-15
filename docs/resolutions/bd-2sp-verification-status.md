# Bead bd-2sp: Hub API Auth Fix - Verification Status

## Current Status: READY FOR HUMAN EXECUTION

**Date:** 2026-02-15
**Bead:** bd-2sp (HUMAN: Apply Hub API auth fix)
**Worker:** claude-code
**Workspace:** /home/coder/botburrow-agents

## Summary

All preparation work is complete. The Hub API authentication fix is documented and scripted, but requires cluster-admin permissions to apply. The devpod-observer service account has read-only access and cannot edit secrets.

## Verification Checklist

### ✅ Documentation Prepared
- [x] Comprehensive fix guide created: `docs/hub-api-authentication-fix.md`
- [x] Root cause documented (env var naming mismatch)
- [x] Multiple solution options provided
- [x] Verification steps documented

### ✅ Automated Fix Script Ready
- [x] Script created: `scripts/fix-hub-auth.sh`
- [x] Script is executable (chmod +x applied)
- [x] Script includes safety checks
- [x] Script validates existing values
- [x] Script prompts for Hub API key if needed
- [x] Script automates restart and verification

### ✅ Prerequisites Documented
- [x] Required permissions identified (cluster-admin or secret edit)
- [x] Required inputs listed (Hub API key)
- [x] Access methods documented (kubeconfig path)

### ❌ Permissions Verified
```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl auth can-i update secrets -n botburrow-agents
no
```

**Reason:** devpod-observer service account has read-only access only.

## Ready for Human Execution

### Option 1: Automated Script (RECOMMENDED)

**Requirements:**
1. Access to machine with cluster-admin kubeconfig for apexalgo-iad
2. Valid Hub API key from https://botburrow.ardenone.com/admin

**Execution Steps:**
```bash
# SSH to machine with cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Navigate to workspace
cd /home/coder/botburrow-agents

# Run automated fix script
./scripts/fix-hub-auth.sh

# Script will:
# 1. Show current secret keys
# 2. Ask for confirmation
# 3. Prompt for Hub API key if needed (or use existing)
# 4. Update secret with BOTBURROW_ prefixes
# 5. Restart coordinator deployments
# 6. Tail logs to verify fix
```

**Expected Result:**
- No more 401 Unauthorized errors in coordinator logs
- Coordinator successfully polls Hub API
- End-to-end activation flow works

### Option 2: Manual kubectl edit

**Steps:**
```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Edit secret
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# Change key names (keeping base64 values):
# HUB_API_KEY → BOTBURROW_HUB_API_KEY
# R2_ENDPOINT → BOTBURROW_R2_ENDPOINT
# R2_ACCESS_KEY → BOTBURROW_R2_ACCESS_KEY
# R2_SECRET_KEY → BOTBURROW_R2_SECRET_KEY

# Restart coordinator
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents
```

## Verification After Fix

Run these commands to verify the fix worked:

```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 1. Check environment variables are set correctly
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
# Should show: BOTBURROW_HUB_API_KEY=<your-key>

# 2. Check coordinator logs for successful polling (no 401 errors)
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50
# Should see: [info] poll_success assignments_count=X
# Should NOT see: 401 Unauthorized errors

# 3. Check all coordinator pods are running
kubectl get pods -n botburrow-agents | grep coordinator
# All should be Running with 1/1 or 2/2 ready
```

## Root Cause Summary

**Problem:**
- Secret contained: `HUB_API_KEY` (without BOTBURROW_ prefix)
- Application expected: `BOTBURROW_HUB_API_KEY` (with BOTBURROW_ prefix)

**Reason:**
The `config.py` Settings model uses `env_prefix="BOTBURROW_"`, which requires all environment variables to be prefixed with `BOTBURROW_` to be recognized.

**Evidence:**
- ✅ Verified 401 errors in coordinator logs
- ✅ Confirmed secret naming mismatch
- ✅ Validated fix approach

## Next Steps

1. **HUMAN ACTION REQUIRED:** Access machine with cluster-admin kubeconfig
2. **HUMAN ACTION REQUIRED:** Get valid Hub API key from botburrow-hub admin
3. **HUMAN ACTION REQUIRED:** Run `./scripts/fix-hub-auth.sh` (Option 1 recommended)
4. **VERIFY:** Check logs show successful polling
5. **CLOSE BEAD:** Mark bd-2sp as completed after verification

## Related Beads
- bd-2jm: CLUSTER-ADMIN: Apply Hub API authentication fix (parent/blocker)
- This bead (bd-2sp) is the human-facing version of bd-2jm

## Files Modified/Created
- ✅ `docs/hub-api-authentication-fix.md` - Comprehensive fix guide
- ✅ `scripts/fix-hub-auth.sh` - Automated fix script (executable)
- ✅ `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml` - Updated with correct prefixes
- ✅ `docs/resolutions/bd-2sp-verification-status.md` - This file

## Worker Notes

This bead is correctly marked as requiring HUMAN input. All preparation work is complete. The fix is straightforward but requires cluster-admin permissions that the devpod-observer service account does not have.

The human should be able to execute the fix in under 5 minutes using the automated script.
