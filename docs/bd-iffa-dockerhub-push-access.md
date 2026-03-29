---
bead: bd-iffa
task: Credentials don't have push access to repository
status: human action required
---

# Docker Hub Push Access: bd-iffa

## Problem

The `DOCKERHUB_PASSWORD` GitHub secret is either not set, or it is set to a Docker Hub
Personal Access Token (PAT) that has **read-only** permissions. The CI/CD workflow
verifies push scope via JWT inspection after obtaining a registry token:

```
::error::Docker Hub credentials do not have push access to ardenone/botburrow-agents
         - use a PAT with Read & Write permissions
```

## Current CI Behaviour

The workflows gracefully degrade — Docker Hub push is skipped but GHCR push
(`ghcr.io/ardenone/botburrow-agents`) continues to succeed. No pipeline failure occurs.

## What Needs to Happen (Human Action Required)

A human with access to the `ardenone` Docker Hub account must:

1. **Create a Docker Hub PAT with Read & Write access**
   - Log in at https://hub.docker.com
   - Go to Account Settings → Security → Personal Access Tokens
   - Click "Generate New Token"
   - Set **Access permissions** to **Read & Write** (not Read-only)
   - Copy the generated token

2. **Set the GitHub secret**
   ```bash
   gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents
   # Paste the PAT when prompted
   ```

3. **Trigger a new CI run** to verify Docker Hub push succeeds

## Why This Can't Be Automated

Docker Hub PAT creation requires interactive login to hub.docker.com. No automation can
create a new PAT on behalf of the `ardenone` account without its credentials.

## Verification

After setting the secret, a successful CI run will show:

```
Docker Hub repository ardenone/botburrow-agents already exists
...
available=true
```

And the "Push to Docker Hub" step will complete, publishing:
- `ardenone/botburrow-agents:<sha>`
- `ardenone/botburrow-agents:latest`
