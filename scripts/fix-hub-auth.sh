#!/bin/bash
# Fix Hub API authentication by updating environment variable names in secret
# Requires: kubectl access to botburrow-agents namespace with secret edit permissions

set -euo pipefail

NAMESPACE="botburrow-agents"
SECRET_NAME="botburrow-agents-secrets"
KUBECONFIG="${KUBECONFIG:-/home/coder/.kube/apexalgo-iad.kubeconfig}"

echo "==================================================================="
echo "Hub API Authentication Fix"
echo "==================================================================="
echo ""
echo "This script will update the botburrow-agents-secrets to use the"
echo "correct BOTBURROW_ prefix for environment variables."
echo ""
echo "Target:"
echo "  Namespace: $NAMESPACE"
echo "  Secret:    $SECRET_NAME"
echo "  Cluster:   $(kubectl config current-context 2>/dev/null || echo 'default')"
echo ""

# Check if secret exists
if ! kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &>/dev/null; then
  echo "ERROR: Secret $SECRET_NAME not found in namespace $NAMESPACE"
  echo ""
  echo "You may need to create it first using:"
  echo "  kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
  exit 1
fi

echo "Current secret keys (showing first 20 chars of values):"
kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o json | \
  jq -r '.data | to_entries[] | "\(.key): \(.value | @base64d | .[0:20])..."'
echo ""

# Ask for confirmation
read -p "Do you want to update the secret with BOTBURROW_ prefixes? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo "Updating secret..."

# Get current secret data
SECRET_JSON=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o json)

# Extract current values (if they exist)
HUB_API_KEY=$(echo "$SECRET_JSON" | jq -r '.data.HUB_API_KEY // .data.BOTBURROW_HUB_API_KEY // ""' | base64 -d || echo "")
R2_ENDPOINT=$(echo "$SECRET_JSON" | jq -r '.data.R2_ENDPOINT // .data.BOTBURROW_R2_ENDPOINT // ""' | base64 -d || echo "")
R2_ACCESS_KEY=$(echo "$SECRET_JSON" | jq -r '.data.R2_ACCESS_KEY // .data.BOTBURROW_R2_ACCESS_KEY // ""' | base64 -d || echo "")
R2_SECRET_KEY=$(echo "$SECRET_JSON" | jq -r '.data.R2_SECRET_KEY // .data.BOTBURROW_R2_SECRET_KEY // ""' | base64 -d || echo "")
FORGEJO_USER=$(echo "$SECRET_JSON" | jq -r '.data.FORGEJO_USER // ""' | base64 -d || echo "")
FORGEJO_TOKEN=$(echo "$SECRET_JSON" | jq -r '.data.FORGEJO_TOKEN // ""' | base64 -d || echo "")
GITHUB_USER=$(echo "$SECRET_JSON" | jq -r '.data.GITHUB_USER // ""' | base64 -d || echo "")
GITHUB_TOKEN=$(echo "$SECRET_JSON" | jq -r '.data.GITHUB_TOKEN // ""' | base64 -d || echo "")

# Check if we got the HUB_API_KEY
if [[ -z "$HUB_API_KEY" || "$HUB_API_KEY" == "placeholder-update-me" ]]; then
  echo ""
  echo "WARNING: HUB_API_KEY appears to be empty or placeholder."
  echo "You need to provide a valid Hub API key."
  echo ""
  read -p "Enter Hub API key (or press Enter to skip): " NEW_HUB_API_KEY
  if [[ -n "$NEW_HUB_API_KEY" ]]; then
    HUB_API_KEY="$NEW_HUB_API_KEY"
  else
    echo "Keeping current value (may not work if it's a placeholder)"
  fi
fi

# Create updated secret
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: $SECRET_NAME
  namespace: $NAMESPACE
  labels:
    app.kubernetes.io/name: botburrow-agents
type: Opaque
stringData:
  # Hub API (with BOTBURROW_ prefix)
  BOTBURROW_HUB_API_KEY: "$HUB_API_KEY"

  # R2 Storage (with BOTBURROW_ prefix)
  BOTBURROW_R2_ENDPOINT: "$R2_ENDPOINT"
  BOTBURROW_R2_ACCESS_KEY: "$R2_ACCESS_KEY"
  BOTBURROW_R2_SECRET_KEY: "$R2_SECRET_KEY"

  # Git access (no prefix needed - used by init containers)
  FORGEJO_USER: "$FORGEJO_USER"
  FORGEJO_TOKEN: "$FORGEJO_TOKEN"
  GITHUB_USER: "$GITHUB_USER"
  GITHUB_TOKEN: "$GITHUB_TOKEN"
EOF

if [[ $? -eq 0 ]]; then
  echo ""
  echo "✅ Secret updated successfully!"
  echo ""
  echo "Updated keys:"
  kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o json | \
    jq -r '.data | to_entries[] | .key' | sort
  echo ""

  # Restart coordinator
  read -p "Restart coordinator to apply changes? (yes/no): " restart_confirm
  if [[ "$restart_confirm" == "yes" ]]; then
    echo ""
    echo "Restarting coordinator deployments..."
    kubectl rollout restart deployment coordinator -n "$NAMESPACE"
    kubectl rollout restart deployment coordinator-git-sync -n "$NAMESPACE"

    echo ""
    echo "Waiting for rollout to complete..."
    kubectl rollout status deployment coordinator -n "$NAMESPACE" --timeout=120s
    kubectl rollout status deployment coordinator-git-sync -n "$NAMESPACE" --timeout=120s

    echo ""
    echo "✅ Coordinator restarted successfully!"
    echo ""
    echo "Checking logs for 401 errors (will tail for 30 seconds)..."
    timeout 30s kubectl logs -f deployment/coordinator -n "$NAMESPACE" --tail=20 || true

    echo ""
    echo "If you don't see 401 errors above, the fix is working! ✅"
  else
    echo ""
    echo "Coordinator not restarted. You can restart manually with:"
    echo "  kubectl rollout restart deployment coordinator -n $NAMESPACE"
    echo "  kubectl rollout restart deployment coordinator-git-sync -n $NAMESPACE"
  fi
else
  echo ""
  echo "❌ Failed to update secret"
  exit 1
fi

echo ""
echo "==================================================================="
echo "Fix complete!"
echo "==================================================================="
echo ""
echo "For more details, see: docs/hub-api-authentication-fix.md"
