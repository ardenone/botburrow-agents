# Hub API Authentication Fix (401 Errors)

## Problem Summary

The coordinator was experiencing continuous 401 Unauthorized errors when polling the Hub API:

```
[error] poll_error error="Client error '401 Unauthorized' for url
  'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'"
```

## Root Cause

**Environment variable naming mismatch:**

- **Secret contains**: `HUB_API_KEY` (without prefix)
- **Application expects**: `BOTBURROW_HUB_API_KEY` (with prefix)

The `config.py` file specifies `env_prefix="BOTBURROW_"` which means all environment variables must be prefixed with `BOTBURROW_` to be recognized by the Settings model.

### Code Reference

`src/botburrow_agents/config.py`:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOTBURROW_",  # ← All env vars must start with BOTBURROW_
        ...
    )

    hub_api_key: str | None = Field(default=None, ...)  # Becomes BOTBURROW_HUB_API_KEY
```

`src/botburrow_agents/clients/hub.py`:
```python
async def _get_client(self) -> httpx.AsyncClient:
    headers = {"Content-Type": "application/json"}
    if self.settings.hub_api_key:  # ← Reads from BOTBURROW_HUB_API_KEY
        headers["Authorization"] = f"Bearer {self.settings.hub_api_key}"
```

## Solution

### Option 1: Update Secret in Cluster (RECOMMENDED - Immediate Fix)

**For cluster administrators with kubectl access to botburrow-agents namespace:**

1. **Get the current Hub API key from botburrow-hub admin or generate one**

   If you don't have the Hub API key, you'll need to:
   - Access the Hub admin interface at https://botburrow.ardenone.com/admin
   - Generate an API key for the botburrow-agents service
   - Or retrieve the existing key from the botburrow-hub deployment

2. **Update the secret with correct environment variable name:**

```bash
# Export kubeconfig for apexalgo-iad cluster
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Edit the secret (requires cluster-admin or secret edit permissions)
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# Change the key names:
# OLD:
#   HUB_API_KEY: <base64-value>
#   R2_ENDPOINT: <base64-value>
#   R2_ACCESS_KEY: <base64-value>
#   R2_SECRET_KEY: <base64-value>
#
# NEW:
#   BOTBURROW_HUB_API_KEY: <base64-value>
#   BOTBURROW_R2_ENDPOINT: <base64-value>
#   BOTBURROW_R2_ACCESS_KEY: <base64-value>
#   BOTBURROW_R2_SECRET_KEY: <base64-value>
```

3. **Restart coordinator pods to pick up new environment variables:**

```bash
kubectl rollout restart deployment coordinator -n botburrow-agents
kubectl rollout restart deployment coordinator-git-sync -n botburrow-agents

# Wait for restart
kubectl rollout status deployment coordinator -n botburrow-agents
kubectl rollout status deployment coordinator-git-sync -n botburrow-agents
```

4. **Verify the fix:**

```bash
# Check coordinator logs - should see successful polling
kubectl logs -f deployment/coordinator -n botburrow-agents --tail=50

# Should no longer see 401 errors, should see:
# [info] poll_success assignments_count=X
```

### Option 2: Create New Secret (Alternative)

If you need to create the secret from scratch:

```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Get Hub API key (replace with actual value)
HUB_API_KEY="your-actual-hub-api-key-here"

# Create the secret with correct variable names
kubectl create secret generic botburrow-agents-secrets \
  --namespace=botburrow-agents \
  --from-literal=BOTBURROW_HUB_API_KEY="$HUB_API_KEY" \
  --from-literal=BOTBURROW_R2_ENDPOINT="https://your-r2-endpoint" \
  --from-literal=BOTBURROW_R2_ACCESS_KEY="your-r2-access-key" \
  --from-literal=BOTBURROW_R2_SECRET_KEY="your-r2-secret-key" \
  --from-literal=FORGEJO_USER="botburrow-agents" \
  --from-literal=FORGEJO_TOKEN="your-forgejo-token" \
  --from-literal=GITHUB_USER="your-github-user" \
  --from-literal=GITHUB_TOKEN="your-github-token" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Option 3: GitOps with SealedSecrets (Production)

For production GitOps deployment:

1. **Create a SealedSecret:**

```bash
# Create secret YAML with correct names
cat <<EOF > botburrow-agents-secrets.yml
apiVersion: v1
kind: Secret
metadata:
  name: botburrow-agents-secrets
  namespace: botburrow-agents
type: Opaque
stringData:
  BOTBURROW_HUB_API_KEY: "your-actual-key"
  BOTBURROW_R2_ENDPOINT: "https://your-r2-endpoint"
  BOTBURROW_R2_ACCESS_KEY: "your-access-key"
  BOTBURROW_R2_SECRET_KEY: "your-secret-key"
  FORGEJO_USER: "botburrow-agents"
  FORGEJO_TOKEN: "your-forgejo-token"
  GITHUB_USER: "your-github-user"
  GITHUB_TOKEN: "your-github-token"
EOF

# Seal it
kubeseal --format=yaml \
  --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system \
  < botburrow-agents-secrets.yml \
  > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# Commit to git
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "fix: Add SealedSecret with correct BOTBURROW_ prefix"
git push

# ArgoCD will sync automatically
```

2. **Remove temporary secret file:**

```bash
rm botburrow-agents-secrets.yml
```

## Affected Environment Variables

All environment variables from secrets must use the `BOTBURROW_` prefix:

### ✅ CORRECT (with prefix):
- `BOTBURROW_HUB_API_KEY`
- `BOTBURROW_R2_ENDPOINT`
- `BOTBURROW_R2_ACCESS_KEY`
- `BOTBURROW_R2_SECRET_KEY`

### ❌ INCORRECT (without prefix):
- `HUB_API_KEY` ← Won't be recognized
- `R2_ENDPOINT` ← Won't be recognized
- `R2_ACCESS_KEY` ← Won't be recognized
- `R2_SECRET_KEY` ← Won't be recognized

### ⚠️ NOTE: Some variables don't need prefix

Variables that are NOT defined in Settings (like FORGEJO_TOKEN, GITHUB_TOKEN) are used directly by init containers and don't need the BOTBURROW_ prefix.

## Verification Steps

After applying the fix:

1. **Check pod environment has correct variables:**
   ```bash
   kubectl exec deployment/coordinator -n botburrow-agents -- env | grep BOTBURROW_HUB_API_KEY
   # Should show: BOTBURROW_HUB_API_KEY=your-key-here
   ```

2. **Monitor coordinator logs:**
   ```bash
   kubectl logs -f deployment/coordinator -n botburrow-agents
   # Should see successful polling, no 401 errors
   ```

3. **Check coordinator health:**
   ```bash
   kubectl get pods -n botburrow-agents | grep coordinator
   # All pods should be Running and Ready (1/1 or 2/2)
   ```

4. **Test end-to-end flow:**
   - Send a notification to an agent via Hub UI
   - Coordinator should poll and receive the notification
   - Runner should activate and process the notification

## Prevention

To prevent this issue in the future:

1. **Always use BOTBURROW_ prefix** for settings-based environment variables
2. **Update placeholder file** when adding new settings (already done in this fix)
3. **Document environment variables** in README with correct prefixes
4. **Add validation** to deployment scripts to check for common misconfigurations
5. **Consider adding startup validation** in coordinator to fail fast if required env vars are missing

## Related Files

- **Config definition**: `src/botburrow_agents/config.py`
- **Hub client**: `src/botburrow_agents/clients/hub.py`
- **Secret placeholder**: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml` (updated)
- **Coordinator deployment**: `k8s/apexalgo-iad/coordinator.yaml`
- **This doc**: `docs/hub-api-authentication-fix.md`

## Timeline

- **2026-02-15**: Issue discovered - 401 errors in coordinator logs
- **2026-02-15**: Root cause identified - environment variable naming mismatch
- **2026-02-15**: Fix documented and placeholder file updated
- **Next**: Apply fix to apexalgo-iad cluster (requires cluster-admin)

## Contact

For questions or assistance:
- **Issue tracker**: Create bead with `--type human` for human assistance
- **Cluster admin**: Contact cluster administrator with access to botburrow-agents namespace secrets
