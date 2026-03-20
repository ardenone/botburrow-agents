# Definitive Answer: Is ronaldraygun/botburrow-agents the correct/official image?

**Bead:** bd-tyq6
**Date:** 2026-03-20

## Answer

**NO** — `ronaldraygun/botburrow-agents` is NOT the correct/official image.

## Correct Image

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Summary

| Property | ronaldraygun/botburrow-agents | ghcr.io/ardenone/botburrow-agents |
|----------|-------------------------------|-----------------------------------|
| **Status** | DEPRECATED / deleted | ACTIVE (official) |
| **Registry** | Docker Hub | GitHub Container Registry |
| **Last build** | 2026-03-17 (commit `8f01f19`) | Current HEAD (auto-built) |
| **CI/CD** | No longer updated | Built on every push to `main` |

## Evidence

1. **Docker Hub repo is deleted/private** — API returns "object not found"
2. **Migration commit `2a2a589`** (2026-03-17): CI/CD migrated from Docker Hub to GHCR
3. **All K8s manifests** in this repo reference `ghcr.io/ardenone/botburrow-agents:latest`
4. **CI/CD pipeline** (`.github/workflows/ci-cd.yml`) pushes to GHCR only

## Action Required

Any pods still referencing `ronaldraygun/botburrow-agents` must be updated to use `ghcr.io/ardenone/botburrow-agents`.

## See Also

- `bd-y47f-definitive-answer.md` — Should we use ardenone instead? (YES)
- `bd-wmfw-definitive-answer.md` — Last ronaldraygun commit was `8f01f19`
- `bd-93p4-definitive-answer.md` — GHCR migration confirmation
