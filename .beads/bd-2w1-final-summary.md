# Task bd-2w1: HUMAN - Create botburrow-agents secrets

## Summary

**Status**: DOCUMENTED - Requires Human Action

Bead bd-2w1 was **incorrectly closed** by a previous worker via timeout escalation, but the required secrets were never actually created.

## Current State

### Cluster State (apexalgo-iad)
- Namespace `botburrow-agents`: EXISTS (empty)
- Secret `botburrow-agents-secrets`: NOT FOUND
- Secret `mcp-credentials`: NOT FOUND  
- RBAC: Read-only only (no admin access)

### Existing Human Beads
The following beads track this same work:

1. **bd-2la** (botburrow-agents workspace) - "HUMAN: Create botburrow-agents-secrets"
   - Status: BLOCKED on bd-1re (RBAC)
   - Contains comprehensive secret creation instructions

2. **bd-1re** (botburrow-agents workspace) - "HUMAN: Apply devpod-observer RBAC"
   - Status: BLOCKED on bd-3sn
   - Requires cluster-admin to apply admin RoleBinding

3. **bd-3sn** - "HUMAN: Apply RBAC RoleBinding"
   - Status: CLOSED (but RBAC not actually applied)

## Required Human Actions

### Step 1: Apply RBAC (cluster-admin required)
```bash
kubectl apply -f /home/coder/botburrow-agents/k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml
```

### Step 2: Create Secrets (cluster-admin required)

**Quick Option - Placeholder Secrets:**
```bash
kubectl apply -f /home/coder/botburrow-agents/k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**Production Option - Real Values:**
```bash
kubectl create secret generic botburrow-agents-secrets -n botburrow-agents \
  --from-literal=HUB_API_KEY="<real-key>" \
  --from-literal=R2_ENDPOINT="<real-endpoint>" \
  --from-literal=R2_ACCESS_KEY="<real-key>" \
  --from-literal=R2_SECRET_KEY="<real-key>" \
  --from-literal=FORGEJO_USER="botburrow-agents" \
  --from-literal=FORGEJO_TOKEN="<real-token>" \
  --from-literal=GITHUB_USER="<real-user>" \
  --from-literal=GITHUB_TOKEN="<real-pat>"

kubectl create secret generic mcp-credentials -n botburrow-agents \
  --from-literal=GITHUB_PAT="<real-pat>" \
  --from-literal=BRAVE_API_KEY="<real-key>" \
  --from-literal=ANTHROPIC_API_KEY=""
```

## Documentation

Full analysis saved to: `/home/coder/botburrow-agents/.beads/bd-2w1-reopen-analysis.md`

## Next Steps

1. Human with cluster-admin access applies RBAC and creates secrets
2. Unblock dependent beads (bd-1re, bd-2la) once secrets exist
3. Deployment can proceed via `kubectl apply -k k8s/apexalgo-iad/`

