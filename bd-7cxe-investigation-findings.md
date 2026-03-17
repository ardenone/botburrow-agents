# Investigation Findings: ronaldraygun/botburrow-agents Image Version

**Date:** 2026-03-17
**Bead:** bd-7cxe
**Investigation:** What commit/version does ronaldraygun/botburrow-agents contain?

## Summary

The `ronaldraygun/botburrow-agents` Docker Hub image was the legacy container registry for this project. It has been **deprecated** in favor of **GitHub Container Registry (GHCR)** at `ghcr.io/ardenone/botburrow-agents`.

## Key Findings

### 1. Image Status: DEPRECATED

The `ronaldraygun/botburrow-agents` image is no longer maintained. All references have been migrated to:
- **New Registry:** `ghcr.io/ardenone/botburrow-agents`
- **Migration Commit:** `2a2a589` (2026-03-17 05:27:19)

### 2. Last Commit in Docker Hub Image

Based on git history analysis, the `ronaldraygun/botburrow-agents:latest` image contains code from approximately:

| Property | Value |
|----------|-------|
| **Last Commit** | `8f01f1996eb2c778b4bb4e98a5089736ca08907f` |
| **Short SHA** | `8f01f19` |
| **Commit Date** | 2026-03-17 02:40:41 -0400 |
| **Author** | jedarden <github@jedarden.com> |
| **Message** | "chore(bd-31j): close obsolete mitosis-child beads" |
| **Previous Commit** | `baebd4b` - "fix(bd-31j): update tests for _get_credentials changes to include hub_url" |

### 3. Migration Timeline

```
2026-03-16 23:52:44  Commit 27f217d - Fixed CI/CD to push to ronaldraygun/botburrow-agents
2026-03-17 02:22:09  Commit baebd4b - Last significant code change before migration
2026-03-17 02:40:41  Commit 8f01f19 - Last commit in Docker Hub image
2026-03-17 05:27:19  Commit 2a2a589 - MIGRATED to ghcr.io/ardenone/botburrow-agents
```

### 4. Build Process

The Docker Hub image was built by GitHub Actions CI/CD pipeline (`.github/workflows/ci-cd.yml`):

```yaml
env:
  REGISTRY: docker.io
  IMAGE_NAME: ronaldraygun/botburrow-agents
```

**Image Tags Pushed:**
- `docker.io/ronaldraygun/botburrow-agents:latest`
- `docker.io/ronaldraygun/botburrow-agents:<SHORT_SHA>`

### 5. Code in the Last Docker Hub Image

The `ronaldraygun/botburrow-agents` image contains:
- Python 3.12 based botburrow-agents
- Leader election code (`work_queue.py` with `LeaderElection` class)
- MCP (Model Context Protocol) integration
- Git-sync capabilities for live config updates
- All features up to commit `8f01f19`

## Recommendation

**Do NOT use the `ronaldraygun/botburrow-agents` image for new deployments.**

Use the current GHCR image instead:
```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Artifacts

- Migration commit: `2a2a589` - "fix(bd-93p4): migrate image refs from ronaldraygun/botburrow-agents to ghcr.io/ardenone/botburrow-agents"
- CI/CD workflow change: `27f217d` - "fix(bd-95k0): align ci-cd.yml image name with release.yml and K8s manifests"
- K8s manifests updated in: `2a2a589` (7 files changed)
