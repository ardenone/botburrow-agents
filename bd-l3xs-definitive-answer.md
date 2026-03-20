# Definitive Answer: Is ronaldraygun/botburrow-agents the correct/official image?

**Bead:** bd-l3xs
**Date:** 2026-03-20

## Answer

**No.** `ronaldraygun/botburrow-agents` is **NOT** the correct/official image. It is **DEPRECATED** and no longer maintained.

## Correct Image

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Evidence

1. **CI/CD Configuration** (`.github/workflows/ci-cd.yml`):
   - Registry: `ghcr.io`
   - Image: `ardenone/botburrow-agents`

2. **Migration History**:
   - On 2026-03-17T09:27:25Z, commit `2a2a589` migrated from Docker Hub (`ronaldraygun/botburrow-agents`) to GHCR (`ardenone/botburrow-agents`)
   - The last build to Docker Hub was 2026-03-17T06:42:40Z for commit `8f01f19`

3. **Docker Hub Status**:
   - The `ronaldraygun/botburrow-agents` repository is deleted or private
   - Docker Hub API returns "object not found"

4. **Zero Active References**:
   - No source code, manifests, or Dockerfiles reference `ronaldraygun`
   - All K8s manifests use `ghcr.io/ardenone/botburrow-agents`

## See Also

- `bd-y8in-definitive-answer.md` — Confirmation that ardenone/botburrow-agents is correct
- `bd-bslk-definitive-answer.md` — Timeline of Docker Hub deprecation
