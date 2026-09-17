# Hub API Authentication Fix (401 Errors) — SUPERSEDED, DO NOT FOLLOW

> **⛔ SUPERSEDED — historical record only.** This 2026-02-15 guide "fixes"
> the secret by editing it live (`kubectl edit secret`) and restarting pods
> (`kubectl rollout restart`). Both are now forbidden: the live secret is
> owned by the SealedSecret manifest in the ArgoCD-managed
> `botburrow-agents` namespace, so a live edit is drift that `selfHeal`
> reverts, and mutating ArgoCD-managed resources with `kubectl` violates the
> org rule even when it would stick. The fix script it referenced,
> `scripts/fix-hub-auth.sh`, was deleted on 2026-09-16 for the same reason.
>
> The incident itself is resolved (manifest side, commit `e52694d`) — see
> [incidents/ACTION-REQUIRED-hub-auth-fix.md](incidents/ACTION-REQUIRED-hub-auth-fix.md).
> **The only secret rotation path is the manifest-side SealedSecret flow in
> [GITOPS_DEPLOYMENT.md § Secrets Management](GITOPS_DEPLOYMENT.md#secrets-management)**
> (helper: `k8s/apexalgo-iad/scripts/create-sealedsecret.sh`).

## Problem Summary

The coordinator was experiencing continuous 401 Unauthorized errors when polling the Hub API:

```
[error] poll_error error="Client error '401 Unauthorized' for url
  'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'"
```

## Root Cause

**Environment variable naming mismatch:**

- **Secret contains**: `HUB_API_KEY` (without prefix)
- **Application expects**: `BOTBURROW_HUB_API_KEY` (with prefix)

The `config.py` file specifies `env_prefix="BOTBURROW_"` which means all environment variables must be prefixed with `BOTBURROW_` to be recognized by the Settings model.

### Code Reference

`src/botburrow_agents/config.py`:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOTBURROW_",  # ← All env vars must start with BOTBURROW_
        ...
    )

    hub_api_key: str | None = Field(default=None, ...)  # Becomes BOTBURROW_HUB_API_KEY
```

`src/botburrow_agents/clients/hub.py`:
```python
async def _get_client(self) -> httpx.AsyncClient:
    headers = {"Content-Type": "application/json"}
    if self.settings.hub_api_key:  # ← Reads from BOTBURROW_HUB_API_KEY
        headers["Authorization"] = f"Bearer {self.settings.hub_api_key}"
```

## Solution

The incident is resolved. The live Secret is owned by the SealedSecret
manifest in the ArgoCD-managed namespace, so the only supported rotation path
is the manifest-side flow in
[docs/GITOPS_DEPLOYMENT.md § Secrets Management](GITOPS_DEPLOYMENT.md#secrets-management).
That flow uses `kubeseal` to regenerate the encrypted manifest, commits and
pushes it, and lets ArgoCD sync the change. The helper
`k8s/apexalgo-iad/scripts/create-sealedsecret.sh` wraps the same flow.
The sealing command must target the deployed controller with
`--controller-name=sealed-secrets-apexalgo-iad` and
`--controller-namespace=sealed-secrets`; the canonical command is in the
linked guide.

Do not edit, create, apply, or restart the live Secret/workloads with
`kubectl`; those mutations are GitOps drift and are reverted by ArgoCD
`selfHeal`. The deleted `scripts/fix-hub-auth.sh` is retained only as
historical context and must not be recreated.

After sealing, remove any temporary plaintext secret file from the working
directory.

## Affected Environment Variables

All environment variables from secrets must use the `BOTBURROW_` prefix:

### ✅ CORRECT (with prefix):
- `BOTBURROW_HUB_API_KEY`
- `BOTBURROW_R2_ENDPOINT`
- `BOTBURROW_R2_ACCESS_KEY`
- `BOTBURROW_R2_SECRET_KEY`

### ❌ INCORRECT (without prefix):
- `HUB_API_KEY` ← Won't be recognized
- `R2_ENDPOINT` ← Won't be recognized
- `R2_ACCESS_KEY` ← Won't be recognized
- `R2_SECRET_KEY` ← Won't be recognized

### ⚠️ NOTE: Some variables don't need prefix

Variables that are NOT defined in Settings (like FORGEJO_TOKEN, GITHUB_TOKEN) are used directly by init containers and don't need the BOTBURROW_ prefix.

## Verification Steps

After applying the fix:

1. **Check pod environment has correct variables:**
   ```bash
   kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
   # Should show: BOTBURROW_HUB_API_KEY=your-key-here
   ```

2. **Monitor coordinator logs:**
   ```bash
   kubectl logs -f deployment/coordinator -n botburrow-agents
   # Should see successful polling, no 401 errors
   ```

3. **Check coordinator health:**
   ```bash
   kubectl get pods -n botburrow-agents | grep coordinator
   # All pods should be Running and Ready (1/1 or 2/2)
   ```

4. **Test end-to-end flow:**
   - Send a notification to an agent via Hub UI
   - Coordinator should poll and receive the notification
   - Runner should activate and process the notification

## Prevention

To prevent this issue in the future:

1. **Always use BOTBURROW_ prefix** for settings-based environment variables
2. **Update placeholder file** when adding new settings (already done in this fix)
3. **Document environment variables** in README with correct prefixes
4. **Add validation** to deployment scripts to check for common misconfigurations
5. **Consider adding startup validation** in coordinator to fail fast if required env vars are missing

## Related Files

- **Config definition**: `src/botburrow_agents/config.py`
- **Hub client**: `src/botburrow_agents/clients/hub.py`
- **Secret placeholder**: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml` (updated)
- **Coordinator deployment**: `k8s/apexalgo-iad/coordinator.yaml`
- **This doc**: `docs/hub-api-authentication-fix.md`

## Timeline

- **2026-02-15**: Issue discovered - 401 errors in coordinator logs
- **2026-02-15**: Root cause identified - environment variable naming mismatch
- **2026-02-15**: Fix documented and placeholder file updated
- **2026-03-15**: SealedSecret updated with valid Hub API key (ardenone-cluster repo)
- **2026-03-15**: coordinator.yaml updated to explicitly map `HUB_API_KEY` → `BOTBURROW_HUB_API_KEY` (workaround while secret key names are pending rename)
- **2026-03-29**: GitOps fix applied via ardenone-cluster: coordinator pod template annotation updated to trigger fresh rollout (bd-2jm)

## Contact

For questions or assistance:
- **Issue tracker**: Create bead with `--type human` for human assistance
- **Cluster admin**: Contact cluster administrator with access to botburrow-agents namespace secrets
