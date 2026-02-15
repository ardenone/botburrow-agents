# Cluster-Admin Action Required: Hub API Authentication Fix

**Bead:** bd-2sp
**Status:** ⏸️ BLOCKED - Requires cluster-admin permissions
**Priority:** HIGH (end-to-end activation flow broken)
**Estimated Time:** 5-10 minutes

---

## 🚨 Problem Summary

The coordinator deployment in **apexalgo-iad cluster** is experiencing **continuous 401 Unauthorized errors** when polling the Hub API. This completely breaks the end-to-end activation flow.

**Error Rate:** Every ~5 seconds
**Impact:** Hub API polling completely non-functional
**Root Cause:** Secret key naming mismatch (confirmed)

---

## 🔍 Root Cause

**Environment variable naming mismatch:**
- **Secret currently has:** `HUB_API_KEY` (without BOTBURROW_ prefix)
- **Application expects:** `BOTBURROW_HUB_API_KEY` (with BOTBURROW_ prefix)

The `config.py` specifies `env_prefix="BOTBURROW_"` which means all environment variables must be prefixed with `BOTBURROW_` to be recognized by the Settings model.

---

## ✅ What Workers Have Completed

1. ✅ **Root cause analysis** - Identified secret key naming mismatch
2. ✅ **Automated fix script** - Created `scripts/fix-hub-auth.sh`
3. ✅ **Comprehensive documentation** - Created `docs/hub-api-authentication-fix.md`
4. ✅ **Updated placeholder manifest** - `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
5. ✅ **Verification steps** - Documented in detail
6. ✅ **All changes committed to git**

---

## 🚫 Why Workers Cannot Complete

**Permission Boundary:**
- Workers run with `devpod-observer` service account (read-only)
- Secret editing requires elevated permissions
- Verification: `kubectl auth can-i update secrets -n botburrow-agents` → **no**

---

## 🛠️ How to Apply the Fix

### Prerequisites
1. **Cluster-admin kubeconfig** for apexalgo-iad cluster
2. **Valid Hub API key** from https://botburrow.ardenone.com/admin

### Option 1: Automated Fix Script (RECOMMENDED - 5 minutes)

```bash
# 1. SSH to machine with cluster-admin access
ssh <machine-with-admin-kubeconfig>

# 2. Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 3. Navigate to workspace (or clone repo if not available)
cd /home/coder/botburrow-agents
# OR: git clone <repo-url> && cd botburrow-agents

# 4. Run automated fix script
./scripts/fix-hub-auth.sh

# The script will:
# - Show current secret keys
# - Ask for confirmation
# - Prompt for Hub API key if needed
# - Update secret with BOTBURROW_ prefixes
# - Restart coordinator deployments
# - Tail logs to verify fix
```

### Option 2: Manual kubectl edit (10 minutes)

```bash
# 1. Set cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 2. Edit secret
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# 3. Change key names (keeping base64 values):
#    OLD:                        NEW:
#    HUB_API_KEY          →      BOTBURROW_HUB_API_KEY
#    R2_ENDPOINT          →      BOTBURROW_R2_ENDPOINT
#    R2_ACCESS_KEY        →      BOTBURROW_R2_ACCESS_KEY
#    R2_SECRET_KEY        →      BOTBURROW_R2_SECRET_KEY
#
# IMPORTANT: Keep FORGEJO_* and GITHUB_* WITHOUT prefix (used by init containers)

# 4. Restart coordinator
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents

# 5. Verify fix
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50
```

---

## ✅ Expected Results After Fix

### 1. No 401 Errors in Logs
```bash
kubectl logs deployment/coordinator -n botburrow-agents --tail=50
# Should NOT show: "401 Unauthorized"
# Should show: Successful polling or connection messages
```

### 2. Environment Variable Set
```bash
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
# Should show: BOTBURROW_HUB_API_KEY=<value>
```

### 3. All Pods Running
```bash
kubectl get pods -n botburrow-agents | grep coordinator
# All should be: Running (1/1 READY)
```

---

## 📚 Documentation Reference

- **This checklist:** `docs/cluster-admin/bd-2sp-hub-auth-fix.md`
- **Comprehensive fix guide:** `docs/hub-api-authentication-fix.md`
- **Fix script:** `scripts/fix-hub-auth.sh`
- **Readiness status:** `docs/bd-2sp-ready-for-human.md`
- **Placeholder manifest:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

---

## 🔒 Security Notes

1. **Hub API Key:** Obtain from https://botburrow.ardenone.com/admin (requires admin access)
2. **Never commit actual secrets** - Only commit placeholder files
3. **Production deployment:** Consider using SealedSecrets (see fix guide for details)

---

## 📝 After Completing Fix

1. **Verify logs show no 401 errors** (see Expected Results above)
2. **Update bead status:**
   ```bash
   cd /home/coder/botburrow-agents
   br close bd-2sp --status completed
   br sync --flush-only
   git add .beads/*.jsonl
   git commit -m "chore(bd-2sp): Applied Hub API auth fix - 401 errors resolved

   Applied fix as cluster-admin:
   - Updated secret keys with BOTBURROW_ prefix
   - Restarted coordinator deployments
   - Verified 401 errors resolved

   Co-Authored-By: Cluster Admin <admin@example.com>"
   git push origin main
   ```

3. **Optional:** Consider granting devpod-observer service account secret edit permissions to enable workers to handle similar tasks autonomously (see `docs/hub-api-authentication-fix.md` for RBAC example)

---

## 🆘 Troubleshooting

**Problem: Secret not found**
```bash
kubectl get secret botburrow-agents-secrets -n botburrow-agents
# If not found, create it using placeholder as template
```

**Problem: Pods won't restart**
```bash
kubectl get pods -n botburrow-agents | grep coordinator
kubectl describe pod <pod-name> -n botburrow-agents
# Check for image pull errors, resource constraints, etc.
```

**Problem: Still seeing 401 errors after fix**
```bash
# Verify environment variable is set correctly
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_

# Check if Hub API key is valid
curl -H "Authorization: Bearer YOUR_API_KEY" https://botburrow.ardenone.com/api/v1/health
```

---

## 📞 Contact

- **Issue tracker:** GitHub Issues in botburrow-agents repo
- **Bead system:** Create bead with `--type human` for questions
- **Cluster admin:** Contact team member with apexalgo-iad cluster-admin access
