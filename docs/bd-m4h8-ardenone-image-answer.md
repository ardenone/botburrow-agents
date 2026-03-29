---
bead: bd-m4h8
task: Should we be using ardenone/botburrow-agents instead?
status: closed
---

# Should we be using ardenone/botburrow-agents instead? — bd-m4h8

## Answer: Yes — specifically `ghcr.io/ardenone/botburrow-agents`

We should use `ghcr.io/ardenone/botburrow-agents` (GitHub Container Registry), not
`ronaldraygun/botburrow-agents` on Docker Hub.

Note: `ardenone/botburrow-agents` on Docker Hub does **not** exist.

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Why Not `ronaldraygun/botburrow-agents`?

- `ronaldraygun/botburrow-agents` on Docker Hub is **deprecated** — last build was
  `v0.1.1` on 2026-02-14
- The project migrated from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`) on 2026-03-17
  in commit `2a2a589` (`fix(bd-93p4): migrate image refs from ronaldraygun to ghcr.io/ardenone`)
- All subsequent releases publish exclusively to GHCR
- CI/CD (`.github/workflows/ci-cd.yml`, `release.yml`) builds and pushes to `ghcr.io/ardenone/botburrow-agents`

## Status

No action required — all K8s manifests in `k8s/apexalgo-iad/` already reference
`ghcr.io/ardenone/botburrow-agents:latest`. Migration is complete.

## References

- `docs/bd-j36d-ardenone-image-answer.md` — previous investigation (same question)
- `docs/bd-waq9-ardenone-image-answer.md` — previous investigation (same question)
- `docs/bd-ggct-ronaldraygun-image-answer.md` — confirms `ronaldraygun` is deprecated
