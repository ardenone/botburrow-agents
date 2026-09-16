# 🚨 HUMAN ACTION REQUIRED: bd-2sp — RESOLVED, DO NOT ACT ON THIS

> **✅ RESOLVED — historical record only. Nothing here needs doing.** The
> outage was fixed on the manifest side (commit `e52694d`, 2026-09-15); see
> [docs/incidents/ACTION-REQUIRED-hub-auth-fix.md](docs/incidents/ACTION-REQUIRED-hub-auth-fix.md).
>
> The fix path below is gone: `scripts/fix-hub-auth.sh` was deleted on
> 2026-09-16 because its `kubectl apply` of the Secret and `kubectl rollout
> restart` of the coordinator deployments are live mutations of
> ArgoCD-managed resources that `selfHeal` reverts — exactly what the GitOps
> rule forbids. **The only secret rotation path is the manifest-side
> SealedSecret flow in
> [docs/GITOPS_DEPLOYMENT.md § Secrets Management](docs/GITOPS_DEPLOYMENT.md#secrets-management)**
> (helper: `k8s/apexalgo-iad/scripts/create-sealedsecret.sh`).
>
> Bead IDs (`bd-2sp`, `bd-2jm`) are from the retired bead-forge backend,
> kept for provenance only.

**Status:** ~~Ready for cluster-admin execution~~ → RESOLVED 2026-09-15 (historical record)
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

### ~~Apply Fix~~ — historical; the script and this live-mutation path no longer exist

The 2026-02-15 procedure (SSH to an admin machine, export a cluster-admin
kubeconfig, run `./scripts/fix-hub-auth.sh`, confirm its prompts) described a
live secret edit plus pod restarts — both forbidden under the GitOps rule
today. Rotation happens through the SealedSecret manifest; see the banner
above.

### Verify Fix

```bash
# Should show no 401 errors
kubectl logs deployment/coordinator -n botburrow-agents --tail=50

# Should show BOTBURROW_HUB_API_KEY is set
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
```

### ~~Mark Complete~~ — done; nothing to run

The fix was applied on the manifest side (commit `e52694d`, 2026-09-15) and
the bead was closed. The historical block below is also obsolete as syntax:
`br` is the retired bead-forge CLI (the current CLI is `bead`), and bead
state lives in `.beads/checkpoint/`, published automatically after each
mutation — it is not staged with `git add .beads/*.jsonl`.

```bash
# historical (2026-02-15) — do not run
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

## ~~Alternative: Manual Fix (10 minutes)~~ — forbidden under the GitOps rule

The historical manual variant — `kubectl edit secret botburrow-agents-secrets`
followed by `kubectl rollout restart` of the coordinator deployments — is not
available any more, not merely discouraged: the live Secret is owned by the
SealedSecret manifest in an ArgoCD-managed namespace, so that edit is drift
`selfHeal` reverts and a GitOps violation regardless. There is no
manual-kubectl variant of this fix.

---

## Complete Documentation

- **Readiness check:** `docs/bd-2sp-ready-for-human.md`
- **Comprehensive guide:** `docs/hub-api-authentication-fix.md`
- **Fix script:** `scripts/fix-hub-auth.sh` (deleted 2026-09-16 — see banner)
- **Placeholder:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

---

## Questions?

If you have questions or need assistance:
1. Review the comprehensive guide: `docs/hub-api-authentication-fix.md`
2. Check the readiness document: `docs/bd-2sp-ready-for-human.md`
3. Contact cluster administrator if you don't have cluster-admin access

---

**This file will be at the repository root for easy visibility when you access the repo.**
