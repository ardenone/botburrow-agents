# Forgejo Credentials Setup Guide - bd-2wsm

**Date:** 2026-02-14
**Task:** Add Forgejo credentials to botburrow-agents init containers

## Overview

Botburrow-agents uses git-sync sidecars to clone the `agent-definitions` repository. Forgejo requires authentication for all operations including read access. This guide walks through setting up the credentials.

## Current State

✅ **Completed:**
- ConfigMap `agent-definitions-repos` updated to point to Forgejo
- Deployment manifests updated to use Forgejo credentials (FORGEJO_USER, FORGEJO_TOKEN)
- Forgejo deployment is running (forgejo-785c7dff4b-blbdp)

❌ **Pending:**
- Forgejo credentials must be added to `botburrow-agents-secrets` Secret
- `botburrow/agent-definitions` repository must exist in Forgejo
- ConfigMap must be deployed to apexalgo-iad cluster

## Prerequisites

### 1. Forgejo Repository Exists

Before adding credentials, verify the repository exists:

```bash
# Option A: Check via Forgejo UI
# Navigate to: https://botburrow-git.ardenone.com
# Check if botburrow/agent-definitions exists

# Option B: Check via API (if accessible)
curl -s "http://forgejo.forgejo.svc.cluster.local:3000/api/v1/repos/botburrow/agent-definitions"
```

**If repository does NOT exist:**

1. Log into Forgejo UI: https://botburrow-git.ardenone.com
2. Create `botburrow` organization (if it doesn't exist)
3. Create `agent-definitions` repository under `botburrow`
4. Configure as mirror from GitHub: `https://github.com/jedarden/agent-definitions`
   - Set sync interval: 8 hours (recommended)
   - This keeps Forgejo in sync with GitHub

### 2. Forgejo Admin Credentials Available

You need access to Forgejo admin credentials to generate tokens. These are stored in:
- SealedSecret: `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/forgejo/forgejo-sealedsecret.yml`
- Secret name: `forgejo-secrets`
- Keys: `ADMIN_USER`, `ADMIN_PASSWORD`

## Setup Steps

### Step 1: Create Forgejo Service Account Token

**Option A: Via Forgejo UI (Recommended)**

1. Log into Forgejo: https://botburrow-git.ardenone.com
2. Click on your avatar → Settings → Applications
3. Click "Generate New Token"
4. Configure token:
   - **Token Name:** `botburrow-agents-git-sync`
   - **Scopes:** `read:user`, `read:repository`, `write:repository`
5. Copy the generated token

**Option B: Via Forgejo CLI (if available)**

```bash
# From a pod with Forgejo CLI access
forgejo admin user generate-access-token \
  --username YOUR_ADMIN_USER \
  --token-name "botburrow-agents-git-sync" \
  --scopes "read:user,read:repository,write:repository"
```

### Step 2: Update SealedSecret Template

Edit the Secret template to add Forgejo credentials:

```bash
cd /home/coder/botburrow-agents/k8s/apexalgo-iad
```

Edit `botburrow-agents-sealedsecrets.yml.template`, find the Forgejo section:

```yaml
  # =============================================================================
  # GIT ACCESS - FORGEJO (Internal Git)
  # =============================================================================
  # Create token at: https://forgejo.ardenone.com/user/settings/applications
  # Required scopes: read:user, read:repository, write:repository
  FORGEJO_USER: "botburrow-agents"
  FORGEJO_TOKEN: "REPLACE_WITH_FORGEJO_PAT"
```

Replace with actual values:
- `FORGEJO_USER`: The username owning the token (e.g., your Forgejo admin username)
- `FORGEJO_TOKEN`: The token generated in Step 1

### Step 3: Generate SealedSecret

```bash
# From ardenone-cluster workspace (has kubeseal and cluster access)
cd /home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents

# Generate SealedSecret
kubeseal --format yaml < botburrow-agents-sealedsecrets.yml.template > botburrow-agents-sealedsecrets.yml

# Verify
kubectl apply --dry-run=server -f botburrow-agents-sealedsecrets.yml
```

### Step 4: Deploy to Cluster

```bash
# Apply SealedSecret
kubectl apply -f /home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/botburrow-agents-sealedsecrets.yml

# Apply ConfigMap (updated with Forgejo URL)
kubectl apply -f /home/coder/botburrow-agents/k8s/apexalgo-iad/configmap.yaml
```

### Step 5: Verify Deployment

```bash
# Check that Secret was created
kubectl get secret botburrow-agents-secrets -n botburrow-agents

# Check ConfigMap
kubectl get configmap agent-definitions-repos -n botburrow-agents -o yaml

# Restart pods to pick up new configuration
kubectl delete pod -n botburrow-agents -l app.kubernetes.io/name=coordinator
kubectl delete pod -n botburrow-agents -l app.kubernetes.io/name=runner

# Watch pods starting
kubectl get pods -n botburrow-agents -w
```

Expected result:
- Pods move from `Init:Error`/`CrashLoopBackOff` to `Running`
- git-sync containers successfully clone repository

## Troubleshooting

### Pods still failing with "Authentication required"

1. Verify Secret has credentials:
   ```bash
   kubectl get secret botburrow-agents-secrets -n botburrow-agents -o jsonpath='{.data.FORGEJO_USER}' | base64 -d
   kubectl get secret botburrow-agents-secrets -n botburrow-agents -o jsonpath='{.data.FORGEJO_TOKEN}' | base64 -d
   ```

2. Verify ConfigMap URL is correct:
   ```bash
   kubectl get configmap agent-definitions-repos -n botburrow-agents -o jsonpath='{.data.repo-url}'
   ```

3. Check git-sync logs:
   ```bash
   kubectl logs -n botburrow-agents POD_NAME -c git-sync
   ```

### Repository not found

1. Verify repository exists in Forgejo UI
2. Check repository is under `botburrow` organization
3. Verify repository name is exactly `agent-definitions`

### Token expired

Tokens in Forgejo can expire. Generate a new token and update the Secret:
1. Generate new token in Forgejo UI
2. Update `botburrow-agents-sealedsecrets.yml.template`
3. Re-generate SealedSecret
4. Apply to cluster

## Files Modified

This task updated the following files:

1. **`k8s/apexalgo-iad/configmap.yaml`**
   - Changed `repo-url` from GitHub to Forgejo
   - Updated `repo-name` from `jedarden/agent-definitions` to `botburrow/agent-definitions`

2. **`k8s/apexalgo-iad/coordinator-git-sync.yaml`**
   - Changed git-sync credentials from `GITHUB_USER/GITHUB_TOKEN` to `FORGEJO_USER/FORGEJO_TOKEN`

3. **`k8s/apexalgo-iad/runner-git-sync.yaml`**
   - Changed git-sync credentials from `GITHUB_USER/GITHUB_TOKEN` to `FORGEJO_USER/FORGEJO_TOKEN`

## Next Steps After Credential Setup

Once credentials are configured:

1. Monitor pod startup: `kubectl get pods -n botburrow-agents -w`
2. Verify git-sync logs show successful clone
3. Test agent activation with new configuration
4. Close bead bd-2wsm

## Related Documentation

- Forgejo README: `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/forgejo/README.md`
- Manual Setup Guide: `/home/coder/botburrow-agents/bd-13t-forgejo-manual-setup-guide.md`
- Deployment Options: `/home/coder/research/botburrow/docs/forgejo-github-sync-options.md`
