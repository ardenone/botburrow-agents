# bd-1fh9: Is ronaldraygun/botburrow-agents the correct/official image?

## Answer: No

`ronaldraygun/botburrow-agents` is **not** the correct or official image. This is a duplicate of bd-lrkr, which already established the definitive answer.

## Official Image

**`ghcr.io/ardenone/botburrow-agents`**

## Why

1. **CI/CD pushes to GHCR** — Both `.github/workflows/ci-cd.yml` and `.github/workflows/release.yml` push to `ghcr.io/ardenone/botburrow-agents`. No Docker Hub push step exists.

2. **All K8s manifests use GHCR** — Every manifest under `k8s/apexalgo-iad/` references `ghcr.io/ardenone/botburrow-agents:latest`.

3. **Migration completed 2026-03-17** — Commit `2a2a589` migrated all references from Docker Hub to GHCR. The `ronaldraygun` image has received no builds since.

4. **`ronaldraygun` is inaccessible** — Pulling `docker.io/ronaldraygun/botburrow-agents:latest` fails with "pull access denied".

## See Also

- bd-lrkr-definitive-answer.md — Original investigation with the same conclusion
- bd-segw-definitive-answer.md — Follow-on confirming `ardenone/botburrow-agents` on GHCR is correct
