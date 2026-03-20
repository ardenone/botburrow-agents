# Definitive Answer: Is ronaldraygun/botburrow-agents the correct/official image?

**Bead ID:** bd-9doc
**Date:** 2026-03-20
**Answer:** **NO**

## Summary

`ronaldraygun/botburrow-agents` is **NOT** the correct/official image. It is a **deprecated legacy image** that was migrated away from on 2026-03-17.

## Correct/Official Image

```
ghcr.io/ardenone/botburrow-agents
```

This is configured in:
- `.github/workflows/release.yml` (line 9-10)
- `.github/workflows/ci-cd.yml` (line 15-16)

## Migration Details

| Property | Value |
|----------|-------|
| **Legacy Registry** | `docker.io/ronaldraygun/botburrow-agents` |
| **Current Registry** | `ghcr.io/ardenone/botburrow-agents` |
| **Migration Commit** | `2a2a589` |
| **Migration Date** | 2026-03-17 05:27:19 |

## Evidence

1. **CI/CD Configuration** - Both workflow files specify `ghcr.io/ardenone/botburrow-agents`
2. **K8s Manifests** - All Kubernetes manifests use `ghcr.io/ardenone/botburrow-agents:latest`
3. **Previous Investigation** - bd-7cxe documented the migration from Docker Hub to GHCR

## Recommendation

Do NOT use `ronaldraygun/botburrow-agents`. Always use:

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Related

- bd-7cxe - Original investigation into ronaldraygun/botburrow-agents image version
- bd-93p4 - Migration from Docker Hub to GHCR
