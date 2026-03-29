---
bead: bd-xmpb
task: Should we be using ardenone/botburrow-agents instead?
status: closed
---

# Should we be using ardenone/botburrow-agents instead? — bd-xmpb

## Answer: Yes — specifically `ghcr.io/ardenone/botburrow-agents`

We should use `ghcr.io/ardenone/botburrow-agents` (GitHub Container Registry).

Note: `ardenone/botburrow-agents` on Docker Hub does **not** exist and was never created.

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Why Not `ronaldraygun/botburrow-agents`?

- `ronaldraygun/botburrow-agents` on Docker Hub is **deprecated** — its last (and only) build
  was `v0.1.1` on 2026-02-14
- The project migrated from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`) in commit `2a2a589`
  (`fix(bd-93p4): migrate image refs from ronaldraygun/botburrow-agents to ghcr.io/ardenone/botburrow-agents`)
- All subsequent releases are published exclusively to GHCR

## Status

No action required — all K8s manifests in `k8s/apexalgo-iad/` already reference
`ghcr.io/ardenone/botburrow-agents:latest`. The migration is complete.

## References

- `docs/bd-5trf-ronaldraygun-image-answer.md` — confirms `ronaldraygun` is deprecated
- `docs/bd-wtp9-ardenone-image-answer.md` — confirms GHCR is the official registry
- `docs/bd-7y9w-dockerhub-ardenone-missing.md` — confirms Docker Hub `ardenone` repo doesn't exist
- `docs/verification/ronaldraygun-image-version-bd-7cxe.md` — full version history
