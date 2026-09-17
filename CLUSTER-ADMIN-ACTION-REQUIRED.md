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
> manifest change (see [docs/GITOPS_DEPLOYMENT.md](docs/GITOPS_DEPLOYMENT.md)).
> The fix script they pointed at, `scripts/fix-hub-auth.sh`, was **deleted
> on 2026-09-16** — its `kubectl apply` of the Secret and `kubectl rollout
> restart` of the coordinator deployments are live mutations of
> ArgoCD-managed resources that `selfHeal` reverts. Do not recreate it; the
> only rotation path is the manifest-side SealedSecret flow in
> [docs/GITOPS_DEPLOYMENT.md § Secrets Management](docs/GITOPS_DEPLOYMENT.md#secrets-management)
> (helper: `k8s/apexalgo-iad/scripts/create-sealedsecret.sh`).
> Bead IDs (`bd-q21`, `bd-2jm`) are from the retired bead-forge backend,
> kept for provenance only. Companion records:
> [docs/incidents/ACTION-REQUIRED-hub-auth-fix.md](docs/incidents/ACTION-REQUIRED-hub-auth-fix.md)
> and [docs/incidents/CLUSTER-ADMIN-ACTION-REQUIRED.md](docs/incidents/CLUSTER-ADMIN-ACTION-REQUIRED.md).

## Status
~~🔴 **BLOCKED** - Requires cluster-admin permissions to edit secrets in apexalgo-iad cluster~~ → **Resolved 2026-09-15** by commit `e52694d`

## Problem
The coordinator is experiencing continuous 401 Unauthorized errors when polling the Hub API at https://botburrow.ardenone.com.

**Root Cause:** Environment variable naming mismatch
- **Secret contains**: `HUB_API_KEY` (without BOTBURROW_ prefix)
- **Application expects**: `BOTBURROW_HUB_API_KEY` (with BOTBURROW_ prefix)

## Current Access Level
The devpod-observer ServiceAccount has **read-only** access and **cannot access secrets**:

```
Error from server (Forbidden): secrets "botburrow-agents-secrets" is forbidden: 
User "system:serviceaccount:devpod-observer:devpod-observer" cannot get resource 
"secrets" in API group "" in the namespace "botburrow-agents"
```

## Current rotation path (the only one)

The deleted `scripts/fix-hub-auth.sh` and the former manual `kubectl` recipe
are historical context only. Never edit or restart the live Secret/workloads;
the ArgoCD-managed SealedSecret is the source of truth. For any future
rotation, follow the canonical manifest-side flow:
[docs/GITOPS_DEPLOYMENT.md § Secrets Management](docs/GITOPS_DEPLOYMENT.md#secrets-management)
(helper: `k8s/apexalgo-iad/scripts/create-sealedsecret.sh`).

That flow regenerates the SealedSecret with `kubeseal`, commits the encrypted
manifest, and pushes it to `main`; ArgoCD then syncs the change and the
SealedSecrets controller updates the live Secret. No live mutation is needed.

## Verification After Fix

```bash
# 1. Check coordinator logs (should see no 401 errors)
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50

# 2. Verify environment variable is set correctly
kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY

# 3. Check all pods are running
kubectl get pods -n botburrow-agents | grep coordinator
```

## Documentation

- **Canonical rotation guide**: `docs/GITOPS_DEPLOYMENT.md § Secrets Management`
- **Historical incident record**: `docs/hub-api-authentication-fix.md`
- **Updated placeholder**: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

## Related Beads

- **Original issue**: bd-q21 (HUMAN: Fix coordinator Hub API authentication (401 errors))
- **This action**: bd-2jm (CLUSTER-ADMIN: Apply Hub API authentication fix)

---

**Next Steps:**
None — resolved by commit `e52694d` on the manifest side; no live `kubectl`
action was taken or is needed. The old bead-forge `br close` command is kept
out of this current record because it is no longer the repository workflow.
