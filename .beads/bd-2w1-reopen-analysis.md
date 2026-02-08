# bd-2w1 Analysis: Botburrow-Agents Secrets Deployment

## Current State (2026-02-08 08:06 UTC)

### Bead Status
| Bead ID | Title | Status | Notes |
|---------|-------|--------|-------|
| bd-2w1 | HUMAN: Create botburrow-agents secrets | CLOSED | **INCORRECTLY CLOSED** - secrets not created |
| bd-2la | HUMAN: Create botburrow-agents-secrets | BLOCKED | Blocked on bd-1re |
| bd-1re | HUMAN: Apply devpod-observer RBAC | BLOCKED | Blocked on bd-3sn |
| bd-3sn | HUMAN: Apply RBAC RoleBinding | CLOSED | RBAC not actually applied |

### Cluster State
- **Namespace**: botburrow-agents exists
- **Secrets**: botburrow-agents-secrets NOT FOUND, mcp-credentials NOT FOUND
- **RBAC**: Only read-only access (mcp-k8s-observer), no admin access
- **Deployments**: No resources running

### Required Actions (HUMAN)

1. **Apply RBAC** (bd-3sn/bd-1re):
```bash
kubectl apply -f /home/coder/botburrow-agents/k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml
```

2. **Create Secrets** (bd-2w1/bd-2la/bd-psf5):
```bash
# Option 1: Placeholder (quick)
kubectl apply -f /home/coder/botburrow-agents/k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Option 2: Manual with real values
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

### Duplicate Human Beads
The following beads all request the same action:
- bd-2w1 (botburrow-agents workspace) - CLOSED incorrectly
- bd-2la (botburrow-agents workspace) - BLOCKED on RBAC
- bd-psf5 (home workspace) - OPEN

### Recommended Next Steps
1. Human applies RBAC manually (cluster-admin required)
2. Human creates secrets manually (cluster-admin required)
3. Unblock bd-1re and bd-2la once RBAC/secrets are applied
4. Close duplicate beads (bd-2w1 already closed, bd-psf5 can reference bd-2la)
