# Hub API Authentication Fix (401 outage) — RESOLVED, historical record

> **✅ RESOLVED — historical incident record. Nothing here needs doing.**
>
> The key-name mismatch described below was fixed on the manifest side in
> commit `e52694d` ("fix(k8s): align secret key names with BOTBURROW_* env
> contract", 2026-09-15): every secret manifest under `k8s/` now carries the
> `BOTBURROW_` prefix the application actually reads, and the contract is
> enforced by `tests/test_secret_manifest_env_contract.py`, which fails if a
> secret manifest defines a key the coordinator/runner code cannot read.
>
> Two things have also changed since this was written, making the runbook
> below obsolete even as a recipe:
>
> - The `kubectl edit secret` / `kubectl rollout restart` instructions are
>   exactly what the GitOps rule now forbids — the live secret is owned by
>   the SealedSecret manifest, so rotation means regenerating and pushing the
>   SealedSecret (see [GITOPS_DEPLOYMENT.md](../GITOPS_DEPLOYMENT.md)).
> - The fix script this document recommended, `scripts/fix-hub-auth.sh`, was
>   **deleted on 2026-09-16** for that reason: its `kubectl apply` of the
>   Secret and its `kubectl rollout restart` of the coordinator deployments
>   are live mutations of ArgoCD-managed resources that `selfHeal` reverts.
>   Do not recreate it. The only rotation path is the manifest-side
>   SealedSecret flow in
>   [GITOPS_DEPLOYMENT.md § Secrets Management](../GITOPS_DEPLOYMENT.md#secrets-management)
>   (helper: `k8s/apexalgo-iad/scripts/create-sealedsecret.sh`).
> - The bead IDs (`bd-2sp`, `bd-q21`) are from the retired bead-forge
>   backend, kept for provenance only.
>
> What follows is the document as it stood on 2026-02-15.

**Status:** ~~Ready for human action~~ → RESOLVED 2026-09-15 (historical record)
**Priority:** High - Blocking end-to-end activation flow (at the time)
**Estimated Time:** 5-10 minutes
**Date Created:** 2026-02-15

---

## Problem Summary

The coordinator deployment in **apexalgo-iad** cluster is experiencing continuous **401 Unauthorized errors** when polling the Hub API. This prevents the end-to-end activation flow from working.

**Current Error (continuous):**
```
[error] poll_error error="Client error '401 Unauthorized' for url
  'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'"
```

**Root Cause (Confirmed):**
- Secret contains: `HUB_API_KEY` (without BOTBURROW_ prefix)
- Application expects: `BOTBURROW_HUB_API_KEY` (with BOTBURROW_ prefix)

---

## ~~✅ RECOMMENDED: Automated Fix Script~~ — retired 2026-09-16

> **⛔ This section is kept as history only.** `scripts/fix-hub-auth.sh` was
> deleted on 2026-09-16: it applied the Secret and restarted the coordinator
> deployments with `kubectl`, which are live mutations of ArgoCD-managed
> resources — forbidden under the GitOps rule, and futile besides, since
> `selfHeal` reverts them. The equivalent of "what it did" is now done on the
> manifest side.

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
wraps the same flow. Key naming is enforced by
`tests/test_secret_manifest_env_contract.py`.

### Historical record (2026-02-15)

The original prerequisites and steps — SSH to an admin machine, export a
cluster-admin kubeconfig, and run `./scripts/fix-hub-auth.sh` — are omitted
from this copy; they described a live-mutation path that no longer exists in
the repo. What the script did at the time:

### What the Script Does

1. ✅ Shows current secret keys and values (first 20 chars)
2. ✅ Asks for confirmation before proceeding
3. ✅ Prompts for Hub API key if missing or placeholder
4. ✅ Updates secret with correct `BOTBURROW_` prefixes
5. ✅ Restarts coordinator deployments
6. ✅ Tails logs to verify fix (checks for 401 errors)

### Expected Output

```
=================================================================
Hub API Authentication Fix
=================================================================

Current secret keys (showing first 20 chars of values):
HUB_API_KEY: placeholder-update-m...
R2_ENDPOINT: https://s3.example....
...

Do you want to update the secret with BOTBURROW_ prefixes? (yes/no): yes

Updating secret...
✅ Secret updated successfully!

Updated keys:
BOTBURROW_HUB_API_KEY
BOTBURROW_R2_ACCESS_KEY
BOTBURROW_R2_ENDPOINT
BOTBURROW_R2_SECRET_KEY
FORGEJO_TOKEN
FORGEJO_USER
GITHUB_TOKEN
GITHUB_USER

Restart coordinator to apply changes? (yes/no): yes

Restarting coordinator deployments...
deployment.apps/coordinator restarted
deployment.apps/coordinator-git-sync restarted

Waiting for rollout to complete...
deployment "coordinator" successfully rolled out
deployment "coordinator-git-sync" successfully rolled out

✅ Coordinator restarted successfully!

Checking logs for 401 errors (will tail for 30 seconds)...
[info] poll_success assignments_count=0
[info] poll_success assignments_count=0

If you don't see 401 errors above, the fix is working! ✅
```

---

## ~~Alternative: Manual kubectl edit~~ — forbidden under the GitOps rule

The historical alternative of editing the live Secret with
`kubectl edit secret botburrow-agents-secrets` and restarting the
coordinator deployments is not available any more, not merely discouraged:
the live Secret is owned by the SealedSecret manifest in an ArgoCD-managed
namespace, so the edit is drift that `selfHeal` reverts and a violation of
the GitOps rule regardless. There is no manual-kubectl variant of this fix —
the manifest-side rotation flow above is the only path.

---

## Verification Steps

After applying the fix:

```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig

# 1. Check environment variable is set
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
# Expected: BOTBURROW_HUB_API_KEY=your-actual-key

# 2. Check for 401 errors (should be NONE)
kubectl logs deployment/coordinator -n botburrow-agents --tail=50 | grep -i "401\|unauthorized"
# Expected: No output (no 401 errors)

# 3. Check for successful polling
kubectl logs deployment/coordinator -n botburrow-agents --tail=50 | grep poll_success
# Expected: [info] poll_success assignments_count=X

# 4. Verify all coordinator pods are healthy
kubectl get pods -n botburrow-agents | grep coordinator
# Expected: All pods Running and Ready (1/1 or 2/2)
```

---

## Files Involved

- **Automated fix script:** `scripts/fix-hub-auth.sh` (deleted 2026-09-16 — see header)
- **Comprehensive documentation:** `docs/hub-api-authentication-fix.md`
- **Updated placeholder:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Config definition:** `src/botburrow_agents/config.py` (env_prefix="BOTBURROW_")
- **Hub client:** `src/botburrow_agents/clients/hub.py` (uses settings.hub_api_key)

---

## Why This Happened

The `config.py` file specifies `env_prefix="BOTBURROW_"` which means **all environment variables must be prefixed with `BOTBURROW_`** to be recognized by the Settings model:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOTBURROW_",  # ← All env vars must start with BOTBURROW_
        ...
    )
    hub_api_key: str | None = Field(default=None, ...)  # Becomes BOTBURROW_HUB_API_KEY
```

---

## Long-term Solution (Optional)

Consider granting `devpod-observer` service account **secret edit permissions** in the `botburrow-agents` namespace to enable automated fixes from devpods:

```yaml
# Apply this to enable automated cluster-admin tasks from devpods
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secret-editor
  namespace: botburrow-agents
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "watch", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: devpod-observer-secret-editor
  namespace: botburrow-agents
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: secret-editor
subjects:
- kind: ServiceAccount
  name: devpod-observer
  namespace: devpod-observer
```

**Security Consideration:** This grants write access to secrets - evaluate based on your security requirements.

---

## Questions or Issues?

- **Bead ID:** bd-2sp (HUMAN: Apply Hub API auth fix)
- **Workspace:** /home/coder/botburrow-agents
- **Documentation:** `docs/hub-api-authentication-fix.md`
- **Fix Script:** `scripts/fix-hub-auth.sh` (deleted 2026-09-16 — see header)

---

## Next Steps After Fix

Once the fix is applied and verified:

1. ✅ Confirm 401 errors are gone
2. ✅ Test end-to-end activation flow
3. ✅ Update this bead status: `br close bd-2sp --status completed`
4. ✅ Commit changes: `git add . && git commit -m "docs: Mark Hub API auth fix as completed"`

---

**Status:** ~~Waiting for human with cluster-admin access to apply fix~~ → Resolved 2026-09-15 by commit `e52694d` (historical record)
**Last Updated:** 2026-09-16
