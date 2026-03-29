---
bead: bd-a7vw
task: Should we be using ardenone/botburrow-agents instead?
status: closed
---

# Should we be using ardenone/botburrow-agents instead? — bd-a7vw

## Answer: Yes — specifically `ghcr.io/ardenone/botburrow-agents`

We should use `ghcr.io/ardenone/botburrow-agents` (GitHub Container Registry), not
`ronaldraygun/botburrow-agents` on Docker Hub.

Note: `ardenone/botburrow-agents` on Docker Hub does **not** exist and was never created.

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Why Not `ronaldraygun/botburrow-agents`?

- `ronaldraygun/botburrow-agents` on Docker Hub is **deprecated** — last build was
  `v0.1.1` on 2026-02-14
- The project migrated from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`) in commit
  `2a2a589` (`fix(bd-93p4): migrate image refs from ronaldraygun to ghcr.io/ardenone`)
- All subsequent releases publish exclusively to GHCR

## Status

No action required — all K8s manifests in `k8s/apexalgo-iad/` already reference
`ghcr.io/ardenone/botburrow-agents:latest`. Migration is complete.

## References

- `docs/bd-mbos-ardenone-image-answer.md` — previous investigation (same question)
- `docs/bd-ojcs-ardenone-image-answer.md` — previous investigation (same question)
- `docs/bd-xmpb-ardenone-image-answer.md` — earlier investigation (same question)
- `docs/bd-5trf-ronaldraygun-image-answer.md` — confirms `ronaldraygun` is deprecated
- `docs/bd-wtp9-ardenone-image-answer.md` — confirms GHCR is the official registry
- `docs/bd-7y9w-dockerhub-ardenone-missing.md` — confirms Docker Hub `ardenone` repo doesn't exist
