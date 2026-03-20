# Definitive Answer: bd-4n4j

**Question:** Should we be using `ardenone/botburrow-agents` instead of `ronaldraygun/botburrow-agents`?
**Answer:** **YES**

## TL;DR

Use `ghcr.io/ardenone/botburrow-agents:latest` — the `ronaldraygun/botburrow-agents` Docker Hub image is **deprecated**.

## Details

| Property | Old (Deprecated) | New (Current) |
|----------|------------------|---------------|
| **Registry** | docker.io | ghcr.io |
| **Image** | ronaldraygun/botburrow-agents | ardenone/botburrow-agents |
| **Status** | Deprecated | Active |
| **Last Build** | 2026-03-17 (final) | Continuous (CI/CD) |

## Evidence

1. **All K8s manifests** in `k8s/apexalgo-iad/` already reference `ghcr.io/ardenone/botburrow-agents:latest`
2. **CI/CD workflows** (`.github/workflows/ci-cd.yml`, `release.yml`) build and push only to GHCR
3. **Migration commit:** `2a2a589` (2026-03-17) — Docker Hub image was the last pre-migration build
4. The `ardenone` org matches the GitHub organization; `ronaldraygun` was a personal account used before org migration

## Correct Image Reference

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Note

The GHCR package is currently private. The cluster needs a GHCR pull secret to actually pull it.
The manifests are already correct — the remaining work is configuring cluster authentication.
