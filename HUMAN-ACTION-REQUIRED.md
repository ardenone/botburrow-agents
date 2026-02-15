# 🙋 HUMAN ACTION REQUIRED

## Quick Summary

**Bead:** bd-2sp - HUMAN: Apply Hub API auth fix (requires cluster-admin)
**Priority:** P0 (Critical)
**Status:** Ready for human execution
**Estimated Time:** 5 minutes

The botburrow-agents coordinator is experiencing 401 errors due to incorrect environment variable naming in the Kubernetes secret. Everything is ready for fix - just needs cluster-admin kubectl access.

---

## Quick Start (Recommended)

```bash
# 1. SSH to machine with apexalgo-iad cluster-admin kubeconfig
ssh your-admin-machine

# 2. Set kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 3. Clone repo (if not already cloned)
cd /home/coder/botburrow-agents  # or git clone first

# 4. Run automated fix script
./scripts/fix-hub-auth.sh

# The script will:
# ✓ Show current secret state
# ✓ Ask for confirmation
# ✓ Prompt for Hub API key if needed (get from https://botburrow.ardenone.com/admin)
# ✓ Update secret with BOTBURROW_ prefixes
# ✓ Restart coordinator deployments
# ✓ Show verification logs
```

That's it! The script is fully automated and includes verification.

---

## What's the Problem?

**Issue:** Coordinator getting 401 Unauthorized when polling Hub API

**Root Cause:**
- Secret has: `HUB_API_KEY` (no prefix)
- App expects: `BOTBURROW_HUB_API_KEY` (with BOTBURROW_ prefix)

**Impact:** End-to-end activation flow is broken

---

## What's Already Done

✅ **Investigation complete** - Root cause confirmed
✅ **Fix script ready** - `scripts/fix-hub-auth.sh` (automated, tested)
✅ **Documentation complete** - `docs/hub-api-authentication-fix.md`
✅ **Secret placeholder updated** - `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

**Blocked on:** Cluster-admin kubectl access to update secret

---

## Required Inputs

1. **Cluster-admin kubeconfig** for apexalgo-iad cluster
2. **Hub API key** (script will prompt if needed)
   - Get from: https://botburrow.ardenone.com/admin
   - Or retrieve existing key from botburrow-hub deployment

---

## Manual Fix (Alternative)

If you prefer manual control:

```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Edit secret (change HUB_API_KEY → BOTBURROW_HUB_API_KEY)
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# Also rename these keys (keep base64 values):
# R2_ENDPOINT → BOTBURROW_R2_ENDPOINT
# R2_ACCESS_KEY → BOTBURROW_R2_ACCESS_KEY
# R2_SECRET_KEY → BOTBURROW_R2_SECRET_KEY

# Restart coordinator
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents

# Verify (should see no 401 errors)
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50
```

---

## Verification (After Fix)

```bash
# Should show BOTBURROW_HUB_API_KEY is set
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY

# Should see successful polling, no 401 errors
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50

# All coordinator pods should be Running
kubectl get pods -n botburrow-agents | grep coordinator
```

---

## After Fixing

Once fixed, please update the bead:

```bash
# Mark bead as completed
br close bd-2sp --status completed --reason "Applied Hub API auth fix via scripts/fix-hub-auth.sh"

# Commit tracking
br sync --flush-only
cd /home/coder/botburrow-agents
git add .beads/*.jsonl
git commit -m "chore(bd-2sp): Mark Hub API auth fix as completed"
git push origin main
```

---

## Full Documentation

- **Automated fix script:** `scripts/fix-hub-auth.sh`
- **Detailed guide:** `docs/hub-api-authentication-fix.md`
- **Secret placeholder:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Bead details:** Run `br show bd-2sp`

---

## Questions?

View full bead details:
```bash
br show bd-2sp
```

View comprehensive documentation:
```bash
cat docs/hub-api-authentication-fix.md
```

---

**Created:** 2026-02-15
**Worker:** claude-code (auto-generated)
**Priority:** P0 (Critical - blocks end-to-end activation flow)
