# Definitive Answer: Should we use ardenone/botburrow-agents instead?

**Bead:** bd-1w62
**Date:** 2026-03-29

## Answer: YES

The correct image is **`ghcr.io/ardenone/botburrow-agents:latest`** (GitHub Container Registry).

| Image | Status |
|-------|--------|
| `ronaldraygun/botburrow-agents` | **DEPRECATED** — Docker Hub repo deleted/private, not pullable |
| `ardenone/botburrow-agents` (Docker Hub) | Optional secondary push, available when `DOCKERHUB_PASSWORD` secret is set |
| `ghcr.io/ardenone/botburrow-agents` | **CORRECT** — primary registry since 2026-03-17 (commit `2a2a589`) |

## Current State

- The K8s manifests in `k8s/apexalgo-iad/` already reference `ghcr.io/ardenone/botburrow-agents:latest` ✅
- The cluster was running the old `docker.io/ronaldraygun/botburrow-agents:latest` due to ArgoCD not having synced
- `ronaldraygun/botburrow-agents` Docker Hub repo is deleted/private — image pull fails with "repository does not exist"

## No Code Changes Needed

All manifests are already correct. The fix requires an ArgoCD sync of the `botburrow-agents` Application in the apexalgo-iad cluster.
