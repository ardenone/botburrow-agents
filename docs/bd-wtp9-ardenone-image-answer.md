---
bead: bd-wtp9
task: Should we be using ardenone/botburrow-agents instead?
status: closed
---

# Should we be using ardenone/botburrow-agents instead? — bd-wtp9

## Answer: Yes

We should use `ghcr.io/ardenone/botburrow-agents` (GHCR), not `ronaldraygun/botburrow-agents` (Docker Hub).

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Evidence

- All K8s manifests (`k8s/apexalgo-iad/*.yaml`) reference `ghcr.io/ardenone/botburrow-agents:latest`
- CI/CD pipelines (`.github/workflows/ci-cd.yml`, `release.yml`) build and push to `ghcr.io/ardenone/botburrow-agents`
- `ronaldraygun/botburrow-agents` on Docker Hub is deleted/private — no longer accessible
- Migration from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`) occurred on 2026-03-17 (commit `2a2a589`)
- Zero references to `ronaldraygun` in any active source code (`.yaml`, `.py`, `.toml`)

## Status

No action required — manifests are already correct. This finding confirms the existing configuration is canonical.
