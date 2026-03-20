# Definitive Answer: Is ronaldraygun/botburrow-agents the correct/official image?

**Bead:** bd-9doc
**Date:** 2026-03-20

## Answer

**NO** — `ronaldraygun/botburrow-agents` is **NOT** the correct/official image. It is **deprecated**.

## Correct/Official Image

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Evidence

| Property | Value |
|----------|-------|
| **Legacy Registry** | Docker Hub (`docker.io/ronaldraygun/botburrow-agents`) |
| **Official Registry** | GitHub Container Registry (`ghcr.io/ardenone/botburrow-agents`) |
| **Migration Date** | 2026-03-17T09:27:25Z |
| **Migration Commit** | `2a2a589` |
| **Last Docker Hub Build** | 2026-03-17T06:42:40Z (commit `8f01f19`) |

### Migration Details

1. **Before migration:** All builds pushed to `docker.io/ronaldraygun/botburrow-agents`
2. **Commit `2a2a589`:** Changed CI/CD from Docker Hub to GHCR
3. **After migration:** All new builds push to `ghcr.io/ardenone/botburrow-agents`
4. **Docker Hub repo:** Deleted or made private — API returns "object not found"

### Current K8s Configuration

All K8s manifests in this repository now reference the correct GHCR image:

- `k8s/apexalgo-iad/coordinator.yaml`
- `k8s/apexalgo-iad/runner-*.yaml`
- `k8s/apexalgo-iad/skill-sync.yaml`
- `k8s/apexalgo-iad/kustomization-gitops.yaml`

## See Also

- `bd-bslk-definitive-answer.md` — When was ronaldraygun/botburrow-agents last built?
- `bd-93p4-definitive-answer.md` — GHCR migration details
- `bd-1f68-definitive-answer.md` — Full registry configuration
- `bd-7cxe-investigation-findings.md` — Investigation details
