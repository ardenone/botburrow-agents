---
bead: bd-s3fb
task: Is ronaldraygun/botburrow-agents the correct/official image?
status: closed
---

# Is ronaldraygun/botburrow-agents the correct/official image? — bd-s3fb

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

- `docs/bd-m4h8-ardenone-image-answer.md` — same question, answered 2026-03-29
- `docs/bd-j36d-ardenone-image-answer.md` — earlier investigation
- `docs/bd-waq9-ardenone-image-answer.md` — earlier investigation
