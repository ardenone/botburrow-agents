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
            └── botburrow-agents-sealedsecrets.yml   # sealed by kubeseal from the template (see docs/GITOPS_DEPLOYMENT.md)
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
# CRITICAL: Hub/R2 keys must use the BOTBURROW_ prefix to match config.py env_prefix
BOTBURROW_HUB_API_KEY: <api-key-from-hub>
BOTBURROW_R2_ENDPOINT: https://<account>.r2.cloudflarestorage.com
BOTBURROW_R2_ACCESS_KEY: <access-key>
BOTBURROW_R2_SECRET_KEY: <secret-key>
GITHUB_TOKEN: <pat>  # Optional, for higher rate limits
FORGEJO_TOKEN: <pat> # Optional, for self-hosted git
```

```yaml
# mcp-credentials
GITHUB_PAT: <pat>
BRAVE_API_KEY: <key>  # Optional
ANTHROPIC_API_KEY: <key>  # Optional if using z.ai proxy
```

Hub/R2 key naming is enforced by `tests/test_secret_manifest_env_contract.py`.

## Deploying to Your Own Cluster

1. Copy the manifests from `k8s/apexalgo-iad/` to your cluster config
2. Update `image:` to point to your registry
3. Create the required secrets (see templates in `k8s/apexalgo-iad/*-PLACEHOLDER.yml`)
4. Update `configmap.yaml` with your Hub URL and Redis URL
5. Apply via ArgoCD or kubectl

## Image Registry

Images are published to GitHub Container Registry, pinned to the semver in
the repo's `VERSION` file (CI auto-bumps it per build — see the
"Versioning" section of [docs/GITOPS_DEPLOYMENT.md](../docs/GITOPS_DEPLOYMENT.md)):

- `ghcr.io/ardenone/botburrow-agents:<version>` — e.g. `0.1.1`

Fleet policy prohibits `:latest` and bare git SHA tags. After each build,
re-pin the manifests to the new version (step 3 of the flow in
GITOPS_DEPLOYMENT.md), then verify the pins before committing:

```bash
python3 scripts/check_image_pins.py   # exits non-zero on any unpinned ref
```

`scripts/check_image_pins.py` (also run as `tests/test_image_pins.py`)
fails any manifest or Dockerfile carrying an unpinned reference.

## Related Documentation

- [DEPLOYMENT-GITOPS.md](./apexalgo-iad/DEPLOYMENT-GITOPS.md) - GitOps deployment guide
- [SECRET_SETUP.md](./apexalgo-iad/SECRET_SETUP.md) - Secrets configuration
- [docs/adr/](../../docs/adr/) - Architecture Decision Records
