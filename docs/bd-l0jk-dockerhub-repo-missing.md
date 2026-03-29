---
bead: bd-l0jk
task: Docker Hub repository `ardenone/botburrow-agents` doesn't exist
status: closed - blocked by human credential requirement
---

# Docker Hub Repository Missing: bd-l0jk

## Status

**Repository confirmed missing** — `curl https://hub.docker.com/v2/repositories/ardenone/botburrow-agents/`
returns `{"message":"object not found","errinfo":{}}`.

## Why It Can't Be Created Automatically

Creating a Docker Hub repository under the `ardenone` namespace requires authentication
with that account's credentials. No automation can create it without the `DOCKERHUB_PASSWORD`
GitHub secret being set.

## What Already Exists

The CI/CD workflow (`.github/workflows/ci-cd.yml`) already contains repository auto-creation
logic (added in commit `4ff08a5`). When `DOCKERHUB_PASSWORD` is set, the workflow:

1. Authenticates via `POST https://hub.docker.com/v2/users/login/`
2. Creates the repository via `POST https://hub.docker.com/v2/repositories/` (handles 201/400/409)
3. Verifies push scope with retries to handle propagation delay
4. Proceeds with Docker Hub push if all checks pass

The repository will be created **automatically on the next CI run** after `DOCKERHUB_PASSWORD`
is configured.

## Human Action Required

As documented in `docs/bd-iffa-dockerhub-push-access.md`:

1. Log in to hub.docker.com as `ardenone`
2. Create a Personal Access Token with **Read & Write** permissions
3. Set the GitHub secret:
   ```bash
   gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents
   ```
4. Trigger a CI run — the workflow will create the repository and push images automatically

## No Code Changes Needed

The auto-creation logic is already in place. This bead's resolution depends entirely on
the human credential action tracked in bd-iffa.
