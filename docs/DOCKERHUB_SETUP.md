# Docker Hub Setup for CI/CD

## Overview

The CI/CD pipeline is configured to push Docker images to both GitHub Container Registry (GHCR) and Docker Hub. The Docker Hub push is optional and only executes when credentials are configured.

## What's Already Configured

The `.github/workflows/ci-cd.yml` workflow includes:
- Docker Hub login as `ardenone` user (hardcoded username)
- Automatic repository creation if it doesn't exist
- Push scope verification to ensure credentials have proper permissions
- Graceful handling if credentials are not configured

## Required Configuration

To enable Docker Hub push, set the following GitHub secret:

### GitHub Secret: `DOCKERHUB_PASSWORD`

**Value:** Docker Hub Personal Access Token (PAT) with **Read & Write** permissions

**How to create:**
1. Log in to Docker Hub as `ardenone`
2. Go to Account Settings → Security → New Access Token
3. Create a token with "Read & Write" permissions
4. Copy the generated token

**How to set the secret:**

Using GitHub CLI:
```bash
gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents
```

Or via GitHub UI:
1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `DOCKERHUB_PASSWORD`
4. Value: paste the Docker Hub PAT
5. Click "Add secret"

## What Happens After Configuration

Once `DOCKERHUB_PASSWORD` is set, the CI/CD workflow will:
1. Log in to Docker Hub as `ardenone` on every push to `main`
2. Verify the repository exists (create it if needed)
3. Confirm push permissions are granted
4. Push built images to both GHCR and Docker Hub

## Images Pushed

- `ardenone/botburrow-agents:<short-sha>` - Versioned image
- `ardenone/botburrow-agents:latest` - Latest image

## Verification

After the next CI run, verify images are pushed:

```bash
# Check latest images on Docker Hub
curl -s https://hub.docker.com/v2/repositories/ardenone/botburrow-agents/tags/ | jq -r '.results[].name'

# Pull and test the image
docker pull ardenone/botburrow-agents:latest
docker run --rm ardenone/botburrow-agents:latest --help
```

## If Credentials Are Not Set

The workflow will **continue normally** with a notice:
```
DOCKERHUB_PASSWORD not configured - skipping Docker Hub push
```

Images will still be pushed to GHCR successfully.

## Troubleshooting

### "Docker Hub login failed for ardenone"
- Verify `DOCKERHUB_PASSWORD` is set correctly
- Ensure the PAT has Read & Write permissions
- Check that the `ardenone` Docker Hub account is active

### "Docker Hub credentials do not have push access"
- The PAT may be read-only
- Regenerate the PAT with "Read & Write" permissions

### "Failed to ensure Docker Hub repository exists"
- Check API rate limits for Docker Hub
- Verify the `ardenone` account has permission to create repositories

## Current Status

- ✅ CI/CD workflow configured for Docker Hub push
- ✅ Username hardcoded as `ardenone`
- ⏳ Awaiting `DOCKERHUB_PASSWORD` secret to be set by repository maintainer

Once the secret is configured, Docker Hub push will activate automatically on the next push to `main`.
