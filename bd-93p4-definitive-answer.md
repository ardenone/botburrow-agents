# Definitive Answer: Should we use ardenone/botburrow-agents?

**Bead:** bd-93p4
**Question:** Should we be using `ardenone/botburrow-agents` instead of `ronaldraygun/botburrow-agents`?
**Answer:** **YES**

## TL;DR

Use `ghcr.io/ardenone/botburrow-agents:latest` — the `ronaldraygun/botburrow-agents` Docker Hub image is **deprecated**.

## Details

| Property | Old (Deprecated) | New (Current) |
|----------|------------------|---------------|
| **Registry** | docker.io | ghcr.io |
| **Image** | ronaldraygun/botburrow-agents | ardenone/botburrow-agents |
| **Status** | ❌ Deprecated | ✅ Active |
| **Last Build** | 2026-03-17 02:40:41 | Continuous (CI/CD) |

## Migration History

- **Migration Commit:** `2a2a589` (2026-03-17 05:27:19)
- **Last commit in Docker Hub image:** `8f01f19` (2026-03-17 02:40:41)
- **All K8s manifests updated:** Yes (see `k8s/apexalgo-iad/`)

## Correct Image Reference

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Why the Change?

1. GitHub Container Registry (GHCR) is better integrated with the GitHub Actions CI/CD pipeline
2. GHCR provides better security and access control
3. The image name now matches the GitHub organization (`ardenone`)

## See Also

- `bd-7cxe-investigation-findings.md` - Full investigation of the legacy image
- `bd-32g-verification-report.md` - Verification of image migration
