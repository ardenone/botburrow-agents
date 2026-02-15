# 🚨 HUMAN ACTION REQUIRED: bd-2sp

**Status:** ✅ **ALL PREPARATION COMPLETE** - Ready for cluster-admin execution
**Date:** 2026-02-15
**Bead:** bd-2sp

---

## Executive Summary

The Hub API authentication fix is **100% ready to apply**. All scripts, documentation, and verification steps are complete. The coordinator deployment continues to experience 401 errors every ~5 seconds. **You need cluster-admin access to apply the fix.**

---

## Quick Start (5 minutes)

### Prerequisites
1. Machine with cluster-admin kubeconfig for apexalgo-iad cluster
2. Hub API key from https://botburrow.ardenone.com/admin

### Apply Fix

```bash
# SSH to machine with cluster-admin kubeconfig
ssh <machine-with-admin-access>

# Set cluster-admin kubeconfig for apexalgo-iad
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Clone/pull the repo if needed
cd /path/to/botburrow-agents
git pull origin main

# Run automated fix script
./scripts/fix-hub-auth.sh

# Follow the prompts:
# 1. Review current secret keys
# 2. Confirm update (type "yes")
# 3. Provide Hub API key if prompted
# 4. Confirm coordinator restart (type "yes")
# 5. Watch logs to verify no 401 errors
```

### Verify Fix

```bash
# Should show no 401 errors
kubectl logs deployment/coordinator -n botburrow-agents --tail=50

# Should show BOTBURROW_HUB_API_KEY is set
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
```

### Mark Complete

```bash
cd /home/coder/botburrow-agents
br close bd-2sp --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-2sp): Applied Hub API auth fix - 401 errors resolved"
git push origin main
```

---

## Problem Details

**Issue:** Coordinator experiencing continuous 401 Unauthorized errors when polling Hub API

**Root Cause:** Environment variable naming mismatch
- Secret contains: `HUB_API_KEY` (without prefix)
- Application expects: `BOTBURROW_HUB_API_KEY` (with prefix)

**Impact:** Hub API polling completely broken, end-to-end activation flow not working

**Evidence:** See logs in `docs/bd-2sp-ready-for-human.md` (401 errors every ~5 seconds since 2026-02-15 19:14 UTC)

---

## What Workers Completed ✅

1. ✅ **Created automated fix script:** `scripts/fix-hub-auth.sh`
   - Interactive prompts
   - Validates current state
   - Updates secret with correct prefixes
   - Restarts coordinator
   - Verifies fix

2. ✅ **Comprehensive documentation:** `docs/hub-api-authentication-fix.md`
   - Root cause analysis
   - Multiple fix options
   - Verification steps
   - Prevention measures

3. ✅ **Updated placeholder manifest:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
   - Correct BOTBURROW_ prefixes
   - Template for future deployments

4. ✅ **Verified current state:**
   - Confirmed 401 errors still occurring
   - Confirmed secret naming mismatch
   - Confirmed read-only access prevents fix

---

## Why Workers Cannot Complete ❌

**Current Access:** Read-only via `devpod-observer` service account

**Required Access:** Secret edit permissions in `botburrow-agents` namespace

**Verification:**
```bash
kubectl auth can-i update secrets -n botburrow-agents
# Output: no
```

**Workers can:**
- ✅ Analyze problems
- ✅ Create fix scripts
- ✅ Document solutions
- ✅ Verify current state

**Workers cannot:**
- ❌ Edit Kubernetes secrets
- ❌ Restart deployments
- ❌ Apply RBAC changes

---

## Alternative: Manual Fix (10 minutes)

If you prefer manual execution instead of the script:

```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Edit secret
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# Change key names (keep base64 values):
# HUB_API_KEY → BOTBURROW_HUB_API_KEY
# R2_ENDPOINT → BOTBURROW_R2_ENDPOINT
# R2_ACCESS_KEY → BOTBURROW_R2_ACCESS_KEY
# R2_SECRET_KEY → BOTBURROW_R2_SECRET_KEY

# Restart coordinator
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents

# Verify
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50
```

---

## Complete Documentation

- **Readiness check:** `docs/bd-2sp-ready-for-human.md`
- **Comprehensive guide:** `docs/hub-api-authentication-fix.md`
- **Fix script:** `scripts/fix-hub-auth.sh`
- **Placeholder:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

---

## Questions?

If you have questions or need assistance:
1. Review the comprehensive guide: `docs/hub-api-authentication-fix.md`
2. Check the readiness document: `docs/bd-2sp-ready-for-human.md`
3. Contact cluster administrator if you don't have cluster-admin access

---

**This file will be at the repository root for easy visibility when you access the repo.**
