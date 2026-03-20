# Definitive Answer: Is ronaldraygun/botburrow-agents the correct/official image?

**Bead:** bd-v27h
**Date:** 2026-03-20

## Answer

**NO** — `ronaldraygun/botburrow-agents` is **NOT** the correct/official image. It is deprecated.

## Correct/Official Image

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Summary

| Property | ronaldraygun/botburrow-agents | ardenone/botburrow-agents |
|----------|-------------------------------|---------------------------|
| **Registry** | Docker Hub | GitHub Container Registry (GHCR) |
| **Status** | Deprecated / deleted | Active, continuously built |
| **Migration date** | 2026-03-17 | Current |
| **CI/CD** | No longer updated | Built on every push to `main` |

## Evidence

1. **Migration commit `2a2a589`** (2026-03-17): CI/CD pipeline was changed from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`).
2. **Docker Hub repo** `ronaldraygun/botburrow-agents` is deleted or private — Docker API returns "object not found".
3. **All K8s manifests** already reference `ghcr.io/ardenone/botburrow-agents:latest`.
4. **CI/CD** (`.github/workflows/ci-cd.yml`) builds and pushes to GHCR with `:latest` and `:<short-sha>` tags.

## See Also

- `bd-9doc-definitive-answer.md` — Prior investigation confirming the same answer
- `bd-y47f-definitive-answer.md` — Should we use ardenone instead? (YES)
- `bd-bslk-definitive-answer.md` — When was ronaldraygun last built?
- `bd-7cxe-definitive-answer.md` — Last ronaldraygun commit was `8f01f19`
