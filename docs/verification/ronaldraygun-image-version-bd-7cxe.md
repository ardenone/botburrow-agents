# ronaldraygun/botburrow-agents Image Version Documentation

**Bead ID:** bd-7cxe
**Investigation Date:** 2026-03-17
**Task:** Determine what commit/version the `ronaldraygun/botburrow-agents` Docker image contains

## Summary

The `ronaldraygun/botburrow-agents` Docker image repository on Docker Hub contains a single versioned release and a `latest` tag, both pushed during the v0.1.1 release on 2026-02-14.

## Image Details

### Available Tags

| Tag | Digest | Git Commit | Date | Status |
|-----|--------|------------|------|--------|
| `v0.1.1` | `sha256:8a122e13e8ec124460dcfd56a072f0bde354a5586987f9c8b50afcfb0e5623da` | `a0021f9d3900fff53c9fb32e5b952d15c5068bb1` | 2026-02-14 21:10 UTC | Successfully pushed |
| `latest` | `sha256:8a122e13e8ec124460dcfd56a072f0bde354a5586987f9c8b50afcfb0e5623da` | `a0021f9d3900fff53c9fb32e5b952d15c5068bb1` | 2026-02-14 21:10 UTC | Same as v0.1.1 |

### Git Tag Information

**Tag:** `v0.1.1`
**Full SHA:** `a0021f9d3900fff53c9fb32e5b952d15c5068bb1`
**Short SHA:** `a0021f9`
**Commit Message:** `fix(bd-xou): Fix Docker Hub secret name reference`
**Tag Date:** 2026-02-14 21:10:56 UTC

### GitHub Actions Release Workflow

**Workflow:** `.github/workflows/release.yml`
**Run ID:** 22024326118
**Status:** Completed successfully
**Duration:** 1m 57s
**Trigger:** Push of tag `v0.1.1`

The release workflow pushed:
- `docker.io/ronaldraygun/botburrow-agents:v0.1.1`
- `docker.io/ronaldraygun/botburrow-agents:latest`

### Release Workflow Configuration (at v0.1.1)

```yaml
env:
  REGISTRY: docker.io
  IMAGE_NAME: ronaldraygun/botburrow-agents

jobs:
  build-and-push:
    # ... builds and pushes:
    # - docker.io/ronaldraygun/botburrow-agents:${VERSION}
    # - docker.io/ronaldraygun/botburrow-agents:latest
```

## Current Status

**IMPORTANT:** This repository and image has been **DEPRECATED** in favor of `ghcr.io/ardenone/botburrow-agents`.

The migration from `ronaldraygun/botburrow-agents` to `ghcr.io/ardenone/botburrow-agents` occurred in commit `2a2a589` (fix(bd-93p4): migrate image refs from ronaldraygun/botburrow-agents to ghcr.io/ardenone/botburrow-agents).

## Key Code Features in v0.1.1

Based on commit `a0021f9`, the v0.1.1 image includes:

- Python 3.12 base
- Node.js 20.x
- Claude Code CLI (`@anthropic-ai/claude-code`)
- MCP servers (github, brave-search, filesystem)
- Goose AI assistant
- Aider chat assistant
- Botburrow agents coordinator and runner

### Leader Election

**Yes — the `LeaderElection` class is included.**

`src/botburrow_agents/coordinator/work_queue.py` was first committed on 2026-02-01 (before the v0.1.1 tag on 2026-02-14) and already contained the `LeaderElection` class at line 347. The v0.1.1 tag (`a0021f9`) retains it at line 371.

Verified via:
```bash
git show v0.1.1:src/botburrow_agents/coordinator/work_queue.py | grep -n "LeaderElection"
# 371:class LeaderElection:
```

## Image History

The v0.1.1 release was the first and only formal release pushed to Docker Hub under the `ronaldraygun/botburrow-agents` repository. Subsequent releases use GitHub Container Registry (`ghcr.io/ardenone/botburrow-agents`).

## Verification

To verify the image contents and labels:

```bash
# Pull the image
docker pull ronaldraygun/botburrow-agents:v0.1.1

# Inspect image labels
docker inspect ronaldraygun/botburrow-agents:v0.1.1 | jq '.[0].Config.Labels'
```

The image should contain labels indicating the git revision:
```json
{
  "org.opencontainers.image.version": "v0.1.1",
  "org.opencontainers.image.revision": "a0021f9d3900fff53c9fb32e5b952d15c5068bb1"
}
```

## References

- GitHub Release: https://github.com/ardenone/botburrow-agents/releases/tag/v0.1.1
- Release Workflow Run: https://github.com/ardenone/botburrow-agents/actions/runs/22024326118
- Commit: https://github.com/ardenone/botburrow-agents/commit/a0021f9d3900fff53c9fb32e5b952d15c5068bb1
