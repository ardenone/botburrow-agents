# bd-4n4j: Should we be using ardenone/botburrow-agents instead?

## Answer: YES — already migrated

`ghcr.io/ardenone/botburrow-agents:latest` is the correct and only actively maintained image.

## Evidence

- **Migration completed** 2026-03-17 in commit `2a2a589`: `fix(bd-93p4): migrate image refs from ronaldraygun/botburrow-agents to ghcr.io/ardenone/botburrow-agents`
- **All active config** (K8s manifests, CI/CD workflows) already references `ghcr.io/ardenone/botburrow-agents`
- **Zero references to `ronaldraygun`** in any source code, manifests, or Dockerfiles
- **Old Docker Hub repo** (`ronaldraygun/botburrow-agents`) is deleted/private — no longer accessible
- **GHCR package** is actively built on every push to `main` via `.github/workflows/ci-cd.yml` and `release.yml`

## No action required

The migration was already done. Multiple prior beads (bd-v27h, bd-y47f, bd-7jh5, bd-93p4, bd-xwf3, bd-dq2b) all independently confirmed the same answer.
