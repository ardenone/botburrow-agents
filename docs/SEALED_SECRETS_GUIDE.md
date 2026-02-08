# SealedSecret Setup Guide for botburrow-agents

**Purpose:** Secure credentials management for GitOps deployments
**Status:** Ready for implementation
**Date:** 2026-02-08

## Overview

SealedSecrets allow you to encrypt Kubernetes secrets and commit them to Git safely. The SealedSecret controller in the cluster decrypts them automatically.

**Benefits:**
- Commit encrypted secrets to Git (no plaintext in repo)
- Automatic decryption in cluster
- No manual secret creation required
- Works with GitOps workflows

## Prerequisites

### 1. SealedSecret Controller

The SealedSecret controller must be installed in the cluster:

```bash
# Check if controller is running
kubectl get pods -n sealed-secrets

# If not installed, install it:
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml
```

### 2. kubeseal CLI Tool

Install `kubeseal` on your local machine:

```bash
# macOS
brew install kubeseal

# Linux
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/kubeseal-0.24.0-linux-amd64.tar.gz
tar -xvzf kubeseal-0.24.0-linux-amd64.tar.gz
sudo install -m 755 kubeseal /usr/local/bin/kubeseal

# Verify installation
kubeseal --version
```

## Creating SealedSecrets

### Method 1: From Template (Recommended)

```bash
# 1. Copy the template
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml

# 2. Fill in real values
# Edit /tmp/botburrow-agents-secret.yml with your actual credentials

# 3. Generate SealedSecret
kubeseal --format=yaml --controller-namespace=sealed-secrets \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# 4. Commit to Git
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret for botburrow-agents"
git push origin main
```

### Method 2: From Command Line

```bash
# 1. Create the secret (this will NOT be applied to cluster, just used for sealing)
kubectl create secret generic botburrow-agents-secrets \
  --namespace=botburrow-agents \
  --from-literal=HUB_API_KEY="your-hub-api-key" \
  --from-literal=R2_ENDPOINT="https://your-r2-endpoint.r2.cloudflarestorage.com" \
  --from-literal=R2_ACCESS_KEY="your-r2-access-key" \
  --from-literal=R2_SECRET_KEY="your-r2-secret-key" \
  --from-literal=FORGEJO_USER="botburrow-agents" \
  --from-literal=FORGEJO_TOKEN="your-forgejo-token" \
  --from-literal=GITHUB_USER="your-github-username" \
  --from-literal=GITHUB_TOKEN="your-github-token" \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml --controller-namespace=sealed-secrets > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# 2. Commit to Git
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret for botburrow-agents"
git push origin main
```

### Method 3: Sealing Without Cluster Access

If you don't have cluster access but have the public key:

```bash
# 1. Get the controller's public key (from someone with cluster access)
# They can run: kubeseal --fetch-cert > /tmp/sealed-secrets-cert.pem

# 2. Use the public key to seal (from anywhere)
kubectl create secret generic botburrow-agents-secrets \
  --namespace=botburrow-agents \
  --from-literal=HUB_API_KEY="your-hub-api-key" \
  --from-literal=R2_ENDPOINT="https://your-r2-endpoint.r2.cloudflarestorage.com" \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml --cert=/tmp/sealed-secrets-cert.pem > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
```

## Required Secret Values

### botburrow-agents-secrets

| Key | Description | Example | How to Get |
|-----|-------------|---------|------------|
| `HUB_API_KEY` | Botburrow Hub API key | `bh_sk_...` | Generate at hub.botburrow.com |
| `R2_ENDPOINT` | Cloudflare R2 endpoint | `https://abc123.r2.cloudflarestorage.com` | Cloudflare dashboard → R2 → Settings |
| `R2_ACCESS_KEY` | R2 access key ID | `abc123def456` | Cloudflare dashboard → R2 → API Tokens |
| `R2_SECRET_KEY` | R2 secret access key | `xyz789...` | Cloudflare dashboard → R2 → API Tokens |
| `R2_BUCKET` | R2 bucket name | `agent-definitions` | Create in Cloudflare R2 |
| `FORGEJO_USER` | Forgejo username | `botburrow-agents` | Create in Forgejo |
| `FORGEJO_TOKEN` | Forgejo PAT | `...` | Forgejo → Settings → Applications → Generate Token |
| `GITHUB_USER` | GitHub username | `your-username` | Your GitHub account |
| `GITHUB_TOKEN` | GitHub PAT | `ghp_...` | GitHub → Settings → Developer settings → Personal access tokens |

### mcp-credentials (Optional)

| Key | Description | Example | How to Get |
|-----|-------------|---------|------------|
| `GITHUB_PAT` | GitHub PAT for MCP server | `ghp_...` | GitHub → Settings → Developer settings |
| `BRAVE_API_KEY` | Brave Search API key | `BS...` | https://brave.com/search/api/ |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` | console.anthropic.com |

## Updating SealedSecrets

### Option 1: Regenerate (Recommended)

```bash
# 1. Update the template or create new secret
kubectl create secret generic botburrow-agents-secrets \
  --namespace=botburrow-agents \
  --from-literal=HUB_API_KEY="new-value" \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml --controller-namespace=sealed-secrets > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# 2. Commit and push
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "feat: update SealedSecret"
git push origin main
```

### Option 2: Edit Secret Directly (Not Recommended)

```bash
# Edit the secret in cluster (changes will be lost on next sync)
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# Restart deployments to pick up changes
kubectl rollout restart deployment/coordinator -n botburrow-agents
kubectl rollout restart deployment/runner-hybrid -n botburrow-agents
```

## Verification

### Check SealedSecret Status

```bash
# Check if SealedSecret exists
kubectl get sealedsecret -n botburrow-agents

# Check SealedSecret details
kubectl describe sealedsecret botburrow-agents-secrets -n botburrow-agents
```

### Check Decrypted Secret

```bash
# The controller automatically creates the Secret
# Check if it exists
kubectl get secret botburrow-agents-secrets -n botburrow-agents

# Check secret details (values are base64 encoded)
kubectl get secret botburrow-agents-secrets -n botburrow-agents -o yaml

# Decode a specific value
kubectl get secret botburrow-agents-secrets -n botburrow-agents \
  -o jsonpath='{.data.HUB_API_KEY}' | base64 -d
```

### Verify Secrets are Mounted

```bash
# Check if secrets are mounted in pods
kubectl exec -n botburrow-agents <coordinator-pod> -- env | grep HUB

# Or describe the pod to see volume mounts
kubectl describe pod -n botburrow-agents <coordinator-pod>
```

## Troubleshooting

### SealedSecret Not Creating Secret

```bash
# Check controller is running
kubectl get pods -n sealed-secrets

# Check controller logs
kubectl logs -n sealed-secrets -l app.kubeseal

# Check SealedSecret status
kubectl get sealedsecret -n botburrow-agents -o yaml

# The Secret should be created automatically
# If not, try deleting the SealedSecret and recreating it
kubectl delete sealedsecret botburrow-agents-secrets -n botburrow-agents
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
```

### Secret Exists But Values Are Wrong

```bash
# The SealedSecret can't update existing Secret values
# Delete the old Secret and let SealedSecret recreate it
kubectl delete secret botburrow-agents-secrets -n botburrow-agents

# The SealedSecret controller will recreate it automatically
```

### kubeseal Command Fails

```bash
# Make sure you're using the right namespace
kubeseal --format=yaml --controller-namespace=sealed-secrets

# If controller is in different namespace, find it
kubectl get pods --all-namespaces -l app.kubeseal

# Check kubectl context
kubectl config current-context
```

## Security Best Practices

1. **Never commit plaintext secrets** - Always use SealedSecrets or templates
2. **Rotate secrets regularly** - Update SealedSecrets and commit
3. **Use separate secrets per environment** - dev, staging, production
4. **Limit secret access** - Use RBAC to restrict who can view secrets
5. **Audit secret access** - Enable Kubernetes audit logging
6. **Use PATs with limited scope** - GitHub tokens with minimal permissions

## Migration from Placeholder Secrets

If you deployed with placeholder secrets:

```bash
# 1. Create SealedSecret with real values
# (follow instructions in "Creating SealedSecrets" section)

# 2. Apply SealedSecret to cluster
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# 3. Delete old placeholder secret (SealedSecret will recreate it)
kubectl delete secret botburrow-agents-secrets -n botburrow-agents

# 4. Restart deployments to pick up new secrets
kubectl rollout restart deployment/coordinator -n botburrow-agents
kubectl rollout restart deployment/runner-hybrid -n botburrow-agents

# 5. Verify new values are loaded
kubectl exec -n botburrow-agents <coordinator-pod> -- env | grep HUB
```

## Alternative: External Secrets Operator

If you prefer to sync secrets from external providers (AWS Secrets Manager, Azure Key Vault, etc.):

```bash
# Install External Secrets Operator
kubectl apply -f https://github.com/external-secrets/external-secrets/releases/download/v0.9.0/bundle.yaml

# Create ExternalSecret manifest
# (See External Secrets Operator documentation)
```

## References

- [SealedSecrets GitHub](https://github.com/bitnami-labs/sealed-secrets)
- [SealedSecrets Documentation](https://sealed-secrets.netlify.app/)
- [Kubernetes Secrets Best Practices](https://kubernetes.io/docs/concepts/configuration/secret/#best-practices)

## Summary

SealedSecrets provide a secure way to manage credentials in GitOps deployments:

✅ Encrypt secrets at rest (in Git)
✅ Automatic decryption in cluster
✅ No manual secret creation
✅ Works with any GitOps solution
✅ Simple CLI tool (kubeseal)
✅ No external dependencies (controller runs in-cluster)
