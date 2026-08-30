# Docker Hub `ardenone` Login - Implementation Status

## Task Summary
**Bead**: botburro-9d8b693b  
**Task**: Log in to Docker Hub as `ardenone` user  
**Parent**: Configure Docker Hub credentials for CI/CD push

## Current State (2026-08-29)

### ✅ What's Already Configured

**CI/CD Workflow** (`.github/workflows/ci-cd.yml`):
- Username hardcoded as `ardenone` (lines 161, 94)
- Login action configured: `docker/login-action@v3`
- Repository creation logic (lines 103-119)
- Push scope verification with retry logic (lines 120-155)
- Graceful handling if credentials missing (lines 88-92)

**Docker Images**:
- Registry configured: `docker.io/ardenone/botburrow-agents`
- Tags: `<git-sha>` and `:latest`
- Primary registry: GHCR (always pushed)
- Secondary registry: Docker Hub (pushed if credentials available)

### ❌ What's Missing

**GitHub Secret**:
- Secret name: `DOCKERHUB_PASSWORD`
- Status: **NOT SET**
- Impact: CI/CD skips Docker Hub push with notice
- Expected credential: Docker Hub Access Token (PAT) with Read & Write permissions

**OpenBao Storage** (optional for local use):
- Path: `secret/ardenone-cluster/docker-hub-ardenone`
- Status: **NOT CREATED**
- Purpose: Local Docker login (not required for CI/CD)

## Implementation Status

### CI/CD Login Configuration: ✅ COMPLETE
The GitHub Actions workflow is fully configured and will automatically log in to Docker Hub as `ardenone` once the `DOCKERHUB_PASSWORD` secret is set.

**Workflow behavior**:
```yaml
# Lines 157-162 in .github/workflows/ci-cd.yml
- name: Log in to Docker Hub
  if: steps.dockerhub.outputs.available == 'true'
  uses: docker/login-action@v3
  with:
    username: ardenone
    password: ${{ secrets.DOCKERHUB_PASSWORD }}
```

**Verification logic** (lines 83-156):
1. Checks if `DOCKERHUB_PASSWORD` secret exists
2. Attempts login to Docker Hub API
3. Creates repository if it doesn't exist
4. Verifies push scope (Read & Write permissions)
5. Only proceeds if all checks pass

### Local Docker Login: ❌ NOT IMPLEMENTED
Local Docker is currently logged in as `ronaldraygun`. Changing to `ardenone` is optional and not required for CI/CD.

## Required Action

### To Enable CI/CD Docker Hub Push

**Step 1: Generate Docker Hub Access Token**
```bash
# 1. Login to https://hub.docker.com as ardenone
# 2. Navigate to: Account Settings → Security → New Access Token
# 3. Create token with permissions: Read & Write
# 4. Copy the token immediately (only shown once)
```

**Step 2: Set GitHub Secret**
```bash
gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents
# Paste the token when prompted
```

**Step 3: Verify (on next push to main)**
```bash
# After next CI run, check Docker Hub:
curl -s https://hub.docker.com/v2/repositories/ardenone/botburrow-agents/tags/ | \
  jq -r '.results[].name' | head -5
```

Expected output:
```
latest
a1b2c3d
<other tags>
```

### To Enable Local Docker Login (Optional)

**Step 1: Store in OpenBao**
```bash
export BAO_ADDR="https://openbao-v2-ardenone-cluster.ardenone.com"

# Use stdin to avoid exposing token
echo "YOUR_DOCKER_HUB_TOKEN" | bao kv put \
  -cas=0 \
  secret/ardenone-cluster/docker-hub-ardenone \
  username=ardenone \
  token=-
```

**Step 2: Login locally**
```bash
# Retrieve token and login
DOCKER_TOKEN=$(bao kv get -field=token secret/ardenone-cluster/docker-hub-ardenone)
echo "$DOCKER_TOKEN" | docker login docker.io -u ardenone --password-stdin

# Verify
docker info | grep -i username  # Should show: ardenone
```

## Workflow After Setup

On each push to `main`:
1. Tests run (pytest, ruff, mypy)
2. Docker image built
3. **Pushed to GHCR** (always, using `GITHUB_TOKEN`)
4. **Pushed to Docker Hub** (if `DOCKERHUB_PASSWORD` set)
   - Logs in as `ardenone`
   - Pushes `ardenone/botburrow-agents:<sha>`
   - Pushes `ardenone/botburrow-agents:latest`

## Documentation References

- `docs/docker-hub-ardenone-setup.md` - Detailed procedures
- `docs/docker-hub-ardenone-status.md` - Current state analysis
- `docs/DOCKERHUB_SETUP.md` - CI/CD integration guide
- `.github/workflows/ci-cd.yml` - Lines 83-162 (Docker Hub logic)

## Security Notes

- Credentials stored by reference only (GitHub Secret for CI/CD, OpenBao for local)
- Token values never visible in transcripts, logs, or documentation
- Follows CLAUDE.md guidelines for credential management
- Uses `--password-stdin` pattern to avoid argv exposure

## Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| CI/CD workflow | ✅ Ready | Awaiting `DOCKERHUB_PASSWORD` secret |
| Docker Hub repo | ✅ Ready | Auto-created by workflow |
| Local login | ❌ Optional | Currently `ronaldraygun` |
| Documentation | ✅ Complete | All procedures documented |

**Next Action**: Set `DOCKERHUB_PASSWORD` GitHub secret to activate Docker Hub push in CI/CD.

---

**Last Updated**: 2026-08-29  
**Bead Status**: Configuration complete, awaiting credential
