# bd-9kbm Findings: Is ronaldraygun/botburrow-agents the correct/official image?

**Date:** 2026-04-09
**Bead:** bd-9kbm

## Answer: NO

`ronaldraygun/botburrow-agents` is **NOT** the correct/official image.

## Correct Image

**`ghcr.io/ardenone/botburrow-agents:latest`** (GitHub Container Registry)

## Image Status Reference

| Image | Status |
|-------|--------|
| `ronaldraygun/botburrow-agents` | **DEPRECATED** — Docker Hub repo deleted/private, not pullable |
| `ardenone/botburrow-agents` (Docker Hub) | Optional secondary push, available when `DOCKERHUB_PASSWORD` secret is set |
| `ghcr.io/ardenone/botburrow-agents` | **CORRECT** — primary registry since 2026-03-17 (commit `2a2a589`) |

## Git History Evidence

Multiple commits document this migration:
- `0b100c2` - "document that ghcr.io/ardenone/botburrow-agents is the correct image"
- `bba99af` - "document that ronaldraygun/botburrow-agents is not the correct image"
- `823b9d9` - "document that ronaldraygun/botburrow-agents is not the correct image"

## References

- See `bd-1w62-definitive-answer.md` for complete details
- See `bd-32g-final-status.md` for deployment status showing the migration in progress
