# bd-6siw: When was this image last built?

## Definitive Answer

**The image was last built on 2026-02-14 at 21:10:56 UTC** when tag `v0.1.1` was pushed, triggering the release workflow.

## Important Clarification

The `ronaldraygun/botburrow-agents` **Docker Hub repository does not exist**. The image is published to **GitHub Container Registry (GHCR)**:

- **Registry:** `ghcr.io/ardenone/botburrow-agents`
- **Latest version:** `v0.1.1` (also tagged as `latest`)

## Evidence

| Source | Finding |
|--------|---------|
| Docker Hub API | Returns "object not found" for `ronaldraygun/botburrow-agents` |
| Release workflow (`.github/workflows/release.yml`) | Pushes to `ghcr.io/ardenone/botburrow-agents` |
| GitHub Actions | Last successful release: 2026-02-14T21:11:01Z |
| Git tag `v0.1.1` | Created 2026-02-14 21:10:56 UTC |

## Image Pull Command

```bash
docker pull ghcr.io/ardenone/botburrow-agents:v0.1.1
# or
docker pull ghcr.io/ardenone/botburrow-agents:latest
```
