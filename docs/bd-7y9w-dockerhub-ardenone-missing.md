---
bead: bd-7y9w
task: Docker Hub repository `ardenone/botburrow-agents` doesn't exist
status: closed
---

# Docker Hub Repository `ardenone/botburrow-agents` Missing — bd-7y9w

## Finding

The Docker Hub repository `ardenone/botburrow-agents` does not exist and was never created.

```bash
$ curl -s https://hub.docker.com/v2/repositories/ardenone/botburrow-agents/
{"message":"object not found","errinfo":{}}
```

## Why It Doesn't Matter

The project migrated from Docker Hub to GitHub Container Registry (GHCR) on 2026-03-17
(commit `2a2a589`). The Docker Hub repository was never needed.

## Official Image Location

```
ghcr.io/ardenone/botburrow-agents:latest
```

- **CI/CD** (`.github/workflows/ci-cd.yml`, `release.yml`): Builds and pushes to GHCR
- **All K8s manifests** (`k8s/apexalgo-iad/`): Reference `ghcr.io/ardenone/botburrow-agents:latest`
- Creating `ardenone/botburrow-agents` on Docker Hub is **not required**

## No Action Needed

The missing Docker Hub repository is not a problem. The CI/CD pipeline and Kubernetes
manifests use GHCR exclusively. See `docs/bd-wtp9-ardenone-image-answer.md` for full
evidence of the GHCR migration.
