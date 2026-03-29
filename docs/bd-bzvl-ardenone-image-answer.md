---
bead: bd-bzvl
task: Should we be using ardenone/botburrow-agents instead?
status: closed
---

# Should we be using ardenone/botburrow-agents instead? — bd-bzvl

## Answer: Yes — specifically `ghcr.io/ardenone/botburrow-agents`

The correct image is `ghcr.io/ardenone/botburrow-agents:latest` (GitHub Container Registry).

Note: `ardenone/botburrow-agents` on Docker Hub does **not** exist.

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Why Not `ronaldraygun/botburrow-agents`?

- `ronaldraygun/botburrow-agents` on Docker Hub is **deprecated** — last build was `v0.1.1` on 2026-02-14
- The project migrated from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`) on 2026-03-17
  in commit `2a2a589` (`fix(bd-93p4): migrate image refs from ronaldraygun to ghcr.io/ardenone`)
- All K8s manifests in `k8s/apexalgo-iad/` already reference `ghcr.io/ardenone/botburrow-agents:latest`
- CI/CD workflows build and push exclusively to `ghcr.io/ardenone/botburrow-agents`

## Status

No action required — migration is complete.

## References

- `docs/bd-waq9-ardenone-image-answer.md` — previous investigation (same question)
- `docs/bd-0hd7-ronaldraygun-image-answer.md` — confirms `ronaldraygun` is deprecated
