#!/bin/bash
# =============================================================================
# Pre-flight Check Script for botburrow-agents Deployment
# =============================================================================
# This script validates prerequisites for deploying botburrow-agents
# to apexalgo-iad cluster using the simplified kubectl approach.
#
# Usage: ./preflight-check.sh [--kubeconfig /path/to/kubeconfig]
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default kubeconfig
KUBECONFIG="${KUBECONFIG:-/home/coder/.kube/apexalgo-iad.kubeconfig}"
NAMESPACE="botburrow-agents"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --kubeconfig)
      KUBECONFIG="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--kubeconfig /path/to/kubeconfig]"
      echo ""
      echo "This script validates prerequisites for botburrow-agents deployment."
      echo ""
      echo "Options:"
      echo "  --kubeconfig  Path to kubeconfig file (default: /home/coder/.kube/apexalgo-iad.kubeconfig)"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

echo "========================================================================"
echo "botburrow-agents Pre-flight Check"
echo "========================================================================"
echo ""

# Track overall status
ALL_GOOD=true

# Function to check a condition
check() {
  local description="$1"
  local command="$2"
  local critical="${3:-true}"

  echo -n "Checking $description... "

  if eval "$command" &>/dev/null; then
    echo -e "${GREEN}✓ PASS${NC}"
    return 0
  else
    if [ "$critical" = "true" ]; then
      echo -e "${RED}✗ FAIL${NC}"
      ALL_GOOD=false
    else
      echo -e "${YELLOW}⚠ WARNING${NC}"
    fi
    return 1
  fi
}

# =============================================================================
# 1. Kubectl Access
# =============================================================================
echo "1. Kubectl Access"
echo "------------------------------------------------------------------------"

check "kubeconfig exists" "test -f $KUBECONFIG" "true"
check "kubectl executable" "command -v kubectl" "true"
check "cluster connectivity" "kubectl --kubeconfig=$KUBECONFIG get node &>/dev/null" "true"
echo ""

# =============================================================================
# 2. Namespace Status
# =============================================================================
echo "2. Namespace Status"
echo "------------------------------------------------------------------------"

if kubectl --kubeconfig="$KUBECONFIG" get namespace "$NAMESPACE" &>/dev/null; then
  echo -e "${GREEN}✓ Namespace '$NAMESPACE' exists${NC}"

  # Check if namespace has resources
  RESOURCE_COUNT=$(kubectl --kubeconfig="$KUBECONFIG" get all -n "$NAMESPACE" 2>/dev/null | grep -v "No resources" | grep -c . || echo "0")
  if [ "$RESOURCE_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠ Namespace has $RESOURCE_COUNT resource(s) already deployed${NC}"
    echo "  Consider cleaning up before fresh deployment:"
    echo "  kubectl --kubeconfig=$KUBECONFIG delete all --all -n $NAMESPACE"
  else
    echo -e "${GREEN}✓ Namespace is empty (ready for deployment)${NC}"
  fi
else
  echo -e "${YELLOW}⚠ Namespace '$NAMESPACE' does not exist${NC}"
  echo "  It will be created during deployment (CreateNamespace=true)"
fi
echo ""

# =============================================================================
# 3. Required Permissions
# =============================================================================
echo "3. Required Permissions"
echo "------------------------------------------------------------------------"

check "can create deployments" "kubectl --kubeconfig=$KUBECONFIG auth can-i create deployment -n $NAMESPACE" "false"
check "can create services" "kubectl --kubeconfig=$KUBECONFIG auth can-i create service -n $NAMESPACE" "false"
check "can create configmaps" "kubectl --kubeconfig=$KUBECONFIG auth can-i create configmap -n $NAMESPACE" "false"
check "can create secrets" "kubectl --kubeconfig=$KUBECONFIG auth can-i create secret -n $NAMESPACE" "false"
check "can create rbac" "kubectl --kubeconfig=$KUBECONFIG auth can-i create rolebinding -n $NAMESPACE" "false"
echo ""

# =============================================================================
# 4. Secrets Check
# =============================================================================
echo "4. Secrets Check"
echo "------------------------------------------------------------------------"

if kubectl --kubeconfig="$KUBECONFIG" get namespace "$NAMESPACE" &>/dev/null; then
  if kubectl --kubeconfig="$KUBECONFIG" get secret botburrow-agents-secrets -n "$NAMESPACE" &>/dev/null; then
    echo -e "${GREEN}✓ Secret 'botburrow-agents-secrets' exists${NC}"
  else
    echo -e "${YELLOW}⚠ Secret 'botburrow-agents-secrets' not found${NC}"
    echo "  Apply placeholder secrets first:"
    echo "  kubectl --kubeconfig=$KUBECONFIG apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
  fi

  if kubectl --kubeconfig="$KUBECONFIG" get secret mcp-credentials -n "$NAMESPACE" &>/dev/null; then
    echo -e "${GREEN}✓ Secret 'mcp-credentials' exists${NC}"
  else
    echo -e "${YELLOW}⚠ Secret 'mcp-credentials' not found${NC}"
    echo "  Apply placeholder secrets first:"
    echo "  kubectl --kubeconfig=$KUBECONFIG apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
  fi
else
  echo -e "${YELLOW}⚠ Cannot check secrets (namespace doesn't exist yet)${NC}"
fi
echo ""

# =============================================================================
# 5. Manifest Files Check
# =============================================================================
echo "5. Manifest Files Check"
echo "------------------------------------------------------------------------"

MANIFESTS_DIR="k8s/apexalgo-iad"
REQUIRED_FILES=(
  "rbac.yaml"
  "configmap.yaml"
  "valkey.yaml"
  "runner-hybrid.yaml"
  "kustomization-minimal.yaml"
  "botburrow-agents-secrets-PLACEHOLDER.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
  check "manifest $file" "test -f $MANIFESTS_DIR/$file" "true"
done
echo ""

# =============================================================================
# 6. Image Availability Check
# =============================================================================
echo "6. Image Availability Check"
echo "------------------------------------------------------------------------"

# Extract image names from runner-hybrid.yaml
if [ -f "$MANIFESTS_DIR/runner-hybrid.yaml" ]; then
  RUNNER_IMAGE=$(grep -A 5 "name: runner" "$MANIFESTS_DIR/runner-hybrid.yaml" | grep "image:" | awk '{print $2}' || echo "")
  VALKEY_IMAGE=$(grep "image:" "$MANIFESTS_DIR/valkey.yaml" | head -1 | awk '{print $2}' || echo "")

  if [ -n "$RUNNER_IMAGE" ]; then
    echo -n "Runner image: $RUNNER_IMAGE... "
    # Just note the image, can't actually pull without docker
    echo -e "${GREEN}✓${NC} (manifest reference)"
  fi

  if [ -n "$VALKEY_IMAGE" ]; then
    echo -n "Valkey image: $VALKEY_IMAGE... "
    echo -e "${GREEN}✓${NC} (manifest reference)"
  fi
fi
echo ""

# =============================================================================
# 7. ArgoCD Status (informational)
# =============================================================================
echo "7. ArgoCD Status (Informational)"
echo "------------------------------------------------------------------------"

# Check if we can see ArgoCD application
if kubectl --kubeconfig="$KUBECONFIG" get application -n argocd "$NAMESPACE-ns-apexalgo-iad" &>/dev/null 2>&1; then
  echo -e "${YELLOW}⚠ ArgoCD application exists for $NAMESPACE${NC}"
  echo "  The simplified approach bypasses ArgoCD. Consider:"
  echo "  1. Delete the ArgoCD application if using kubectl deployment"
  echo "  2. Or investigate ArgoCD sync issues"
elif kubectl --kubeconfig="$KUBECONFIG" get applicationset -n argocd &>/dev/null 2>&1; then
  echo -e "${GREEN}✓ ArgoCD ApplicationSet exists (but no app for $NAMESPACE)${NC}"
else
  echo -e "${YELLOW}⚠ Cannot access ArgoCD (RBAC or ArgoCD not available)${NC}"
fi
echo ""

# =============================================================================
# Summary
# =============================================================================
echo "========================================================================"
if [ "$ALL_GOOD" = true ]; then
  echo -e "${GREEN}✓ All critical checks passed${NC}"
  echo ""
  echo "Next steps:"
  echo "1. Apply placeholder secrets:"
  echo "   kubectl --kubeconfig=$KUBECONFIG apply -f $MANIFESTS_DIR/botburrow-agents-secrets-PLACEHOLDER.yml"
  echo ""
  echo "2. Deploy minimal components:"
  echo "   kubectl --kubeconfig=$KUBECONFIG apply -k $MANIFESTS_DIR/ --kustomize=kustomization-minimal.yaml"
  echo ""
  echo "3. Verify deployment:"
  echo "   kubectl --kubeconfig=$KUBECONFIG get all -n $NAMESPACE"
  exit 0
else
  echo -e "${RED}✗ Some critical checks failed${NC}"
  echo ""
  echo "Please resolve the issues above before proceeding with deployment."
  echo ""
  echo "Common issues:"
  echo "- Missing kubeconfig: Set KUBECONFIG or use --kubeconfig option"
  echo "- Insufficient permissions: Use cluster-admin or namespace-admin context"
  echo "- Missing secrets: Apply botburrow-agents-secrets-PLACEHOLDER.yml first"
  exit 1
fi
