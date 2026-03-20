# Definitive Answer: When was ronaldraygun/botburrow-agents last built?

**Bead:** bd-bslk
**Date:** 2026-03-20

## Answer

| Property | Value |
|----------|-------|
| **Build-and-push completed** | **2026-03-17T06:42:40Z** |
| **Build job completed** | 2026-03-17T06:42:43Z |
| **Workflow triggered** | 2026-03-17T06:41:24Z |
| **Last Commit** | `8f01f1996eb2c778b4bb4e98a5089736ca08907f` |
| **Short SHA** | `8f01f19` |
| **Commit Date** | 2026-03-17 02:40:41 -0400 |
| **Commit Message** | "chore(bd-31j): close obsolete mitosis-child beads" |
| **GitHub Actions run** | [#23181875444](https://github.com/ardenone/botburrow-agents/actions/runs/23181875444) |
| **Tags pushed** | `ronaldraygun/botburrow-agents:latest`, `ronaldraygun/botburrow-agents:8f01f19` |

## Evidence

1. **GitHub Actions run [#23181875444](https://github.com/ardenone/botburrow-agents/actions/runs/23181875444):** The CI/CD pipeline built and pushed to Docker Hub at 2026-03-17T06:42:40Z for commit `8f01f19`. The workflow at that commit pointed to `docker.io` / `ronaldraygun/botburrow-agents`.

2. **Migration:** On 2026-03-17T09:27:25Z, commit `2a2a589` changed ci-cd.yml from `docker.io`/`ronaldraygun/botburrow-agents` to `ghcr.io`/`ardenone/botburrow-agents`. No subsequent build has pushed to Docker Hub.

3. **Docker Hub repo status:** The Docker Hub API returns "object not found" — the repository has been deleted or made private.

## Last Release Build (Separate from CI/CD)

The `release.yml` workflow also pushed to Docker Hub for the v0.1.1 release:

| Property | Value |
|----------|-------|
| **Release** | v0.1.1 |
| **Build completed** | 2026-02-14T21:12:58Z |
| **Run** | [#22024326118](https://github.com/ardenone/botburrow-agents/actions/runs/22024326118) |
| **Commit** | `a0021f9` — "fix(bd-xou): Fix Docker Hub secret name reference" |

## Status

**DEPRECATED** — The `ronaldraygun/botburrow-agents` image is no longer maintained. All new builds go to `ghcr.io/ardenone/botburrow-agents`.

## See Also

- `docs/verification/image-investigation-bd-212.md` — Full parent investigation (bd-212)
- `bd-93p4-definitive-answer.md` — GHCR migration details
