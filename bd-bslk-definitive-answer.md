# Definitive Answer: When was ronaldraygun/botburrow-agents last built?

**Bead:** bd-bslk
**Date:** 2026-03-20

## Answer

| Property | Value |
|----------|-------|
| **Last Build Date** | **2026-03-17 06:41:24 UTC** |
| **Last Commit** | `8f01f1996eb2c778b4bb4e98a5089736ca08907f` |
| **Short SHA** | `8f01f19` |
| **Commit Date** | 2026-03-17 02:40:41 -0400 |
| **Commit Message** | "chore(bd-31j): close obsolete mitosis-child beads" |

## Evidence

1. **GitHub Actions Workflow Run:** The CI/CD pipeline executed for commit `8f01f19` on 2026-03-17T06:41:24Z, building and pushing `docker.io/ronaldraygun/botburrow-agents:latest` and `docker.io/ronaldraygun/botburrow-agents:8f01f19`

2. **Migration:** On 2026-03-17 05:27:19, commit `2a2a589` migrated all image references from Docker Hub (`ronaldraygun/botburrow-agents`) to GitHub Container Registry (`ghcr.io/ardenone/botburrow-agents`)

## Status

**DEPRECATED** - The `ronaldraygun/botburrow-agents` image is no longer maintained. All new builds go to `ghcr.io/ardenone/botburrow-agents`.
