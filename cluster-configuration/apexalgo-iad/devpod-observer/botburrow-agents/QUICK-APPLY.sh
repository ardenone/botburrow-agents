#!/bin/bash
# Quick application script for cluster-admin
# Bead: bd-1qs
# Purpose: Apply RBAC manifests for devpod-observer in botburrow-agents namespace

set -euo pipefail

echo "🔒 Applying RBAC manifests for devpod-observer in botburrow-agents namespace"
echo "Cluster: apexalgo-iad"
echo "Bead: bd-1qs"
echo ""

# Ensure we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if cluster-admin access
if ! kubectl auth can-i create roles -n botburrow-agents &>/dev/null; then
  echo "❌ ERROR: You do not have cluster-admin access to create roles in botburrow-agents namespace"
  echo "Please set KUBECONFIG to cluster-admin kubeconfig for apexalgo-iad cluster"
  exit 1
fi

echo "✅ Verified cluster-admin access"
echo ""

# Apply manifests
echo "📋 Applying secrets-manager-role.yml..."
kubectl apply -f secrets-manager-role.yml

echo "📋 Applying deployment-scaler-role.yml..."
kubectl apply -f deployment-scaler-role.yml

echo ""
echo "✅ RBAC manifests applied successfully!"
echo ""

# Verify application
echo "🔍 Verifying roles..."
kubectl get role -n botburrow-agents secrets-manager deployment-scaler

echo ""
echo "🔍 Verifying rolebindings..."
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager devpod-observer-scaler

echo ""
echo "✅ Verification complete!"
echo ""
echo "Next steps:"
echo "1. Workers can now access secrets in botburrow-agents namespace"
echo "2. Workers can scale deployments and HPAs"
echo "3. Beads bd-2jm and bd-3o6 are unblocked"
