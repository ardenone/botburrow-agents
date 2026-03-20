# bd-txuz: Docker Hub repository `ardenone/botburrow-agents` doesn't exist

## Answer: NOT REQUIRED — Project uses GHCR

The Docker Hub repository `ardenone/botburrow-agents` **does not need to exist** because the project has migrated to GitHub Container Registry (GHCR).

## Summary

| Registry | Image | Status |
|----------|-------|--------|
| Docker Hub | `ardenone/botburrow-agents` | Never created — not needed |
| Docker Hub | `ronaldraygun/botburrow-agents` | Deprecated/deleted |
| GHCR | `ghcr.io/ardenone/botburrow-agents` | **Active** — built on every push to main |

## Evidence

1. **CI/CD workflow** (`.github/workflows/ci-cd.yml`):
   - `REGISTRY: ghcr.io`
   - `IMAGE_NAME: ardenone/botburrow-agents`
   - Uses `GITHUB_TOKEN` for authentication (no Docker Hub secrets needed)

2. **Release workflow** (`.github/workflows/release.yml`):
   - Same GHCR configuration
   - Tags pushed to GHCR, not Docker Hub

3. **Parent bead (bd-31j)** was closed as "done" because the solution was to switch to GHCR

4. **Migration completed** in commit `2a2a589` (2026-03-17)

## Correct Image Reference

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## No Action Required

The Docker Hub repository doesn't need to be created. The project's CI/CD pipeline successfully builds and pushes to GHCR.

## See Also

- `bd-ur5o-definitive-answer.md` — Migration from Docker Hub to GHCR
- `bd-fi7h-definitive-answer.md` — Correct image reference
- `bd-jj01-definitive-answer.md` — ronaldraygun image is NOT official
