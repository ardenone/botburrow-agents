# Definitive Answer: Should we be using ardenone/botburrow-agents instead?

**Bead:** bd-4n4j
**Date:** 2026-03-20

## Answer

**YES** — We should be using `ghcr.io/ardenone/botburrow-agents:latest`, NOT `ronaldraygun/botburrow-agents`.

## Correct/Official Image

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Summary

| Property | ronaldraygun/botburrow-agents | ghcr.io/ardenone/botburrow-agents |
|----------|-------------------------------|-----------------------------------|
| **Status** | **DEPRECATED** | Active, continuously built |
| **Registry** | Docker Hub | GitHub Container Registry |
| **CI/CD** | No longer updated | Built on every push to `main` |
| **Docker Hub repo** | Deleted/private | N/A |

## Evidence

1. **Migration commit `2a2a589`** (2026-03-17): CI/CD pipeline was changed from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`).

2. **Docker Hub repo deleted/private:** The Docker Hub API returns "object not found" for `ronaldraygun/botburrow-agents`.

3. **All K8s manifests** in the cluster-configuration repo already reference `ghcr.io/ardenone/botburrow-agents:latest`.

4. **CI/CD** (`.github/workflows/ci-cd.yml`) builds and pushes to GHCR with `:latest` and `:<short-sha>` tags on every push to `main`.

## Action Required

If any running pods still reference `ronaldraygun/botburrow-agents`, they need to be updated via ArgoCD sync to pick up the correct image.

## See Also

- `bd-v27h-definitive-answer.md` — Is ronaldraygun the correct image? (NO)
- `bd-bslk-definitive-answer.md` — When was ronaldraygun last built?
- `bd-7cxe-definitive-answer.md` — Last ronaldraygun commit was `8f01f19`
