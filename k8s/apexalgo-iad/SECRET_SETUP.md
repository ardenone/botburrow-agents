# Botburrow Agents Secrets Setup Guide

## Status: WAITING FOR CLUSTER-ADMIN

The botburrow-agents namespace deployments are blocked because required secrets do not exist. Workers cannot create secrets due to RBAC (intentional security boundary).

## Required Secrets

Two secrets need to be created in the `botburrow-agents` namespace:

1. `botburrow-agents-secrets` - Contains Hub API, R2 storage, and Git credentials
2. `mcp-credentials` - Contains MCP server API keys

## Quick Start: Create Placeholder Secrets (RECOMMENDED)

**From a cluster-admin context (not from devpod):**

```bash
# Option 1: Apply the pre-made placeholder manifest
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Option 2: Create manually with kubectl
# CRITICAL: Hub/R2 keys must use the BOTBURROW_ prefix to match config.py
# env_prefix - unprefixed names are invisible to the application (401 bug).
kubectl create secret generic botburrow-agents-secrets -n botburrow-agents \
  --from-literal=BOTBURROW_HUB_API_KEY="placeholder-update-me" \
  --from-literal=BOTBURROW_R2_ENDPOINT="https://placeholder.r2.cloudflarestorage.com" \
  --from-literal=BOTBURROW_R2_ACCESS_KEY="placeholder" \
  --from-literal=BOTBURROW_R2_SECRET_KEY="placeholder" \
  --from-literal=FORGEJO_USER="botburrow-agents" \
  --from-literal=FORGEJO_TOKEN="placeholder-update-me" \
  --from-literal=GITHUB_USER="placeholder" \
  --from-literal=GITHUB_TOKEN="placeholder-update-me"

kubectl create secret generic mcp-credentials -n botburrow-agents \
  --from-literal=GITHUB_PAT="placeholder-update-me" \
  --from-literal=BRAVE_API_KEY="placeholder-update-me" \
  --from-literal=ANTHROPIC_API_KEY=""

# Verify
kubectl get secret botburrow-agents-secrets mcp-credentials -n botburrow-agents
```

## Verify Deployment After Secrets

Once secrets are applied, deployments should start automatically:

```bash
# Watch pods start up
kubectl get pods -n botburrow-agents -w

# Check deployments are ready
kubectl get deployments -n botburrow-agents
```

## Production: Replace with Real Values

Rotate by regenerating the SealedSecret and pushing it (canonical flow:
[docs/GITOPS_DEPLOYMENT.md § Secrets Management](../../docs/GITOPS_DEPLOYMENT.md#secrets-management)).
Do **not** `kubectl edit secret` the live Secret: the namespace is
ArgoCD-managed with `selfHeal`, so the edit is drift that gets reverted —
and a live mutation of an ArgoCD-managed resource is forbidden regardless.

```bash
# 1. Copy template and fill real values
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
# Edit /tmp/botburrow-agents-secret.yml with real values

# 2. Create SealedSecret (--controller-name is required: the Service is
#    named for its Helm release, not the upstream default `sealed-secrets`)
kubeseal --format=yaml \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-apexalgo-iad \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml

# 3. Commit and push — ArgoCD syncs it; never kubectl apply by hand
# git add k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
# git commit -m "feat: add SealedSecret for botburrow-agents"
```

(Historical, forbidden: this section once suggested
`kubectl edit secret botburrow-agents-secrets` /
`kubectl edit secret mcp-credentials` directly — live edits that `selfHeal`
reverts.)

## Secret Key Reference

### botburrow-agents-secrets

| Key | Source | Notes |
|-----|--------|-------|
| `BOTBURROW_HUB_API_KEY` | Botburrow Hub admin | API key for hub access (prefix required by config.py) |
| `BOTBURROW_R2_ENDPOINT` | Cloudflare R2 dashboard | e.g., `https://abc123.r2.cloudflarestorage.com` |
| `BOTBURROW_R2_ACCESS_KEY` | Cloudflare R2 dashboard | R2 access key ID |
| `BOTBURROW_R2_SECRET_KEY` | Cloudflare R2 dashboard | R2 secret access key |
| `FORGEJO_USER` | Forgejo | Service account username (use: `botburrow-agents`) |
| `FORGEJO_TOKEN` | https://forgejo.ardenone.com | Token with `read:repository` scope |
| `GITHUB_USER` | GitHub | Your GitHub username |
| `GITHUB_TOKEN` | GitHub Settings → Developer settings | PAT with `repo` scope |

Hub/R2 key naming is enforced by `tests/test_secret_manifest_env_contract.py`;
run it after renaming any secret key.

### mcp-credentials

| Key | Source | Notes |
|-----|--------|-------|
| `GITHUB_PAT` | GitHub Settings → Developer settings | PAT for MCP github server |
| `BRAVE_API_KEY` | https://brave.com/search/api/ | Brave Search API key |
| `ANTHROPIC_API_KEY` | Anthropic Console | Leave empty if using z.ai proxy (default) |

## Related Files

- `botburrow-agents-secret.yml.template` - Template with all keys and documentation
- `botburrow-agents-secrets-PLACEHOLDER.yml` - Ready-to-apply placeholder manifest
- `SECRET_SETUP.md` - This file

## Current Impact

- **Namespace:** botburrow-agents exists but is empty (no running pods)
- **Blocked deployments:** coordinator, runner-hybrid, runner-notification, runner-exploration, valkey
- **Beads blocked:** bd-3s2, bd-akn, and dependent beads
