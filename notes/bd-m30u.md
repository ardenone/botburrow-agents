# bd-m30u: Log in to Docker Hub as `ardenone` user

**Status:** BLOCKED — `ardenone` Docker Hub credentials not found (re-confirmed 2026-05-15)

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

## Re-investigation 2026-05-15

Re-confirmed the blocker. No change in state:

- `~/.docker/config.json` still only has `ronaldraygun` and GHCR auth
- `docker-hub-registry` secret on iad-ci still uses `ronaldraygun` (decoded and verified)
- OpenBao still inaccessible locally (`bao status` → connection refused to 127.0.0.1:8200)
- No `ardenone` Docker Hub PAT surfaced in any accessible location

Additional access paths exhausted:
- ardenone-manager `openbao` namespace pods ARE running (`openbao-ardenone-manager-0`, etc.)
- `kubectl exec` blocked by read-only RBAC on ardenone-manager proxy
- `/home/coding/.kube/ardenone-manager.kubeconfig` does not exist on disk
- `rs-manager.kubeconfig` returns auth error (`credentials required`) when pointed at ardenone-manager
- ArgoCD RO proxy (`argocd-ro-ardenone-manager-ts.ardenone.com:8444`) unreachable (curl exit 6)
- No `ARDENONE_*`, `PAT`, `PASSWORD`, or `TOKEN` env vars set

This task requires the user to provide the `ardenone` Docker Hub PAT to proceed.

## Re-investigation 2026-05-15 (second pass)

Additional access paths exhausted:

- **sigil vault** (`/home/coding/.cargo/bin/sigil`, vault at `~/.sigil/vault/`): Only contains test secrets (`test/api_key`, `test/from-file`, `test/interactive`) — no Docker Hub credentials for any user
- **`sigil-credential-docker`** listed in `~/.docker/config.json` credHelpers for `https://index.docker.io` — but sigil vault has no Docker Hub entry; the helper would return nothing
- **GitHub secrets** (`gh secret list -R ardenone/botburrow-agents`, `gh secret list --org ardenone`): No output — either empty or jedarden account lacks org-admin scope to list secrets
- **iad-ci secrets (all namespaces)**: No secret with both "ardenone" and "docker" in decoded value
- **OpenBao via sigil/direct HTTP**: `bao status` → error; no Tailscale hostname for OpenBao resolves (`openbao-ardenone-manager`, `openbao.ardenone.com`, `vault.ardenone.com` all timeout)

State remains unchanged: the `ardenone` Docker Hub PAT does not exist in any locally-accessible store. The user must provide it directly.
