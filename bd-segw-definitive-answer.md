# bd-segw: Should we be using ardenone/botburrow-agents instead?

## Answer: Yes

**`ghcr.io/ardenone/botburrow-agents`** is the correct image to use. `ronaldraygun/botburrow-agents` is the deprecated Docker Hub image and should not be used.

## Correct Image Reference

```
ghcr.io/ardenone/botburrow-agents:latest
ghcr.io/ardenone/botburrow-agents:v<semver>
```

## Why

1. **CI/CD pushes to GHCR** — Both `.github/workflows/ci-cd.yml` and `.github/workflows/release.yml` push to `ghcr.io/ardenone/botburrow-agents`. No Docker Hub push step exists.

2. **All k8s manifests use GHCR** — Every manifest under `k8s/apexalgo-iad/` references `ghcr.io/ardenone/botburrow-agents:latest`.

3. **Migration completed 2026-03-17** — Commit `2a2a589` migrated all references from Docker Hub to GHCR. The `ronaldraygun` image has received no builds since commit `8f01f19` on that date.

4. **`ronaldraygun` is inaccessible** — Attempting to pull `docker.io/ronaldraygun/botburrow-agents:latest` fails with "pull access denied, repository does not exist or may require authorization".

## Relationship to bd-lrkr

This bead is the direct follow-on to bd-lrkr ("Is ronaldraygun/botburrow-agents the correct/official image?"), which concluded it is **not** correct. The answer to this bead follows directly: yes, use `ardenone/botburrow-agents` (on GHCR) instead.
