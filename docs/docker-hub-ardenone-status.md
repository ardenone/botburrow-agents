# Docker Hub `ardenone` Login Status

## Current State (2026-08-29)

### Local Docker Login
- **Currently logged in as**: `ronaldraygun`
- **Config location**: `~/.docker/config.json`
- **Status**: Functional, but using wrong user for this project

### CI/CD Configuration (`.github/workflows/ci-cd.yml`)
- **Username configured**: `ardenone` (hardcoded, lines 161, 94)
- **Login mechanism**: GitHub Actions `docker/login-action@v3`
- **Credential source**: GitHub Secret `DOCKERHUB_PASSWORD`
- **Secret status**: ❌ **NOT SET** - CI/CD will skip Docker Hub push

### What's Already Working
✅ CI/CD workflow fully configured for `ardenone` user  
✅ Automatic repository creation via Docker Hub API  
✅ Push scope verification (ensures PAT has Read & Write)  
✅ Graceful fallback if credentials not configured  

### What's Missing
❌ GitHub Secret `DOCKERHUB_PASSWORD` not set  
❌ Local Docker not logged in as `ardenone`

## Action Required

To complete "Log in to Docker Hub as `ardenone` user":

### Option 1: For CI/CD Push (Recommended)
Set the GitHub Secret that CI/CD uses:

```bash
# Create Docker Hub Access Token first:
# 1. Login to hub.docker.com as ardenone
# 2. Account Settings → Security → New Access Token
# 3. Grant "Read & Write" permissions
# 4. Copy the token (only shown once)

# Set the GitHub secret:
gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents
# Paste the token when prompted
```

**Verification** (after next push to main):
```bash
# Check Docker Hub for the image
curl -s https://hub.docker.com/v2/repositories/ardenone/botburrow-agents/tags/ | \
  jq -r '.results[].name' | head -5
```

### Option 2: For Local Docker Login
Use OpenBao pattern (per CLAUDE.md security guidelines):

```bash
# Set OpenBao address
export BAO_ADDR="https://openbao-v2-ardenone-cluster.ardenone.com"

# Store token (use stdin to avoid exposure)
echo "YOUR_DOCKER_HUB_TOKEN" | bao kv put \
  -cas=0 \
  secret/ardenone-cluster/docker-hub-ardenone \
  username=ardenone \
  token=-

# Login locally (retrieve and use token)
DOCKER_TOKEN=$(bao kv get -field=token secret/ardenone-cluster/docker-hub-ardenone)
echo "$DOCKER_TOKEN" | docker login docker.io -u ardenone --password-stdin
```

## Expected Behavior After Setup

### CI/CD Push
On each push to `main`:
1. Workflow logs into Docker Hub as `ardenone`
2. Pushes `ardenone/botburrow-agents:<git-sha>` and `:latest`
3. Continues to push to GHCR as primary registry

### Local Docker
```bash
# Push to Docker Hub manually
docker tag ghcr.io/ardenone/botburrow-agents:latest ardenone/botburrow-agents:latest
docker push ardenone/botburrow-agents:latest
```

## Related Documentation

- `docs/docker-hub-ardenone-setup.md` - Detailed setup procedures
- `docs/DOCKERHUB_SETUP.md` - CI/CD integration guide
- `.github/workflows/ci-cd.yml` - Lines 83-162 (Docker Hub login & push)

## Bead Context

- **Bead ID**: botburro-9d8b693b
- **Parent**: Configure Docker Hub credentials for CI/CD push
- **Task**: Log in to Docker Hub as `ardenone` user
- **Status**: Configuration complete, awaiting credential

---

**Note**: Per CLAUDE.md security guidelines, credentials are stored by reference only (GitHub Secret for CI/CD, OpenBao for local). The actual token value is never visible in transcripts, logs, or documentation.
