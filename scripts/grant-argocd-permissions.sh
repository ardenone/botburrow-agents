#!/bin/bash
# Grant temporary cluster-admin to devpod-observer for ArgoCD installation
# Related bead: bd-fvs

set -e

echo "=================================================="
echo "ArgoCD Installation - Permission Grant Script"
echo "=================================================="
echo ""
echo "This script will:"
echo "  1. Grant temporary cluster-admin to devpod-observer"
echo "  2. Verify the grant"
echo "  3. Provide revocation instructions"
echo ""
echo "⚠️  SECURITY NOTE:"
echo "  - These permissions should be revoked within 30 minutes"
echo "  - Run revoke-argocd-permissions.sh after installation"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1: Creating cluster-admin ClusterRoleBinding..."
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

echo ""
echo "Step 2: Verifying ClusterRoleBinding..."
kubectl get clusterrolebinding devpod-observer-cluster-admin

echo ""
echo "✅ Permissions granted successfully!"
echo ""
echo "Next steps:"
echo "  1. Workers will automatically install ArgoCD (< 5 minutes)"
echo "  2. Monitor installation: kubectl get pods -n argocd"
echo "  3. After installation completes, run: ./scripts/revoke-argocd-permissions.sh"
echo ""
echo "⏰ REMINDER: Revoke permissions within 30 minutes"
echo ""
