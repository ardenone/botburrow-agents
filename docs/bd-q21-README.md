# Hub API Authentication Fix - Quick Start — SUPERSEDED, DO NOT FOLLOW

> **⛔ SUPERSEDED — historical record only.** The incident below was resolved
> on the manifest side (commit `e52694d`, 2026-09-15); the "quick fix" of
> running `scripts/fix-hub-auth.sh` is gone — the script was deleted on
> 2026-09-16 because its `kubectl apply` of the Secret and `kubectl rollout
> restart` of the coordinator deployments are live mutations of
> ArgoCD-managed resources that `selfHeal` reverts, which the GitOps rule
> forbids. See
> [incidents/ACTION-REQUIRED-hub-auth-fix.md](incidents/ACTION-REQUIRED-hub-auth-fix.md).
>
> **The only secret rotation path is the manifest-side SealedSecret flow in
> [GITOPS_DEPLOYMENT.md § Secrets Management](GITOPS_DEPLOYMENT.md#secrets-management)**
> (helper: `k8s/apexalgo-iad/scripts/create-sealedsecret.sh`).
>
> Bead IDs (`bd-q21`, `bd-2jm`) are from the retired bead-forge backend,
> kept for provenance only.

**Bead**: bd-q21
**Status**: ✅ Root cause identified, fix ready, **BLOCKED on cluster-admin**
**Blocker**: bd-2jm
**Date**: 2026-02-15

---

## 🚨 TL;DR - For Cluster Admins

The coordinator has **401 errors** polling Hub API. **Root cause**: Secret uses `HUB_API_KEY` but code expects `BOTBURROW_HUB_API_KEY`.

**~~Quick Fix (5 minutes)~~ — resolved on the manifest side; the script no longer exists.** Rotation now goes through the SealedSecret manifest (see banner above).

---

## 📋 What's Included

### 1. Automated Fix Script — deleted 2026-09-16
**File**: `scripts/fix-hub-auth.sh` (deleted — see banner)
**What it did**:
- Migrates secret keys from `HUB_API_KEY` → `BOTBURROW_HUB_API_KEY`
- Prompts for Hub API key if missing
- Restarts coordinator
- Shows verification logs

**Usage**: none — there is nothing to run. Rotation goes through the
SealedSecret manifest per the banner above.

### 2. Comprehensive Documentation ✅
**File**: `docs/hub-api-authentication-fix.md`
**Contents**:
- Root cause analysis with code references
- 3 solution options (script, manual, GitOps)
- Step-by-step instructions
- Verification procedures
- Prevention guidelines

### 3. Fixed Secret Template ✅
**File**: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
**Changes**:
- `HUB_API_KEY` → `BOTBURROW_HUB_API_KEY`
- `R2_ENDPOINT` → `BOTBURROW_R2_ENDPOINT`
- Added comments explaining BOTBURROW_ prefix requirement

### 4. Complete Summary ✅
**File**: `docs/bd-q21-summary.md`
**Contents**:
- Technical deep-dive
- Environment variable mapping table
- Code flow analysis
- Lessons learned
- Quick reference commands

---

## 🎯 Next Steps

### For Cluster Administrators
1. **Get Hub API Key**
   - From botburrow-hub admin: https://botburrow.ardenone.com/admin
   - Or from existing botburrow-hub deployment

2. **~~Run Fix Script~~** — superseded; rotate via the SealedSecret manifest instead (see banner)

3. **Verify**
   ```bash
   # Should see NO 401 errors
   kubectl logs -f deployment/coordinator -n botburrow-agents
   ```

4. **Resolve Bead**
   ```bash
   # After verification succeeds
   br close bd-2jm --status completed --resolution "Applied fix via script, coordinator now authenticating successfully"
   ```

### For Developers
No action needed - fix is documented and ready for cluster-admin.

---

## 📚 Documentation Links

| Document | Purpose | Audience |
|----------|---------|----------|
| ~~fix-hub-auth.sh~~ (deleted 2026-09-16) | Automated fix script — superseded by the GITOPS_DEPLOYMENT.md SealedSecret flow | Cluster admins |
| [hub-api-authentication-fix.md](hub-api-authentication-fix.md) | Comprehensive guide | All |
| [bd-q21-summary.md](bd-q21-summary.md) | Technical deep-dive | Developers |
| [bd-q21-README.md](bd-q21-README.md) | Quick start (this file) | All |

---

## 🔍 Quick Diagnostics

### Check if fix is needed:
```bash
# See 401 errors?
kubectl logs deployment/coordinator -n botburrow-agents --tail=50 | grep 401

# Check current secret keys
kubectl get secret botburrow-agents-secrets -n botburrow-agents -o json | jq '.data | keys'
```

### After applying fix:
```bash
# Should show BOTBURROW_HUB_API_KEY
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY

# Should see successful polling
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=20
```

---

## 🐛 Root Cause (Short Version)

**Problem**: Coordinator sends Hub API requests without Authorization header

**Why**:
- Code expects env var `BOTBURROW_HUB_API_KEY` (with prefix)
- Secret provides `HUB_API_KEY` (without prefix)
- Variable not found → `None` → no Authorization header → 401

**Fix**: Rename secret keys to include `BOTBURROW_` prefix

**Code Reference**:
```python
# config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOTBURROW_",  # ← All vars need this prefix!
    )
    hub_api_key: str | None = ...  # Becomes BOTBURROW_HUB_API_KEY
```

---

## 📞 Support

- **Bead tracking**: bd-q21 (this bead), bd-2jm (blocker)
- **Cluster**: apexalgo-iad
- **Namespace**: botburrow-agents
- **Issue**: https://github.com/ardenone/botburrow-agents (create issue if needed)

---

## ✅ Checklist

- [x] Root cause identified
- [x] Fix script created
- [x] Documentation written
- [x] Secret template updated
- [x] Changes committed & pushed
- [x] Human bead created (bd-2jm)
- [x] Dependency tracked
- [ ] **Fix applied to cluster** ← WAITING ON CLUSTER-ADMIN
- [ ] Verification complete
- [ ] End-to-end test passed
- [ ] Beads closed (bd-2jm, bd-q21)

---

**Last Updated**: 2026-02-15
**Worker**: claude-code
**Commits**: ab88d7e, 644e4a0
