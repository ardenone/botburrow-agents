# bd-y8in: Should we be using ardenone/botburrow-agents instead?

## Answer: Yes — and the migration is already complete

The correct image is **`ghcr.io/ardenone/botburrow-agents`**. The project migrated from `ronaldraygun/botburrow-agents` on Docker Hub to `ghcr.io/ardenone/botburrow-agents` on GitHub Container Registry.

## Current State

| Image | Registry | Status |
|-------|----------|--------|
| `ronaldraygun/botburrow-agents` | Docker Hub | DELETED — no longer accessible |
| `ghcr.io/ardenone/botburrow-agents` | GHCR | Active — CI/CD builds on every push |

## Evidence

1. **CI/CD uses GHCR** — `.github/workflows/ci-cd.yml` pushes to `ghcr.io/ardenone/botburrow-agents`
2. **All K8s manifests use GHCR** — Every manifest under `k8s/apexalgo-iad/` references `ghcr.io/ardenone/botburrow-agents:latest`
3. **Migration commit** — `2a2a589` (2026-03-17) completed the migration
4. **ronaldraygun is gone** — Docker Hub repo deleted/inaccessible; `docker pull` fails with "pull access denied"

## Prior Investigations

This has been answered definitively in multiple prior beads:
- bd-93p4 — Same question, same answer
- bd-1fh9 — Confirmed ronaldraygun is not the correct image
- bd-lrkr — Original investigation establishing GHCR as official registry
- bd-212 — Full investigation of image version discrepancy
