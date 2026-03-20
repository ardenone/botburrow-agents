# Answer: Should we use ardenone/botburrow-agents instead?

**Bead:** bd-93p4
**Date:** 2026-03-20
**Question:** Should we be using ardenone/botburrow-agents instead?

## TL;DR

**YES.** Use `ghcr.io/ardenone/botburrow-agents` — the project has already migrated.

## Answer Table

| Image | Status | Recommendation |
|-------|--------|----------------|
| `ronaldraygun/botburrow-agents` | **DEPRECATED** | Do NOT use |
| `ghcr.io/ardenone/botburrow-agents` | **CURRENT** | Use this |

## Evidence

### 1. Migration Already Complete

The migration from Docker Hub (`ronaldraygun/botburrow-agents`) to GitHub Container Registry (`ghcr.io/ardenone/botburrow-agents`) was completed in commit `2a2a589` on 2026-03-17.

### 2. CI/CD Uses GHCR

The `.github/workflows/ci-cd.yml` is configured to push to GHCR:

```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ardenone/botburrow-agents
```

### 3. K8s Manifests Use GHCR

All K8s manifests in `k8s/apexalgo-iad/` reference `ghcr.io/ardenone/botburrow-agents:latest`.

### 4. Docker Hub Image is Stale

The last `ronaldraygun/botburrow-agents` image was built from commit `8f01f19` (2026-03-17 02:40:41). No further updates are pushed there.

## Prior Investigation

Full details documented in:
- `bd-7cxe-investigation-findings.md`
- `docs/verification/ronaldraygun-image-version-bd-7cxe.md`

## Conclusion

The question is answered definitively: **Yes, use `ghcr.io/ardenone/botburrow-agents`.** The migration is complete and `ronaldraygun/botburrow-agents` is deprecated.
