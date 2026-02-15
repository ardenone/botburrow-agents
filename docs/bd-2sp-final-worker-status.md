# bd-2sp: Final Worker Status - Ready for Human Execution

**Status:** ✅ ALL PREPARATION COMPLETE - AWAITING HUMAN WITH CLUSTER-ADMIN ACCESS

**Last Updated:** 2026-02-15 19:42 UTC

## Current State Verification (2026-02-15 19:42 UTC)

### ❌ Problem Still Active
- **401 Errors:** Still occurring every ~5 seconds
- **Last verified:** 2026-02-15 19:42:02 UTC
- **Error pattern:** Continuous polling failures to Hub API
- **Impact:** End-to-end activation flow completely broken

```
[2026-02-15T19:42:02.732538Z] [error] poll_error error="Client error '401 Unauthorized'"
[2026-02-15T19:41:57.118903Z] [error] poll_error error="Client error '401 Unauthorized'"
[2026-02-15T19:41:52.571856Z] [error] poll_error error="Client error '401 Unauthorized'"
... (continues every ~5 seconds)
```

### ✅ All Preparation Complete

**What Workers Have Completed:**
1. ✅ Root cause analysis and confirmation
2. ✅ Automated fix script: `scripts/fix-hub-auth.sh`
3. ✅ Comprehensive documentation: `docs/hub-api-authentication-fix.md`
4. ✅ Updated placeholder manifest: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
5. ✅ Human action guide: `docs/bd-2sp-ready-for-human.md`
6. ✅ Verified 401 errors still occurring (2026-02-15 19:42 UTC)
7. ✅ All changes committed to git

### 🚫 Worker Blocker

**Permission Level:** Read-only (`devpod-observer` service account)

```bash
$ kubectl auth can-i update secrets -n botburrow-agents
no

$ kubectl auth can-i get secrets -n botburrow-agents
no
```

**Why Workers Cannot Complete:**
- No access to read or update secrets in `botburrow-agents` namespace
- Cluster-admin or secret edit permissions required
- This is a security boundary that workers cannot cross

## Human Action Required

### Prerequisites
1. **Cluster Access:** Machine with cluster-admin kubeconfig for apexalgo-iad
2. **Hub API Key:** Valid key from https://botburrow.ardenone.com/admin

### Quick Start (5 minutes)

**OPTION 1: Automated Fix Script (RECOMMENDED)**
```bash
# SSH to machine with cluster-admin kubeconfig
ssh <machine-with-admin-access>

# Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# Navigate to workspace (or git clone if not present)
cd /home/coder/botburrow-agents
# OR: git clone <repo> && cd botburrow-agents

# Run the automated fix
./scripts/fix-hub-auth.sh

# The script will:
# 1. Show current secret keys
# 2. Ask for confirmation
# 3. Prompt for Hub API key if needed
# 4. Update secret with BOTBURROW_ prefixes
# 5. Restart coordinator deployments
# 6. Tail logs to verify fix
```

**OPTION 2: Manual Fix (10 minutes)**

See `docs/bd-2sp-ready-for-human.md` for detailed manual steps.

### Verification After Fix

**1. No 401 Errors:**
```bash
kubectl logs deployment/coordinator -n botburrow-agents --tail=50
# Should NOT see: "401 Unauthorized"
# Should see: Successful polling or quiet operation
```

**2. Environment Variable Set:**
```bash
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
# Should show: BOTBURROW_HUB_API_KEY=<value>
```

**3. All Pods Running:**
```bash
kubectl get pods -n botburrow-agents | grep coordinator
# All should be: Running (1/1 or 2/2 READY)
```

### Close Bead After Success

```bash
cd /home/coder/botburrow-agents
br close bd-2sp --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-2sp): Applied Hub API auth fix - 401 errors resolved"
git push origin main
```

## Root Cause Summary

**Environment Variable Mismatch:**
- **Secret contains:** `HUB_API_KEY` (no prefix)
- **Application expects:** `BOTBURROW_HUB_API_KEY` (with prefix)

**Why:** The `config.py` specifies `env_prefix="BOTBURROW_"` which means all settings-based environment variables must have the `BOTBURROW_` prefix to be recognized by Pydantic Settings.

**Code Reference:** `src/botburrow_agents/config.py:25-28`

## Documentation Links

- **This status:** `docs/bd-2sp-final-worker-status.md`
- **Human action guide:** `docs/bd-2sp-ready-for-human.md`
- **Comprehensive fix guide:** `docs/hub-api-authentication-fix.md`
- **Automated fix script:** `scripts/fix-hub-auth.sh`
- **Placeholder manifest:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

## Worker Handoff Complete

All preparation, analysis, scripting, and documentation are complete. The issue is verified as still occurring. The next step requires human intervention with cluster-admin access to execute the fix script or manually update the secret.

**Bead:** bd-2sp
**Worker:** claude-code
**Status:** Blocked on cluster-admin permissions - awaiting human execution
**Next Action:** Human with cluster-admin access runs fix script

---

**Note to Human:** This is not a complex fix - it's simply renaming environment variable keys in a Kubernetes secret. The automated script makes it a 5-minute task. The comprehensive documentation is provided for transparency and future reference, but you don't need to read all 300+ lines to execute the fix. Just run `./scripts/fix-hub-auth.sh` and follow the prompts.
