# bd-xwf3: Is ronaldraygun/botburrow-agents the correct/official image?

## Answer: No

`ronaldraygun/botburrow-agents` is **not** the correct/official image. It has been deprecated.

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Evidence

- **CI/CD** (`.github/workflows/ci-cd.yml`, `release.yml`): Builds and pushes to `ghcr.io/ardenone/botburrow-agents`
- **All K8s manifests** (`k8s/apexalgo-iad/`): Reference `ghcr.io/ardenone/botburrow-agents:latest`
- **Zero references** to `ronaldraygun` in any source code (`.yaml`, `.py`, `.toml` files)
- The Docker Hub repo (`ronaldraygun/botburrow-agents`) is deleted/private
- Migration to GHCR happened on 2026-03-17 (commit `2a2a589`)
