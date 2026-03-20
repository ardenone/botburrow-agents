# Definitive Answer: Is ronaldraygun/botburrow-agents the correct/official image?

**Bead:** bd-jj01
**Date:** 2026-03-20

## Answer

**NO** — `ronaldraygun/botburrow-agents` is **NOT** the correct/official image. It is deprecated.

## Correct/Official Image

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Summary

| Property | ronaldraygun/botburrow-agents | ghcr.io/ardenone/botburrow-agents |
|----------|-------------------------------|-----------------------------------|
| **Registry** | Docker Hub | GitHub Container Registry (GHCR) |
| **Status** | Deprecated / deleted | Active, continuously built |
| **Last build** | 2026-03-17 (commit `8f01f19`) | Current HEAD (auto-built) |
| **CI/CD** | No longer updated | Built on every push to `main` |
| **Accessible** | No — repo deleted/private | Yes |

## Evidence

1. **Migration commit `2a2a589`** (2026-03-17): CI/CD pipeline migrated from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`).
2. **Docker Hub repo** `ronaldraygun/botburrow-agents` is deleted or private — Docker API returns "object not found".
3. **All K8s manifests** in this repo already reference `ghcr.io/ardenone/botburrow-agents:latest`.
4. **CI/CD** (`.github/workflows/ci-cd.yml`) builds and pushes to GHCR with both `:latest` and `:<short-sha>` tags.

## Action Required

Any pods still referencing `ronaldraygun/botburrow-agents` must be updated to use `ghcr.io/ardenone/botburrow-agents:latest`.

## See Also

- `bd-v27h-definitive-answer.md` — Same question answered
- `bd-tyq6-definitive-answer.md` — Same question answered
- `bd-ur5o-definitive-answer.md` — Use ardenone instead (YES)
- `bd-wmfw-definitive-answer.md` — Last ronaldraygun commit was `8f01f19`
