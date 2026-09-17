# Docker Hub `ardenone` User Login Setup (Historical)

> This repository is retired. These notes preserve the last validated setup
> procedure for archival purposes; they are not an active deployment path.

## Purpose

Configure Docker Hub authentication for the `ardenone` user to enable CI/CD push capability to `ardenone/*` repositories.

## Current State

- **Existing login**: `ronaldraygun` user (configured)
- **Required login**: `ardenone` user (for CI/CD push to `ardenone/*` repos)
- **Primary registry**: GHCR (ghcr.io) - used for botburrow-agents images
- **Secondary registry**: Docker Hub (hub.docker.com) - optional but configured for flexibility

## Secure Login Procedure

### Step 1: Obtain Docker Hub Credentials

Docker Hub credentials for the `ardenone` account should be obtained from:
- OpenBao secret store (if already stored)
- Docker Hub account settings (if creating new access token)

**Generate Docker Hub Access Token:**
1. Log in to https://hub.docker.com
2. Go to Account Settings → Security → New Access Token
3. Create token with **Read & Write** permissions
4. **Copy the token immediately** (it won't be shown again)

### Step 2: Store Credentials in OpenBao

Store the credentials securely in OpenBao (never in plaintext):

```bash
# Store the Docker Hub access token
# Read without echo, then stream directly to the authoritative OpenBao instance
read -r -s DOCKER_TOKEN
printf '%s' "$DOCKER_TOKEN" | bao-as openbao-v2 kv put \
  -cas=0 \
  secret/ardenone-cluster/docker-hub-ardenone \
  username=ardenone \
  token=-
unset DOCKER_TOKEN
```

**Verify storage:**
```bash
bao-as openbao-v2 kv metadata get secret/ardenone-cluster/docker-hub-ardenone
```

### Step 3: Perform Docker Login

Retrieve the token and perform the login:

```bash
# Stream the token directly to Docker; do not retain it in a shell variable
bao-as openbao-v2 kv get -field=token \
  secret/ardenone-cluster/docker-hub-ardenone | \
  docker login docker.io -u ardenone --password-stdin

# Verify login
docker info | grep -i username
```

**Expected output:**
```
Username: ardenone
```

### Step 4: Verify Configuration

Check that the login was successful:

```bash
docker info --format '{{json .RegistryConfig.IndexConfigs}}' | jq 'has("docker.io")'
```

Should show an auth entry for `ardenone` user.

## CI/CD Integration

### Argo Workflows (iad-ci)

This repository's CI/CD path is retired. If an archived workflow is ever
recreated, provide registry credentials through a Kubernetes Secret populated
by the owning OpenBao/ExternalSecret flow. Do not read OpenBao values into
workflow variables or logs.

Use pinned versions for any manual archival image push:

```yaml
- name: Push to Docker Hub
  run: |
    docker push "ardenone/my-image:${IMAGE_VERSION:?set a pinned version}"
```

## Security Guidelines

**CRITICAL - Follow these rules:**

1. **Never print tokens to stdout** - use variable assignment and pipes
2. **Never pass tokens as command-line arguments** - use `--password-stdin`
3. **Never commit tokens to git** - use OpenBao or GitHub Secrets
4. **Use access tokens, not passwords** - tokens can be rotated
5. **Grant minimal permissions** - Read & Write only for needed repos

## Troubleshooting

### Login fails with "unauthorized"

- Verify token hasn't expired (Docker Hub tokens can expire)
- Regenerate token from Docker Hub account settings
- Update OpenBao secret with new token

### CI/CD can't access credentials

- Verify OpenBao secret path is correct
- Check service account has OpenBao read permissions
- Ensure `-cas` check-and-set is used when updating

### Multiple logins conflict

Docker config can store multiple logins:
```json
{
  "auths": {
    "https://index.docker.io/v1/": {
      "auth": "<base64-ardenone>"
    },
    "ghcr.io": {
      "auth": "<base64-ghcr>"
    }
  }
}
```

## Related Documentation

- `docs/bd-lsp0-dockerhub-secrets-not-needed.md` - GHCR migration history
- `docs/bd-7y9w-dockerhub-ardenone-missing.md` - Repository status
- CLAUDE.md - OpenBao credential storage guidelines

## Status

- **Task**: Log in to Docker Hub as `ardenone` user
- **Bead ID**: botburro-9d8b693b
- **Parent**: Configure Docker Hub credentials for CI/CD push

---

**Last Updated:** 2026-08-29
