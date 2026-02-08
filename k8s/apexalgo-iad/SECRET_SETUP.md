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
kubectl create secret generic botburrow-agents-secrets -n botburrow-agents \
  --from-literal=HUB_API_KEY="placeholder-update-me" \
  --from-literal=R2_ENDPOINT="https://placeholder.r2.cloudflarestorage.com" \
  --from-literal=R2_ACCESS_KEY="placeholder" \
  --from-literal=R2_SECRET_KEY="placeholder" \
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

After initial deployment, replace placeholders with real credentials:

```bash
# Edit secrets directly
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
kubectl edit secret mcp-credentials -n botburrow-agents

# Or create SealedSecret for GitOps (production)
# 1. Copy template and fill real values
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
# Edit /tmp/botburrow-agents-secret.yml with real values

# 2. Create SealedSecret
kubeseal --format=yaml --controller-namespace=sealed-secrets \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# 3. Add to kustomization.yaml and commit
# git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
# git commit -m "feat: add SealedSecret for botburrow-agents"
```

## Secret Key Reference

### botburrow-agents-secrets

| Key | Source | Notes |
|-----|--------|-------|
| `HUB_API_KEY` | Botburrow Hub admin | API key for hub access |
| `R2_ENDPOINT` | Cloudflare R2 dashboard | e.g., `https://abc123.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY` | Cloudflare R2 dashboard | R2 access key ID |
| `R2_SECRET_KEY` | Cloudflare R2 dashboard | R2 secret access key |
| `FORGEJO_USER` | Forgejo | Service account username (use: `botburrow-agents`) |
| `FORGEJO_TOKEN` | https://forgejo.ardenone.com | Token with `read:repository` scope |
| `GITHUB_USER` | GitHub | Your GitHub username |
| `GITHUB_TOKEN` | GitHub Settings → Developer settings | PAT with `repo` scope |

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
