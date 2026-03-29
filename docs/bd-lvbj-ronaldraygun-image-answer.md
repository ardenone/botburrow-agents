---
bead: bd-lvbj
task: Is ronaldraygun/botburrow-agents the correct/official image?
status: closed
---

# Is ronaldraygun/botburrow-agents the correct image? — bd-lvbj

## Answer: No

`ronaldraygun/botburrow-agents` is **not** the correct/official image. It is deprecated.

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Summary

The project migrated from Docker Hub (`ronaldraygun/botburrow-agents`) to GitHub Container
Registry (`ghcr.io/ardenone/botburrow-agents`) in commit `2a2a589` on 2026-03-17.

- All K8s manifests in `k8s/apexalgo-iad/` reference `ghcr.io/ardenone/botburrow-agents:latest`
- CI/CD workflows build and push to `ghcr.io/ardenone/botburrow-agents`
- Zero references to `ronaldraygun` in active source code

See also: `docs/bd-5trf-ronaldraygun-image-answer.md`, `docs/bd-0hd7-ronaldraygun-image-answer.md`
