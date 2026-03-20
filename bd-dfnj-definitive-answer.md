# Definitive Answer: bd-dfnj

## Question
What commit/version does ronaldraygun/botburrow-agents contain?

## Answer

The `ronaldraygun/botburrow-agents` image contains commit **`8f01f19`**.

| Property | Value |
|----------|-------|
| **Full SHA** | `8f01f1996eb2c778b4bb4e98a5089736ca08907f` |
| **Short SHA** | `8f01f19` |
| **Commit Date** | 2026-03-17T06:42:40Z (2026-03-17 02:40:41 -0400) |
| **Commit Message** | "chore(bd-31j): close obsolete mitosis-child beads" |
| **Image Tags** | `ronaldraygun/botburrow-agents:latest`, `ronaldraygun/botburrow-agents:8f01f19` |
| **Status** | DEPRECATED — no new builds since this commit |

## Evidence

- The CI/CD GitHub Actions run that built the image pushed both `:latest` and `:8f01f19` tags simultaneously
- The `ronaldraygun/botburrow-agents` Docker Hub repo is now deleted/private
- CI/CD migrated to GHCR on 2026-03-17 (commit `2a2a589`), so no new images have been pushed to ronaldraygun since

## Current Recommendation

Use the current GHCR image instead:
```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## See Also

- `bd-wmfw-definitive-answer.md` — Prior investigation (same answer)
- `bd-upce-definitive-answer.md` — Another prior investigation (same answer)
- `bd-bslk-definitive-answer.md` — When was the image last built?
- `bd-v27h-definitive-answer.md` — Is ronaldraygun the correct/official image? (NO)
