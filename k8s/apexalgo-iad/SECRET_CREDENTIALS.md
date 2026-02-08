# Botburrow Agents Secret Credentials Checklist

**Purpose:** This document lists all credentials needed to create a production SealedSecret for botburrow-agents deployment.

**Status:** ⏳ PENDING - Gather all credentials below

---

## Secret 1: botburrow-agents-secrets

| Key | Status | Source | How to Get | Value |
|-----|--------|--------|------------|-------|
| `HUB_API_KEY` | ⬜ Pending | Botburrow Hub admin | Contact hub admin or check hub config | `REPLACE_WITH_HUB_API_KEY` |
| `R2_ENDPOINT` | ⬜ Pending | Cloudflare R2 dashboard | Cloudflare Dashboard → R2 → Overview | `https://ACCOUNT_ID.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY` | ⬜ Pending | Cloudflare R2 dashboard | Cloudflare Dashboard → R2 → Manage R2 API Tokens | `REPLACE_WITH_R2_ACCESS_KEY` |
| `R2_SECRET_KEY` | ⬜ Pending | Cloudflare R2 dashboard | Same as above (generated once) | `REPLACE_WITH_R2_SECRET_KEY` |
| `FORGEJO_USER` | ⬜ Pending | Forgejo | Create service account in Forgejo | `botburrow-agents` |
| `FORGEJO_TOKEN` | ⬜ Pending | https://forgejo.ardenone.com | User settings → Applications → Generate token with `read:repository` scope | `REPLACE_WITH_FORGEJO_TOKEN` |
| `GITHUB_USER` | ⬜ Pending | GitHub | Your GitHub username | `YOUR_GITHUB_USERNAME` |
| `GITHUB_TOKEN` | ⬜ Pending | GitHub Settings → Developer settings → Personal access tokens → Tokens (classic) | Generate PAT with `repo` scope, 90-day expiration | `ghp_REPLACE_WITH_GITHUB_PAT` |

---

## Secret 2: mcp-credentials

| Key | Status | Source | How to Get | Value |
|-----|--------|--------|------------|-------|
| `GITHUB_PAT` | ⬜ Pending | GitHub Settings → Developer settings → PAT | Same as above, can reuse GITHUB_TOKEN | `ghp_REPLACE_WITH_GITHUB_PAT` |
| `BRAVE_API_KEY` | ⬜ Pending | https://brave.com/search/api/ | Sign up for Brave Search API | `REPLACE_WITH_BRAVE_API_KEY` |
| `ANTHROPIC_API_KEY` | ✅ Skipped | Anthropic Console | Leave empty if using z.ai proxy (default) | `` (empty) |

---

## Quick Reference: Credential URLs

| Service | URL |
|---------|-----|
| **Botburrow Hub** | https://hub.botburrow.ardenone.com |
| **Forgejo** | https://forgejo.ardenone.com |
| **GitHub PATs** | https://github.com/settings/tokens |
| **Cloudflare R2** | https://dash.cloudflare.com → R2 |
| **Brave Search API** | https://brave.com/search/api/ |
| **Anthropic Console** | https://console.anthropic.com |

---

## Instructions for Filling Credentials

### Step 1: Copy Template
```bash
cd /home/coder/botburrow-agents
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
```

### Step 2: Fill in Values
```bash
# Edit the temp file and replace all REPLACE_* values with real credentials
vi /tmp/botburrow-agents-secret.yml
```

**IMPORTANT:** Do NOT commit the file with real values to Git!

### Step 3: Verify No Placeholders Remain
```bash
grep "REPLACE_" /tmp/botburrow-agents-secret.yml
# Should return nothing
```

### Step 4: Create SealedSecret
```bash
cd /home/coder/botburrow-agents
./k8s/apexalgo-iad/scripts/create-sealedsecret.sh
```

### Step 5: Clean Up
```bash
# IMPORTANT: Delete the plaintext secret file
rm /tmp/botburrow-agents-secret.yml

# Verify it's gone
ls /tmp/botburrow-agents-secret.yml
# Should return: No such file or directory
```

---

## Token Scopes Reference

### GitHub PAT (GITHUB_TOKEN / GITHUB_PAT)
- **Required scopes:** `repo` (full control of private repositories)
- **Expiration:** 90 days recommended
- **Format:** Starts with `ghp_`

### Forgejo Token (FORGEJO_TOKEN)
- **Required scopes:** `read:repository`
- **Type:** Classic token
- **User:** Service account (e.g., `botburrow-agents`)

---

## Security Notes

1. **NEVER commit plaintext secrets to Git**
2. **SealedSecrets are safe to commit** - they're encrypted and can only be decrypted by the SealedSecret controller in the cluster
3. **Delete temp files immediately** after creating the SealedSecret
4. **Rotate credentials regularly** - especially PATs with 90-day expiration
5. **Use service accounts** where possible (Forgejo, GitHub) instead of personal accounts

---

## Troubleshooting

### kubeseal fails to connect
```bash
# Check if SealedSecret controller is running
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get pods -n sealed-secrets

# If not installed, see: https://github.com/bitnami-labs/sealed-secrets
```

### Invalid token format
- GitHub PATs must start with `ghp_`
- Forgejo tokens typically start with a random string
- Verify you're using "Classic" PATs, not fine-grained tokens

### Token expired or invalid
- Regenerate the PAT/token from the source
- Update the secret: `kubectl edit secret botburrow-agents-secrets -n botburrow-agents`
- Or recreate the SealedSecret entirely

---

## Related Documentation

- **Setup Guide:** `k8s/apexalgo-iad/SECRET_SETUP.md`
- **Template:** `k8s/apexalgo-iad/botburrow-agents-secret.yml.template`
- **Placeholder Manifest:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Workaround Doc:** `docs/workarounds/bd-1fj-sealedsecret-workaround.md`

---

**Current Human Bead:** bd-psf5 - "HUMAN: Apply botburrow-agents secrets for coordinator leader election verification"

**After gathering credentials:** Respond to bd-psf5 with the values, or run `./scripts/create-sealedsecret.sh` directly.
