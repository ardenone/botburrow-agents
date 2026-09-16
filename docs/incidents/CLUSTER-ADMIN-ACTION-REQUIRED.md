# CLUSTER-ADMIN ACTION REQUIRED: Hub API Authentication Fix — RESOLVED, historical record

> **✅ RESOLVED — historical incident record. Nothing here needs doing.**
>
> The secret-key mismatch described below was fixed on the manifest side in
> commit `e52694d` ("fix(k8s): align secret key names with BOTBURROW_* env
> contract", 2026-09-15), and the key contract is now enforced by
> `tests/test_secret_manifest_env_contract.py`. No cluster-admin action is
> pending.
>
> The `kubectl edit secret` / `kubectl rollout restart` recipes below are
> also obsolete as recipes: the live secret is owned by the SealedSecret
> manifest and the namespace is ArgoCD-managed, so rotation goes through a
> manifest change (see [GITOPS_DEPLOYMENT.md](../GITOPS_DEPLOYMENT.md)).
> The fix script they pointed at, `scripts/fix-hub-auth.sh`, was **deleted
> on 2026-09-16** — it applied the Secret and restarted the coordinator
> deployments with `kubectl`, which are live mutations of ArgoCD-managed
> resources that `selfHeal` reverts. Do not recreate it; the only rotation
> path is the manifest-side SealedSecret flow in
> [GITOPS_DEPLOYMENT.md § Secrets Management](../GITOPS_DEPLOYMENT.md#secrets-management)
> (helper: `k8s/apexalgo-iad/scripts/create-sealedsecret.sh`).
> Bead IDs (`bd-q21`, `bd-2jm`) are from the retired bead-forge backend,
> kept for provenance only.
>
> What follows is the document as it stood on 2026-02-15.

**Date:** 2026-02-15 (resolved 2026-09-15)
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents
**Priority:** ~~HIGH (blocking end-to-end activation flow)~~ → resolved

## ⚠️ Current Issue

The `coordinator` deployment is experiencing continuous 401 Unauthorized errors when polling the Hub API:

```
[error] poll_error error="Client error '401 Unauthorized' for url 'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'"
```

**Verified:** Logs checked on 2026-02-15 20:16 UTC - 401 errors occurring every ~5 seconds

## 🔍 Root Cause

Environment variable naming mismatch between secret and application:

| Location | Variable Name |
|----------|---------------|
| **Secret contains** | `HUB_API_KEY` (no prefix) |
| **Application expects** | `BOTBURROW_HUB_API_KEY` (with prefix) |

## ~~✅ Solution: Run Automated Fix Script~~ — retired 2026-09-16

> **⛔ This section is kept as history only.** `scripts/fix-hub-auth.sh` was
> deleted on 2026-09-16: it applied the Secret and restarted the coordinator
> deployments with `kubectl`, which are live mutations of ArgoCD-managed
> resources — forbidden under the GitOps rule, and futile besides, since
> `selfHeal` reverts them. Do not recreate it.

### Current rotation path (the only one)

Rotate by regenerating and pushing the SealedSecret, per
[GITOPS_DEPLOYMENT.md § Secrets Management](../GITOPS_DEPLOYMENT.md#secrets-management):

```bash
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
# edit /tmp/botburrow-agents-secret.yml with real values, then:
# (--controller-name is required: the Service here is named for its Helm
#  release, not the upstream default `sealed-secrets`)
kubeseal --format=yaml \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-apexalgo-iad \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
git add k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
git commit -m "feat: update SealedSecret" && git push origin main
```

ArgoCD syncs the SealedSecret, the SealedSecrets controller updates the
Secret, and the rollout happens through the manifest change — no live
`kubectl` mutation. `k8s/apexalgo-iad/scripts/create-sealedsecret.sh`
wraps the same flow.

### Historical record (2026-02-15)

The original steps — export a cluster-admin kubeconfig, run
`./scripts/fix-hub-auth.sh`, confirm the prompts — described a
live-mutation path that no longer exists in the repo. What the script did
at the time:
1. ✅ Shows current secret keys (first 20 chars for safety)
2. ✅ Asks for confirmation before making changes
3. ✅ Extracts current values from secret (supports both old and new key names)
4. ✅ Prompts for Hub API key if missing/placeholder
5. ✅ Updates secret with correct `BOTBURROW_*` prefixes
6. ✅ Restarts coordinator deployments to apply changes
7. ✅ Waits for rollout completion
8. ✅ Tails logs for 30 seconds to verify no more 401 errors

The "Alternative: Manual Fix" of the same date — `kubectl edit secret
botburrow-agents-secrets` plus `kubectl rollout restart` of the
coordinator deployments — is likewise gone: the live Secret is owned by the
SealedSecret manifest, so that edit is drift `selfHeal` reverts and a GitOps
violation regardless. There is no manual-kubectl variant of this fix.

## 🧪 Verification Steps

After applying the fix:

```bash
# 1. Check logs (should NOT see 401 errors)
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50

# 2. Verify environment variable exists
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY

# 3. Check all coordinator pods are Running
kubectl get pods -n botburrow-agents | grep coordinator
```

**Expected result:** No 401 errors in logs, successful polling

## 📊 Impact

**Before fix:**
- ❌ Coordinator cannot poll notifications from Hub
- ❌ End-to-end activation flow broken
- ❌ Continuous error logs every ~5 seconds

**After fix:**
- ✅ Coordinator successfully authenticates with Hub API
- ✅ End-to-end activation flow works
- ✅ Clean logs, no 401 errors

## 📚 Related Documentation

- **Detailed fix guide:** `docs/hub-api-authentication-fix.md` (also a historical record — see its banner)
- **Automated script:** `scripts/fix-hub-auth.sh` (deleted 2026-09-16 — see header)
- **Updated placeholder:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Original issue:** Bead bd-q21 (HUMAN: Fix coordinator Hub API authentication)

## 🔐 Security Notes

Notes on the deleted script, kept for the record:

- Script used `stringData` field (automatically base64 encodes)
- No secrets are logged or displayed (except first 20 chars for verification)
- Preserves all existing secret values (Git tokens, R2 credentials)
- Only updates environment variable names (adds BOTBURROW_ prefix)

The SealedSecret flow replaces this entirely: plaintext values only ever
live in a temporary file outside the repo, and what gets committed is the
kubeseal output.

## ⏱️ Estimated Time

Historical, for the deleted script: ~3-5 minutes (automated), ~5-10 minutes
(manual edit). The manifest-side rotation path takes about the same.

## 📞 Support

If you encounter issues:
1. Verify the SealedSecret synced: `kubectl get sealedsecrets -n botburrow-agents`
2. Verify kubectl read access: `kubectl auth can-i get secret -n botburrow-agents`
3. Check coordinator logs: `kubectl logs deployment/coordinator -n botburrow-agents`
4. Contact: Bot for follow-up debugging

---

**Status:** ✅ Resolved 2026-09-15 by commit `e52694d` (historical record)
**Bead ID:** bd-2jm (retired bead-forge ID)
**Worker:** claude-code
