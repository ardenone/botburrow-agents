# Definitive Answer: Is ronaldraygun/botburrow-agents the correct/official image?

**Bead:** bd-1f68
**Date:** 2026-03-20
**Answer:** **NO** — `ronaldraygun/botburrow-agents` is **deprecated**.

## Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Summary

| Image | Status | Notes |
|-------|--------|-------|
| `ronaldraygun/botburrow-agents` | **DEPRECATED** | Legacy Docker Hub image, last updated 2026-03-17 |
| `ghcr.io/ardenone/botburrow-agents` | **CURRENT** | Official GHCR image, actively maintained |

## Evidence

1. **CI/CD Configuration** (`.github/workflows/release.yml:8-10`):
   ```yaml
   env:
     REGISTRY: ghcr.io
     IMAGE_NAME: ardenone/botburrow-agents
   ```

2. **Kubernetes Manifests** — All botburrow-agents components use:
   ```yaml
   image: ghcr.io/ardenone/botburrow-agents:latest
   ```

3. **Migration Commit** (`2a2a589`, 2026-03-17 05:27:19):
   > "fix(bd-93p4): migrate image refs from ronaldraygun/botburrow-agents to ghcr.io/ardenone/botburrow-agents"

4. **Prior Investigation** (bd-7cxe):
   > The `ronaldraygun/botburrow-agents` Docker Hub image was the legacy container registry for this project. It has been **deprecated** in favor of **GitHub Container Registry (GHCR)** at `ghcr.io/ardenone/botburrow-agents`.

## Recommendation

Use `ghcr.io/ardenone/botburrow-agents:latest` for all deployments. The Docker Hub image should not be used.
