# Definitive Answer: Docker Hub Repository `ardenone/botburrow-agents`

**Bead ID:** bd-p92v
**Date:** 2026-03-20

## Question
Does Docker Hub repository `ardenone/botburrow-agents` exist?

## Answer
**No, and it's not needed.** The project uses GitHub Container Registry (GHCR) instead.

## Context
This bead was created from parent bd-31j ("Configure Docker Hub credentials for CI/CD push"). The parent bead documented two resolution options:

1. **Option 1:** Create Docker Hub repository and configure secrets
2. **Option 2:** Switch to GitHub Container Registry (GHCR)

**Resolution chosen: Option 2 (GHCR)**

## Evidence

### Current CI/CD Configuration
Both `.github/workflows/ci-cd.yml` and `.github/workflows/release.yml` are configured for GHCR:

```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ardenone/botburrow-agents
```

Images are pushed to:
- `ghcr.io/ardenone/botburrow-agents:<sha>`
- `ghcr.io/ardenone/botburrow-agents:latest`

### Git History
Key commits showing the migration:
- `2a2a589` - "migrate image refs from ronaldraygun/botburrow-agents to ghcr.io/ardenone/botburrow-agents"
- `27f217d` - "align ci-cd.yml image name with release.yml and K8s manifests"
- `cd7ae70` - "grant packages:write permission for GHCR push in build job"

## Conclusion
The Docker Hub repository `ardenone/botburrow-agents` does not exist because the project was migrated to GHCR. This is the intended configuration - no Docker Hub repository needs to be created.

## Image Location
The correct image location is: **ghcr.io/ardenone/botburrow-agents**
