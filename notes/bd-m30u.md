# bd-m30u: Log in to Docker Hub as `ardenone` user

**Status:** BLOCKED — `ardenone` Docker Hub credentials not found

## Task

Log in to Docker Hub as `ardenone` user, as part of parent goal: "Configure Docker Hub credentials for CI/CD push".

## Investigation

### Current Docker Hub state

- Local `~/.docker/config.json` is authenticated as `ronaldraygun` (PAT stored in OpenBao at `rs-manager/iad-ci/docker/build`)
- The `docker-hub-registry` Kubernetes secret in `argo-workflows` on iad-ci uses `ronaldraygun` credentials
- `ronaldraygun` credentials are sourced via ExternalSecret from OpenBao at path `rs-manager/iad-ci/docker/build` property `PAT`

### Why `ardenone` credentials are needed

Testing confirmed that `ronaldraygun` cannot access `ardenone/botburrow-agents` on Docker Hub (returns UNAUTHORIZED). A separate `ardenone` Docker Hub PAT is required.

### Where `ardenone` credentials are NOT stored

- `~/.docker/config.json` — only `ronaldraygun` and `jedarden` (GHCR)
- Kubernetes secrets across iad-ci, iad-kalshi, apexalgo-iad — no ardenone Docker Hub PAT found
- OpenBao (ardenone-manager) — accessible only via kubectl exec; no local token available to read KV
- `sigil-credential-docker` — configured in docker credHelpers but binary not in PATH
- Environment variables — none found

### What is needed to unblock

One of:
1. The `ardenone` Docker Hub PAT stored in OpenBao at a new path (e.g., `rs-manager/iad-ci/docker/ardenone-build`), then update the ExternalSecret template
2. The `ardenone` Docker Hub PAT provided directly to run `docker login -u ardenone --password-stdin`

### Context

The botburrow-agents CI/CD (`botburrow-agents-build` WorkflowTemplate on iad-ci) currently pushes only to GHCR (`ghcr.io/ardenone/botburrow-agents`). The `docker-hub-registry` secret exists but is not wired into the botburrow-agents workflow. This task is a prerequisite for adding Docker Hub as a secondary push target.
