#!/bin/bash
# bd-3f3 Verification Script - Run BEFORE executing cluster-admin commands
# This verifies that all prerequisites are in place

set -e

echo "=========================================="
echo "bd-3f3: ArgoCD Installation Readiness Check"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counters
checks_passed=0
checks_failed=0
checks_total=8

echo "Running pre-flight checks..."
echo ""

# Check 1: Cluster-admin kubeconfig
echo -n "✓ Checking cluster-admin permissions... "
if kubectl auth can-i create clusterrolebinding &>/dev/null; then
    echo -e "${GREEN}PASS${NC}"
    ((checks_passed++))
else
    echo -e "${RED}FAIL${NC}"
    echo "  ERROR: You need cluster-admin credentials for apexalgo-iad cluster"
    echo "  Current kubeconfig: $KUBECONFIG"
    echo "  Set KUBECONFIG to your cluster-admin kubeconfig file"
    ((checks_failed++))
fi

# Check 2: botburrow-agents namespace exists
echo -n "✓ Checking botburrow-agents namespace... "
if kubectl get namespace botburrow-agents &>/dev/null; then
    echo -e "${GREEN}PASS${NC}"
    ((checks_passed++))
else
    echo -e "${RED}FAIL${NC}"
    echo "  ERROR: Namespace botburrow-agents does not exist"
    ((checks_failed++))
fi

# Check 3: devpod-observer ServiceAccount exists
echo -n "✓ Checking devpod-observer ServiceAccount... "
if kubectl get serviceaccount devpod-observer -n devpod-observer &>/dev/null; then
    echo -e "${GREEN}PASS${NC}"
    ((checks_passed++))
else
    echo -e "${RED}FAIL${NC}"
    echo "  ERROR: ServiceAccount devpod-observer does not exist in devpod-observer namespace"
    ((checks_failed++))
fi

# Check 4: ArgoCD namespace should NOT exist yet
echo -n "✓ Checking ArgoCD namespace does NOT exist... "
if ! kubectl get namespace argocd &>/dev/null; then
    echo -e "${GREEN}PASS${NC} (expected)"
    ((checks_passed++))
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  ArgoCD namespace already exists - may need to clean up first"
    ((checks_passed++))
fi

# Check 5: cluster-admin binding should NOT exist yet
echo -n "✓ Checking cluster-admin binding does NOT exist... "
if ! kubectl get clusterrolebinding devpod-observer-cluster-admin &>/dev/null; then
    echo -e "${GREEN}PASS${NC} (expected)"
    ((checks_passed++))
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  ClusterRoleBinding already exists - may be left over from previous run"
    ((checks_passed++))
fi

# Check 6: ArgoCD manifests exist locally
echo -n "✓ Checking ArgoCD manifests exist... "
if [ -f "k8s/apexalgo-iad/argocd/install.yaml" ]; then
    echo -e "${GREEN}PASS${NC}"
    ((checks_passed++))
else
    echo -e "${RED}FAIL${NC}"
    echo "  ERROR: ArgoCD manifest not found at k8s/apexalgo-iad/argocd/install.yaml"
    echo "  Make sure you're running this from /home/coder/botburrow-agents"
    ((checks_failed++))
fi

# Check 7: Execution guide exists
echo -n "✓ Checking execution guide exists... "
if [ -f "docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md" ]; then
    echo -e "${GREEN}PASS${NC}"
    ((checks_passed++))
else
    echo -e "${RED}FAIL${NC}"
    echo "  ERROR: Execution guide not found"
    ((checks_failed++))
fi

# Check 8: kubectl-proxy connectivity (optional)
echo -n "✓ Checking kubectl-proxy connectivity... "
if kubectl get pods -n devpod-observer -l app=kubectl-proxy &>/dev/null; then
    pod_count=$(kubectl get pods -n devpod-observer -l app=kubectl-proxy --no-headers 2>/dev/null | wc -l)
    if [ "$pod_count" -gt 0 ]; then
        echo -e "${GREEN}PASS${NC} ($pod_count pod(s) running)"
        ((checks_passed++))
    else
        echo -e "${YELLOW}WARNING${NC}"
        echo "  No kubectl-proxy pods found - workers may not be able to install ArgoCD"
        ((checks_passed++))
    fi
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  Cannot check kubectl-proxy - may not have access to devpod-observer namespace"
    ((checks_passed++))
fi

echo ""
echo "=========================================="
echo "Results: $checks_passed/$checks_total checks passed"
echo "=========================================="
echo ""

if [ $checks_failed -eq 0 ]; then
    echo -e "${GREEN}✓ READY FOR EXECUTION${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Review execution guide: docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md"
    echo "2. Execute Phase 1: Grant cluster-admin permissions"
    echo "3. Monitor Phase 2: Workers install ArgoCD"
    echo "4. Execute Phase 3: Revoke cluster-admin permissions"
    echo ""
    exit 0
else
    echo -e "${RED}✗ NOT READY - Fix errors above before proceeding${NC}"
    echo ""
    exit 1
fi
