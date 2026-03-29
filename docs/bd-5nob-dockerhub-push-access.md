---
bead: bd-5nob
task: Credentials don't have push access to repository
status: handled — human action required to enable Docker Hub push
---

# Docker Hub Push Access: bd-5nob

## Problem

The `DOCKERHUB_PASSWORD` GitHub secret is either not set or is a Docker Hub
Personal Access Token (PAT) with **read-only** permissions. The CI/CD workflow
detects this by decoding the JWT returned from Docker Hub's auth service and
checking whether `push` scope was granted.

## Prior Work

This is the same issue as `bd-iffa` (also a child of `bd-31j`). The CI/CD fix
has already been implemented — see `docs/bd-iffa-dockerhub-push-access.md` and
commit `3e2bcd0` (retry push scope check) / `cdf65b2` (JWT scope verification).

## Current CI Behaviour

The workflow (`ci-cd.yml`, step `Check Docker Hub credentials`) gracefully
degrades when push scope is not granted:

- Sets `steps.dockerhub.outputs.available=false`
- Emits `::error::Docker Hub credentials do not have push access to ardenone/botburrow-agents - use a PAT with Read & Write permissions`
- Skips "Log in to Docker Hub" and "Push to Docker Hub" steps
- GHCR push (`ghcr.io/ardenone/botburrow-agents`) still succeeds — no pipeline failure

## What Needs to Happen (Human Action Required)

A human with access to the `ardenone` Docker Hub account must:

1. **Create a Docker Hub PAT with Read & Write access**
   - Log in at https://hub.docker.com
   - Account Settings → Security → Personal Access Tokens → Generate New Token
   - Set **Access permissions** to **Read & Write**
   - Copy the generated token

2. **Set the GitHub secret**
   ```bash
   gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents
   # Paste the PAT when prompted
   ```

3. **Trigger a new CI run** to confirm Docker Hub push succeeds

## Why This Can't Be Automated

Docker Hub PAT creation requires interactive login to hub.docker.com with the
account owner's credentials. No automation can issue a new PAT on behalf of the
`ardenone` account without those credentials.

## Verification

After the secret is set, a passing CI run will log:

```
Docker Hub repository ardenone/botburrow-agents already exists
...
available=true
```

And the "Push to Docker Hub" step will publish:
- `ardenone/botburrow-agents:<sha>`
- `ardenone/botburrow-agents:latest`
