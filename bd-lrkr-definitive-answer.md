# bd-lrkr: Is ronaldraygun/botburrow-agents the correct/official image?

## Answer: No

`ronaldraygun/botburrow-agents` is **not** the correct or official image. It is the **deprecated** Docker Hub image that was replaced on 2026-03-17.

## Official Image

**`ghcr.io/ardenone/botburrow-agents`**

Tags:
- `:latest` — current build
- `:v<semver>` — versioned releases (e.g., `:v1.0.0`)

## Evidence

1. **CI/CD** — Both `.github/workflows/ci-cd.yml` and `.github/workflows/release.yml` push to `ghcr.io/ardenone/botburrow-agents`. No Docker Hub push exists.

2. **Kubernetes manifests** — All `k8s/apexalgo-iad/` manifests reference `ghcr.io/ardenone/botburrow-agents:latest`.

3. **Migration** — Commit `2a2a589` (2026-03-17) migrated all references from Docker Hub to GHCR. The last `ronaldraygun` build was commit `8f01f19` on the same date.

4. **README** — References only `ghcr.io/ardenone/botburrow-agents`; no mention of `ronaldraygun`.

## Summary

`ronaldraygun/botburrow-agents` was the original Docker Hub image during early development. It was migrated to `ghcr.io/ardenone/botburrow-agents` on 2026-03-17 for better integration with GitHub Actions (automatic `GITHUB_TOKEN` auth, no Docker Hub secrets needed). The `ronaldraygun` image is stale and should not be used.
