# ArgoCD GitOps Deployment Status for botburrow-agents

## Overview

This document tracks the status of the ArgoCD GitOps deployment for botburrow-agents as of 2026-02-08.

## Current Status: Ready for Deployment (Awaiting Credentials)

The GitOps infrastructure is fully prepared. The only remaining blocker is obtaining actual credential values to create the SealedSecrets.

## Infrastructure Checklist

| Component | Status | Notes |
|-----------|--------|-------|
| ArgoCD Application Manifest | ✅ Ready | `k8s/apexalgo-iad/argocd-application.yaml` |
| Kustomization for GitOps | ✅ Ready | `k8s/apexalgo-iad/kustomization-gitops.yaml` |
| SealedSecret Template | ✅ Ready | `k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml.template` |
| SealedSecret Controller | ✅ Running | Namespace: `sealed-secrets` |
| Namespace | ✅ Exists | `botburrow-agents` (6d old) |
| Documentation | ✅ Complete | `DEPLOYMENT-GITOPS.md`, `SECRET_SETUP.md` |
| Creation Script | ✅ Ready | `scripts/create-sealedsecret.sh` |
| **SealedSecret (with real values)** | ⏳ **BLOCKED** | Requires human input with credentials |

## Required Credentials

To complete the deployment, the following credential values are needed:

| Credential | Source | Required For |
|------------|--------|--------------|
| HUB_API_KEY | Botburrow Hub admin | Hub API access |
| R2_ENDPOINT | Cloudflare R2 dashboard | Storage endpoint |
| R2_ACCESS_KEY | Cloudflare R2 dashboard | Storage access |
| R2_SECRET_KEY | Cloudflare R2 dashboard | Storage secret |
| FORGEJO_USER | Forgejo | Git service account |
| FORGEJO_TOKEN | https://forgejo.ardenone.com | Git operations |
| GITHUB_USER | GitHub | GitHub username |
| GITHUB_TOKEN | GitHub Settings → Developer settings | External repos |
| GITHUB_PAT | GitHub Settings → Developer settings | MCP server |
| BRAVE_API_KEY | https://brave.com/search/api/ | Web search |
| ANTHROPIC_API_KEY | Anthropic Console | Optional (use z.ai proxy) |

## Deployment Steps (When Credentials Available)

### Step 1: Create SealedSecret

```bash
# Copy and edit template with real values
cp k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml.template /tmp/botburrow-agents-secrets.yml
vi /tmp/botburrow-agents-secrets.yml  # Fill in all REPLACE_* values

# Create SealedSecret
kubeseal --format=yaml \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets \
  < /tmp/botburrow-agents-secrets.yml \
  > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml

# Verify
kubectl apply --dry-run=server -f k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml

# Clean up
rm /tmp/botburrow-agents-secrets.yml

# Commit to Git
git add k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
git commit -m "feat(bd-3e3): Add SealedSecret with production credentials"
git push origin main
```

### Step 2: Enable SealedSecret in Kustomization

Uncomment the SealedSecret line in `kustomization-gitops.yaml`:

```yaml
resources:
  # Wave -1: SealedSecrets
  - botburrow-agents-sealedsecrets.yml  # Uncomment this
```

### Step 3: Apply ArgoCD Application

```bash
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml
```

### Step 4: Monitor Deployment

```bash
# Watch sync status
kubectl get application botburrow-agents -n argocd -w

# Check pods
kubectl get pods -n botburrow-agents
```

## Related Beads

| Bead ID | Title | Status | Notes |
|---------|-------|--------|-------|
| bd-3e3 | Create ArgoCD GitOps deployment | 🔄 In Progress | Infrastructure ready, blocked on credentials |
| bd-2la | Create botburrow-agents-secrets and mcp-credentials | ⏳ Blocked | Human bead for cluster-admin to create secrets |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  GitOps Flow                                                   │
│                                                                │
│  GitHub (ardenone/botburrow-agents)                            │
│  ├── k8s/apexalgo-iad/                                         │
│  │   ├── argocd-application.yaml    ← ArgoCD Application       │
│  │   ├── kustomization-gitops.yaml  ← GitOps Kustomization     │
│  │   ├── botburrow-agents-sealedsecrets.yml ← Encrypted       │
│  │   └── *.yaml                    → All manifests            │
│  │                             ↓                               │
│  │                     ArgoCD Sync                               │
│  │                             ↓                               │
│  └───────────────────────────────────────────────────────┐   │
│                                                             │   │
│  apexalgo-iad Cluster                                       │   │
│  └── botburrow-agents namespace                             │   │
│      ├── Secrets (decrypted by SealedSecrets)               │   │
│      ├── Valkey (Redis)                                      │   │
│      ├── Coordinator (2 replicas, leader election)           │   │
│      ├── Runners (hybrid, notification, exploration)         │   │
│      └── HPA, ServiceMonitor                                 │   │
└─────────────────────────────────────────────────────────────┘
```

## Success Criteria

- [x] ArgoCD Application manifest created
- [x] Kustomization configured for GitOps
- [x] SealedSecret template available
- [x] Documentation complete
- [ ] SealedSecret created with real credentials
- [ ] ArgoCD Application applied to cluster
- [ ] All pods running successfully

## Files Modified

This GitOps setup was prepared as part of bead bd-3e3. Key files:

- `k8s/apexalgo-iad/argocd-application.yaml` - ArgoCD Application manifest
- `k8s/apexalgo-iad/kustomization-gitops.yaml` - GitOps Kustomization with SealedSecret placeholder
- `k8s/apexalgo-iad/DEPLOYMENT-GITOPS.md` - Comprehensive deployment guide
- `k8s/apexalgo-iad/SECRET_SETUP.md` - Secret creation instructions
- `k8s/apexalgo-iad/scripts/create-sealedsecret.sh` - Automated SealedSecret creation

## Next Steps

1. **Human Action**: Resolve bead bd-2la to provide actual credential values
2. **Create SealedSecret**: Follow Step 1 above with real values
3. **Enable in Kustomization**: Uncomment SealedSecret line
4. **Apply ArgoCD Application**: Deploy via `kubectl apply -f argocd-application.yaml`
5. **Verify**: Confirm all pods are running and healthy

## Contact

For questions or issues, refer to:
- DEPLOYMENT-GITOPS.md - Detailed deployment instructions
- SECRET_SETUP.md - Secret creation workflow
- Bead bd-2la - Cluster-admin action for secrets
