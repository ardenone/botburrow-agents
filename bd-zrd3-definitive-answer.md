---
bead: bd-zrd3
task: GitHub secrets DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD not configured
status: closed - no action required
---

# Definitive Answer: bd-zrd3

## Task
GitHub secrets DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD not configured

## Finding
**No code changes are possible without human-provided credentials.**

## Current State

The CI/CD workflows (`.github/workflows/ci-cd.yml` and `.github/workflows/release.yml`) already handle missing Docker Hub credentials gracefully:

1. **DOCKERHUB_USERNAME is not a secret** — the username `ardenone` is hardcoded directly in both workflow files. No `DOCKERHUB_USERNAME` secret is referenced anywhere.

2. **DOCKERHUB_PASSWORD is optional** — both workflows check whether the secret is set before attempting Docker Hub push:
   ```yaml
   - name: Check Docker Hub credentials
     id: dockerhub
     env:
       DOCKERHUB_PASSWORD: ${{ secrets.DOCKERHUB_PASSWORD }}
     run: |
       if [[ -z "${DOCKERHUB_PASSWORD}" ]]; then
         echo "available=false" >> $GITHUB_OUTPUT
         echo "::notice::DOCKERHUB_PASSWORD not configured - skipping Docker Hub push"
         exit 0
       fi
   ```

3. **No secrets currently configured** — `gh secret list` returns empty. GHCR push works via the automatic `GITHUB_TOKEN`.

## What Would Enable Docker Hub Push

A human with access to the `ardenone` Docker Hub account needs to:
1. Create a Personal Access Token (PAT) with **Read & Write** permissions at hub.docker.com
2. Set the GitHub secret: `gh secret set DOCKERHUB_PASSWORD`

The `DOCKERHUB_USERNAME` secret does not need to be set.

## Conclusion

No code changes are needed. The workflow is correctly written to handle the missing secret case. Docker Hub push is currently skipped (not broken). To enable Docker Hub push, a human must provide the Docker Hub PAT.
