# Definitive Answer: Should we use ardenone/botburrow-agents instead?

**Bead:** bd-y47f
**Date:** 2026-03-20

## Answer

**YES** — we should be using `ghcr.io/ardenone/botburrow-agents` instead of `ronaldraygun/botburrow-agents`.

## Summary

| | ronaldraygun/botburrow-agents | ardenone/botburrow-agents |
|---|---|---|
| **Registry** | Docker Hub | GitHub Container Registry (GHCR) |
| **Status** | Deprecated / deleted | Active, continuously built |
| **Last build** | 2026-03-17 (commit `8f01f19`) | Current HEAD |
| **CI/CD** | No longer updated | Built on every push to `main` |

## Evidence

1. **Migration commit `2a2a589`** (2026-03-17): CI/CD pipeline changed from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`).
2. **Docker Hub repo** `ronaldraygun/botburrow-agents` is deleted or private — API returns "object not found".
3. **All K8s manifests** in this repo already reference `ghcr.io/ardenone/botburrow-agents:latest`.
4. **CI/CD** (`.github/workflows/ci-cd.yml`) builds and pushes to GHCR with both `:latest` and `:<short-sha>` tags.

## Correct Image Reference

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## See Also

- `bd-9doc-definitive-answer.md` — Is ronaldraygun the correct/official image? (NO)
- `bd-93p4-definitive-answer.md` — GHCR migration confirmation
- `bd-7cxe-definitive-answer.md` — Last ronaldraygun commit was `8f01f19`
