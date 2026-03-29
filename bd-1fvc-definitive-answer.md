---
bead: bd-1fvc
task: GitHub secrets DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD not configured
status: closed - human action required for credentials
---

# Definitive Answer: bd-1fvc

## Task
GitHub secrets DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD not configured

## Finding
**No code changes are possible or needed. Credentials must be provided by a human.**

## Current State

The CI/CD workflows already handle missing Docker Hub credentials gracefully:

1. **DOCKERHUB_USERNAME is not a secret** — the username `ardenone` is hardcoded in both
   workflow files. No `DOCKERHUB_USERNAME` secret is referenced anywhere in the workflows.

2. **DOCKERHUB_PASSWORD is optional** — both workflows check whether the secret is set
   before attempting Docker Hub push, and skip gracefully if it is absent:
   ```yaml
   if [[ -z "${DOCKERHUB_PASSWORD}" ]]; then
     echo "available=false" >> $GITHUB_OUTPUT
     echo "::notice::DOCKERHUB_PASSWORD not configured - skipping Docker Hub push"
     exit 0
   fi
   ```

3. **No secrets currently configured** — `gh secret list` returns empty.
   GHCR push works via the automatic `GITHUB_TOKEN` and does not require any secrets.

4. **Parent bead bd-31j is already CLOSED** — the Docker Hub push infrastructure has
   been implemented. The only remaining gap is the credential secret itself.

## What Would Enable Docker Hub Push

A human with access to the `ardenone` Docker Hub account must:
1. Create a Personal Access Token (PAT) with **Read & Write** permissions at hub.docker.com
2. Set the GitHub secret:
   ```bash
   gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents
   ```

The `DOCKERHUB_USERNAME` secret does not need to be set (username is hardcoded).

## Conclusion

No code changes are needed or possible. The workflow is correctly written to handle the
missing secret case. Docker Hub push is currently skipped (not broken). To enable Docker
Hub push, a human must provide the Docker Hub PAT and set the `DOCKERHUB_PASSWORD` secret.
