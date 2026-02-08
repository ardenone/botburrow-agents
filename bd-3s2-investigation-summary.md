# Bead bd-3s2 Investigation Summary

## Problem
The botburrow-agents namespace infrastructure cannot be deployed because the required secrets `botburrow-agents-secrets` and `mcp-credentials` do not exist. The devpod-observer ServiceAccount (used by workers) lacks permission to create secrets in the botburrow-agents namespace (intentional security boundary).

## Investigation Findings

### Secret Manifest Exists
- **Template location:** `/home/coder/botburrow-agents/k8s/apexalgo-iad/botburrow-agents-secret.yml.template`
- **Contains two secrets:**
  1. `botburrow-agents-secrets` (8 keys: HUB_API_KEY, R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, FORGEJO_USER, FORGEJO_TOKEN, GITHUB_USER, GITHUB_TOKEN)
  2. `mcp-credentials` (3 keys: GITHUB_PAT, BRAVE_API_KEY, ANTHROPIC_API_KEY)

### Namespace Status
- **Namespace exists:** botburrow-agents (Active, 6d8h old)
- **No resources deployed:** Namespace is empty (0 pods, 0 deployments)
- **Deployments blocked:** 5 deployments (coordinator, runner-hybrid, runner-notification, runner-exploration, valkey)

### RBAC Confirmation
```bash
$ kubectl auth can-i create secret --namespace=botburrow-agents --as=system:serviceaccount:devpod-observer:devpod-observer
# Result: no (Forbidden)

$ kubectl create secret generic botburrow-agents-secrets -n botburrow-agents ...
# Error: User "system:serviceaccount:devpod-observer:devpod-observer" cannot create resource "secrets"
```

### Alternatives Attempted
1. **kubectl apply** - Blocked by RBAC
2. **SealedSecret creation** - Certificate access blocked
3. **GitOps deployment** - SealedSecret doesn't exist yet

## Resolution Path

**Human with cluster-admin access must create the secrets.**

## Human Bead Created
- **Bead ID:** bd-akn
- **Title:** HUMAN: Apply botburrow-agents-secrets and mcp-credentials to apexalgo-iad deployments blocked
- **Dependency:** bd-3s2 waits-for bd-akn

## Recommended Action (Option 1 - Fastest)

```bash
# Create botburrow-agents-secrets with placeholders
kubectl create secret generic botburrow-agents-secrets -n botburrow-agents \
  --from-literal=HUB_API_KEY="placeholder-update-me" \
  --from-literal=R2_ENDPOINT="https://placeholder.r2.cloudflarestorage.com" \
  --from-literal=R2_ACCESS_KEY="placeholder" \
  --from-literal=R2_SECRET_KEY="placeholder" \
  --from-literal=FORGEJO_USER="botburrow-agents" \
  --from-literal=FORGEJO_TOKEN="placeholder-update-me" \
  --from-literal=GITHUB_USER="placeholder" \
  --from-literal=GITHUB_TOKEN="placeholder-update-me"

# Create mcp-credentials with placeholders
kubectl create secret generic mcp-credentials -n botburrow-agents \
  --from-literal=GITHUB_PAT="placeholder-update-me" \
  --from-literal=BRAVE_API_KEY="placeholder-update-me" \
  --from-literal=ANTHROPIC_API_KEY=""

# Verify
kubectl get secret botburrow-agents-secrets mcp-credentials -n botburrow-agents
```

## Next Steps
1. ⏳ WAITING: Human to apply secrets (bd-akn)
2. ⏳ PENDING: Verify secrets exist in cluster
3. ⏳ PENDING: Verify deployments start (coordinator, runners, valkey)
4. ⏳ PENDING: Close human bead (bd-akn)
5. ⏳ PENDING: Resume bd-3s2 deployment
6. ⏳ PENDING: Complete bd-3s2 and close

## Full Human Bead Description
See `/tmp/human_bead_bd_3s2.md` for complete context with 4 resolution options.
