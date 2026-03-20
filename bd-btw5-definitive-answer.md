# bd-btw5: Is ronaldraygun/botburrow-agents the correct/official image?

## Answer: No

`ronaldraygun/botburrow-agents` is **not** the correct/official image. It has been deprecated.

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Evidence

1. **CI/CD pipeline** (`.github/workflows/ci-cd.yml`, `release.yml`): Builds and pushes to `ghcr.io/ardenone/botburrow-agents`
2. **All K8s manifests** (`k8s/apexalgo-iad/`): Reference `ghcr.io/ardenone/botburrow-agents:latest`
3. **Zero references** to `ronaldraygun` in any source code (`.yaml`, `.py`, `.toml` files)
4. **Docker Hub repo** `ronaldraygun/botburrow-agents` is deleted/private — returns "object not found"
5. **Migration completed** on 2026-03-17 (commit `2a2a589`) from Docker Hub to GHCR

## Prior Investigation

This confirms findings from:
- `bd-xwf3-definitive-answer.md`
- `bd-fi7h-definitive-answer.md`
- `bd-ur5o-definitive-answer.md`
- `bd-jj01-definitive-answer.md`
