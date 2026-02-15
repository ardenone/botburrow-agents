#!/bin/bash
# Revoke temporary cluster-admin from devpod-observer after ArgoCD installation
# Related bead: bd-fvs

set -e

echo "=================================================="
echo "ArgoCD Installation - Permission Revocation Script"
echo "=================================================="
echo ""
echo "This script will:"
echo "  1. Verify ArgoCD is installed"
echo "  2. Revoke cluster-admin from devpod-observer"
echo "  3. Verify revocation"
echo ""

# Step 1: Verify ArgoCD installation
echo "Step 1: Verifying ArgoCD installation..."
if ! kubectl get namespace argocd &>/dev/null; then
    echo "❌ ERROR: ArgoCD namespace does not exist"
    echo "Cannot revoke permissions - installation not complete"
    exit 1
fi

argocd_pods=$(kubectl get pods -n argocd --no-headers 2>/dev/null | wc -l)
if [ "$argocd_pods" -eq 0 ]; then
    echo "❌ ERROR: No ArgoCD pods found"
    echo "Cannot revoke permissions - installation not complete"
    exit 1
fi

running_pods=$(kubectl get pods -n argocd --no-headers 2>/dev/null | grep -c "Running" || true)
echo "  ✅ ArgoCD namespace exists"
echo "  ✅ ArgoCD pods: $running_pods/$argocd_pods Running"

# Check if Application exists (optional)
if kubectl get application botburrow-agents -n argocd &>/dev/null; then
    echo "  ✅ botburrow-agents Application exists"
fi

echo ""
read -p "Proceed with permission revocation? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Step 2: Revoke cluster-admin
echo ""
echo "Step 2: Deleting cluster-admin ClusterRoleBinding..."
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Step 3: Verify revocation
echo ""
echo "Step 3: Verifying revocation..."
if kubectl get clusterrolebinding devpod-observer-cluster-admin &>/dev/null; then
    echo "❌ ERROR: ClusterRoleBinding still exists"
    exit 1
fi
echo "  ✅ ClusterRoleBinding deleted"

# Verify permissions are revoked
echo ""
echo "Step 4: Testing permission revocation..."
# This command should fail, but we want to capture the output
if kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer 2>/dev/null | grep -q "yes"; then
    echo "⚠️  WARNING: devpod-observer can still create namespaces"
    echo "Additional cluster-admin bindings may exist"
else
    echo "  ✅ devpod-observer cannot create namespaces (correct)"
fi

echo ""
echo "✅ Permissions revoked successfully!"
echo ""
echo "Final verification:"
kubectl get clusterrolebinding | grep devpod-observer || echo "  ✅ No cluster-admin bindings found"
echo ""
echo "ArgoCD installation complete!"
echo "  - Namespace: argocd"
echo "  - Pods: $running_pods Running"
echo "  - Permissions: Revoked to read-only"
echo ""
