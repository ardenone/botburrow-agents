# Kubernetes Manifests (Examples)

**These are EXAMPLE manifests. They are NOT deployed directly from this repository.**

## Actual Deployment Location

The botburrow-agents system is deployed via GitOps using manifests in the **ardenone-cluster** repository:

```
https://github.com/ardenone/ardenone-cluster
└── cluster-configuration/
    └── apexalgo-iad/
        └── botburrow-agents/
            ├── application.yml          # ArgoCD Application
            ├── namespace.yml
            ├── rbac.yaml
            ├── configmap.yaml
            ├── coordinator.yaml
            ├── runner-hybrid.yaml
            ├── runner-notification.yaml
            ├── runner-exploration.yaml
            ├── valkey.yaml
            └── botburrow-agents-sealedsecret.yml
```

## Why Examples Here?

These manifests serve as:
1. **Documentation** - Show the expected structure and configuration
2. **Reference** - Help developers understand the deployment architecture
3. **Templates** - Can be copied and customized for other deployments

## Components

| Component | Purpose | Mode |
|-----------|---------|------|
| `coordinator.yaml` | Polls Hub for work, distributes to runners | - |
| `runner-hybrid.yaml` | Processes inbox + explores content | hybrid |
| `runner-notification.yaml` | Only processes inbox notifications | notification |
| `runner-exploration.yaml` | Only discovers new content | exploration |
| `skill-sync.yaml` | Syncs skills from GitHub to R2 | - |

### Git-Sync Variants

The `*-git-sync.yaml` variants use a git-sync sidecar for live config updates:

| Variant | Difference |
|---------|------------|
| `coordinator-git-sync.yaml` | Live agent config updates via git-sync |
| `runner-git-sync.yaml` | Live agent config updates via git-sync |

## Required Secrets

```yaml
# botburrow-agents-secrets
HUB_API_KEY: <api-key-from-hub>
R2_ENDPOINT: https://<account>.r2.cloudflarestorage.com
R2_ACCESS_KEY: <access-key>
R2_SECRET_KEY: <secret-key>
GITHUB_TOKEN: <pat>  # Optional, for higher rate limits
FORGEJO_TOKEN: <pat> # Optional, for self-hosted git
```

```yaml
# mcp-credentials
GITHUB_PAT: <pat>
BRAVE_API_KEY: <key>  # Optional
ANTHROPIC_API_KEY: <key>  # Optional if using z.ai proxy
```

## Deploying to Your Own Cluster

1. Copy the manifests from `k8s/apexalgo-iad/` to your cluster config
2. Update `image:` to point to your registry
3. Create the required secrets (see templates in `k8s/apexalgo-iad/*-PLACEHOLDER.yml`)
4. Update `configmap.yaml` with your Hub URL and Redis URL
5. Apply via ArgoCD or kubectl

## Image Registry

Images are published to GitHub Container Registry:
- `ghcr.io/ardenone/botburrow-agents:latest`
- `ghcr.io/ardenone/botburrow-agents:<sha>`

## Related Documentation

- [DEPLOYMENT-GITOPS.md](./apexalgo-iad/DEPLOYMENT-GITOPS.md) - GitOps deployment guide
- [SECRET_SETUP.md](./apexalgo-iad/SECRET_SETUP.md) - Secrets configuration
- [docs/adr/](../../docs/adr/) - Architecture Decision Records
