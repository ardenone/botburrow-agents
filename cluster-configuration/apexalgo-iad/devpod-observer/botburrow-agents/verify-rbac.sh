#!/bin/bash
#
# Verification script for devpod-observer RBAC in botburrow-agents namespace
# Run this script AFTER applying the RBAC manifests to verify permissions
#
# Usage: ./verify-rbac.sh
# Requirements: kubectl with cluster-admin access to apexalgo-iad

set -euo pipefail

echo "=================================================="
echo "Verifying devpod-observer RBAC in botburrow-agents"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check command output
check_result() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $1"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}: $1"
        return 1
    fi
}

# Function to check auth with expected result
check_auth() {
    local expected=$1
    local verb=$2
    local resource=$3
    local namespace=$4

    result=$(kubectl auth can-i "$verb" "$resource" -n "$namespace" \
        --as=system:serviceaccount:devpod-observer:devpod-observer 2>&1)

    if [ "$result" = "$expected" ]; then
        echo -e "${GREEN}✓ PASS${NC}: devpod-observer can $verb $resource in $namespace"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}: devpod-observer CANNOT $verb $resource in $namespace (got: $result)"
        return 1
    fi
}

FAILED_CHECKS=0

echo "Step 1: Verify Roles exist"
echo "----------------------------"
kubectl get role -n botburrow-agents secrets-manager &>/dev/null
check_result "Role 'secrets-manager' exists" || ((FAILED_CHECKS++))

kubectl get role -n botburrow-agents deployment-scaler &>/dev/null
check_result "Role 'deployment-scaler' exists" || ((FAILED_CHECKS++))

echo ""
echo "Step 2: Verify RoleBindings exist"
echo "-----------------------------------"
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager &>/dev/null
check_result "RoleBinding 'devpod-observer-secrets-manager' exists" || ((FAILED_CHECKS++))

kubectl get rolebinding -n botburrow-agents devpod-observer-scaler &>/dev/null
check_result "RoleBinding 'devpod-observer-scaler' exists" || ((FAILED_CHECKS++))

echo ""
echo "Step 3: Verify Secret Permissions (bd-2jm)"
echo "--------------------------------------------"
check_auth "yes" "get" "secrets" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "list" "secrets" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "patch" "secrets" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "update" "secrets" "botburrow-agents" || ((FAILED_CHECKS++))

# Verify devpod-observer CANNOT delete secrets (should be "no")
check_auth "no" "delete" "secrets" "botburrow-agents" || ((FAILED_CHECKS++))

echo ""
echo "Step 4: Verify Deployment Scaling Permissions (bd-3o6)"
echo "--------------------------------------------------------"
check_auth "yes" "get" "deployments" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "list" "deployments" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "patch" "deployments/scale" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "update" "deployments/scale" "botburrow-agents" || ((FAILED_CHECKS++))

# Verify devpod-observer CANNOT delete deployments (should be "no")
check_auth "no" "delete" "deployments" "botburrow-agents" || ((FAILED_CHECKS++))

echo ""
echo "Step 5: Verify HPA Permissions (bd-3o6)"
echo "-----------------------------------------"
check_auth "yes" "get" "horizontalpodautoscalers" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "list" "horizontalpodautoscalers" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "patch" "horizontalpodautoscalers" "botburrow-agents" || ((FAILED_CHECKS++))

echo ""
echo "Step 6: Verify Pod Permissions (read-only)"
echo "--------------------------------------------"
check_auth "yes" "get" "pods" "botburrow-agents" || ((FAILED_CHECKS++))
check_auth "yes" "list" "pods" "botburrow-agents" || ((FAILED_CHECKS++))

# Verify devpod-observer CANNOT delete pods (should be "no")
check_auth "no" "delete" "pods" "botburrow-agents" || ((FAILED_CHECKS++))

echo ""
echo "Step 7: Verify Port-Forward Permission"
echo "----------------------------------------"
check_auth "yes" "create" "pods/portforward" "botburrow-agents" || ((FAILED_CHECKS++))

echo ""
echo "=================================================="
if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED${NC}"
    echo "devpod-observer has correct RBAC permissions in botburrow-agents namespace"
    echo ""
    echo "Next steps:"
    echo "1. Update CLUSTER-ADMIN-README.md status to 'APPLIED'"
    echo "2. Commit and push changes to main branch"
    echo "3. Workers will automatically retry blocked beads (bd-12r, bd-2jm, bd-3o6)"
    exit 0
else
    echo -e "${RED}✗ $FAILED_CHECKS CHECK(S) FAILED${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Verify manifests were applied: kubectl get role,rolebinding -n botburrow-agents"
    echo "2. Check RoleBinding subjects: kubectl get rolebinding -n botburrow-agents -o yaml"
    echo "3. Restart kubectl-proxy to flush RBAC cache: kubectl rollout restart deployment/kubectl-proxy -n devpod-observer"
    exit 1
fi
