---
bead: bd-i2vz
task: Create repository `ardenone/botburrow-agents`
status: closed - requires human credentials
---

# Create Docker Hub Repository: bd-i2vz

## Status

Repository `ardenone/botburrow-agents` does not exist on Docker Hub
(`curl https://hub.docker.com/v2/repositories/ardenone/botburrow-agents/` returns `object not found`).

## Why It Can't Be Created Automatically

Creating a Docker Hub repository under the `ardenone` namespace requires authenticating
as that account. No credentials are available in this environment.

## What Already Exists

The CI/CD workflow already has repository auto-creation logic (added in commit `4ff08a5`).
When `DOCKERHUB_PASSWORD` is set as a GitHub secret, the CI run will:

1. Authenticate via `POST https://hub.docker.com/v2/users/login/`
2. Create the repository via `POST https://hub.docker.com/v2/repositories/` (handles 201/400/409)
3. Verify push scope with retries to handle propagation delay
4. Push the image to Docker Hub

The repository will be **created automatically on the first CI run** after `DOCKERHUB_PASSWORD`
is configured.

## Human Action Required

1. Log in to hub.docker.com as `ardenone`
2. Create a Personal Access Token with **Read & Write** permissions
3. Set the GitHub secret:
   ```bash
   gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents
   ```
4. Trigger a CI run — the workflow will create the repository and push images automatically

No code changes are needed. The auto-creation logic is already in place.
