---
bead: bd-9kbm
task: Is ronaldraygun/botburrow-agents the correct/official image?
status: closed
---

# Is ronaldraygun/botburrow-agents the correct/official image? — bd-9kbm

## Answer: No

`ronaldraygun/botburrow-agents` is **not** the correct or official image.

The official image is:

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Why Not `ronaldraygun/botburrow-agents`?

- It is **deprecated** — last build was `v0.1.1` on 2026-02-14
- The project migrated from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`) on 2026-03-17
  in commit `2a2a589` (`fix(bd-93p4): migrate image refs from ronaldraygun to ghcr.io/ardenone`)
- All subsequent releases publish exclusively to `ghcr.io/ardenone/botburrow-agents`

## References

- `docs/bd-s3fb-ronaldraygun-image-answer.md` — same question, answered previously
- `docs/bd-bzvl-ardenone-image-answer.md` — confirms ghcr.io/ardenone is correct
- `docs/bd-0hd7-ronaldraygun-image-answer.md` — confirms ronaldraygun is deprecated
