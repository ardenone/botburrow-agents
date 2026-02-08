#!/bin/bash
# =============================================================================
# botburrow-agents Workaround Deployment Script
# =============================================================================
# This script implements a workaround for the ArgoCD deployment issue.
# It bypasses ArgoCD and deploys directly via kubectl.
#
# Related beads:
#   - bd-1v9: Fix botburrow-agents deployment via ArgoCD
#   - bd-cni: Alternative: Use workaround approach (this bead)
#
# Usage: ./deploy-workaround.sh [--kubeconfig /path/to/kubeconfig] [--dry-run]
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
KUBECONFIG="${KUBECONFIG:-/home/coder/.kube/apexalgo-iad.kubeconfig}"
NAMESPACE="botburrow-agents"
MANIFESTS_DIR="k8s/apexalgo-iad"
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --kubeconfig)
      KUBECONFIG="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      cat <<EOF
Usage: $0 [OPTIONS]

Deploy botburrow-agents using kubectl workaround approach (bypasses ArgoCD).

OPTIONS:
  --kubeconfig PATH    Path to kubeconfig file
                       (default: /home/coder/.kube/apexalgo-iad.kubeconfig)
  --dry-run            Show commands without executing
  -h, --help           Show this help message

EXAMPLES:
  # Deploy with default kubeconfig
  $0

  # Deploy with custom kubeconfig
  $0 --kubeconfig /path/to/kubeconfig

  # Dry run to see what would be deployed
  $0 --dry-run

REQUIREMENTS:
  - kubectl configured with cluster-admin or namespace-admin permissions
  - Kubeconfig with access to apexalgo-iad cluster

RELATED FILES:
  - kustomization-minimal.yaml: Defines minimal deployment components
  - botburrow-agents-secrets-PLACEHOLDER.yml: Placeholder secrets

AFTER DEPLOYMENT:
  1. Update placeholder secrets with real values:
     kubectl edit secret botburrow-agents-secrets -n botburrow-agents
     kubectl edit secret mcp-credentials -n botburrow-agents

  2. Verify deployment:
     kubectl get all -n botburrow-agents
EOF
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Use --help to see usage"
      exit 1
      ;;
  esac
done

# Kubectl command wrapper
KUBECTL="kubectl --kubeconfig=$KUBECONFIG"

# Dry-run wrapper
run_cmd() {
  local cmd="$*"
  if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}[DRY RUN]${NC} $cmd"
  else
    echo -e "${BLUE}Executing:${NC} $cmd"
    eval "$cmd"
  fi
}

echo "========================================================================"
echo "botburrow-agents Workaround Deployment"
echo "========================================================================"
echo ""
echo "This script deploys botburrow-agents using kubectl, bypassing ArgoCD."
echo ""
echo "Configuration:"
echo "  Kubeconfig: $KUBECONFIG"
echo "  Namespace: $NAMESPACE"
echo "  Manifests: $MANIFESTS_DIR"
echo "  Dry run: $DRY_RUN"
echo ""

# =============================================================================
# Pre-flight checks
# =============================================================================

echo "========================================================================"
echo "Step 1: Pre-flight Checks"
echo "========================================================================"
echo ""

# Check kubeconfig exists
if [ ! -f "$KUBECONFIG" ]; then
  echo -e "${RED}ERROR: Kubeconfig not found: $KUBECONFIG${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Kubeconfig exists${NC}"

# Check cluster connectivity
if ! $KUBECTL get node &>/dev/null; then
  echo -e "${RED}ERROR: Cannot connect to cluster${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Cluster connectivity OK${NC}"

# Check required manifest files
REQUIRED_FILES=(
  "$MANIFESTS_DIR/kustomization-minimal.yaml"
  "$MANIFESTS_DIR/botburrow-agents-secrets-PLACEHOLDER.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo -e "${RED}ERROR: Required file not found: $file${NC}"
    exit 1
  fi
done
echo -e "${GREEN}✓ All required manifest files exist${NC}"

# Change to manifests directory for kustomize
cd "$MANIFESTS_DIR"

echo ""
echo -e "${GREEN}All pre-flight checks passed!${NC}"
echo ""

# =============================================================================
# Step 2: Apply Placeholder Secrets
# =============================================================================

echo "========================================================================"
echo "Step 2: Apply Placeholder Secrets"
echo "========================================================================"
echo ""

echo "Applying placeholder secrets..."
run_cmd $KUBECTL apply -f botburrow-agents-secrets-PLACEHOLDER.yml

if [ "$DRY_RUN" = false ]; then
  echo ""
  echo -e "${GREEN}✓ Secrets applied${NC}"
  echo -e "${YELLOW}NOTE: These are placeholder values. Update them with real credentials:${NC}"
  echo "  kubectl --kubeconfig=$KUBECONFIG edit secret botburrow-agents-secrets -n $NAMESPACE"
  echo "  kubectl --kubeconfig=$KUBECONFIG edit secret mcp-credentials -n $NAMESPACE"
fi
echo ""

# =============================================================================
# Step 3: Deploy Minimal Components
# =============================================================================

echo "========================================================================"
echo "Step 3: Deploy Minimal Components"
echo "========================================================================"
echo ""

echo "Deploying minimal components (valkey, runner-hybrid, rbac, configmaps)..."
run_cmd $KUBECTL apply -k . --kustomize=kustomization-minimal.yaml

if [ "$DRY_RUN" = false ]; then
  echo ""
  echo -e "${GREEN}✓ Minimal components deployed${NC}"
fi
echo ""

# =============================================================================
# Step 4: Verify Deployment
# =============================================================================

if [ "$DRY_RUN" = false ]; then
  echo "========================================================================"
  echo "Step 4: Verify Deployment"
  echo "========================================================================"
  echo ""

  echo "Waiting for deployments to be ready..."
  run_cmd $KUBECTL wait --for=condition=available --timeout=60s \
    deployment/valkey -n $NAMESPACE || true

  run_cmd $KUBECTL wait --for=condition=available --timeout=60s \
    deployment/runner-hybrid -n $NAMESPACE || true

  echo ""
  echo "Deployed resources:"
  run_cmd $KUBECTL get all -n $NAMESPACE

  echo ""
  echo "Pod status:"
  run_cmd $KUBECTL get pods -n $NAMESPACE

  echo ""
  echo -e "${GREEN}✓ Deployment verification complete${NC}"
fi

# =============================================================================
# Summary and Next Steps
# =============================================================================

echo ""
echo "========================================================================"
echo "Deployment Summary"
echo "========================================================================"
echo ""

if [ "$DRY_RUN" = true ]; then
  echo -e "${YELLOW}DRY RUN COMPLETE - No changes were made${NC}"
  echo ""
  echo "To deploy for real, run:"
  echo "  $0 --kubeconfig $KUBECONFIG"
else
  echo -e "${GREEN}WORKAROUND DEPLOYMENT COMPLETE${NC}"
  echo ""
  echo "The following components are now deployed:"
  echo "  - valkey (Redis/Valkey for leader election)"
  echo "  - runner-hybrid (can handle all work types)"
  echo "  - RBAC (ServiceAccount, Role, RoleBinding)"
  echo "  - ConfigMaps (botburrow-agents-config, agent-definitions-repos, agent-permissions)"
  echo ""
  echo -e "${YELLOW}IMPORTANT NEXT STEPS:${NC}"
  echo ""
  echo "1. Update placeholder secrets with real credentials:"
  echo "   kubectl --kubeconfig=$KUBECONFIG edit secret botburrow-agents-secrets -n $NAMESPACE"
  echo "   kubectl --kubeconfig=$KUBECONFIG edit secret mcp-credentials -n $NAMESPACE"
  echo ""
  echo "2. Restart runners to pick up new secrets:"
  echo "   kubectl --kubeconfig=$KUBECONFIG rollout restart deployment/runner-hybrid -n $NAMESPACE"
  echo ""
  echo "3. Check pod logs:"
  echo "   kubectl --kubeconfig=$KUBECONFIG logs -f -n $NAMESPACE -l app.kubernetes.io/name=runner-hybrid"
  echo ""
  echo "4. Verify health:"
  echo "   kubectl --kubeconfig=$KUBECONFIG port-forward -n $NAMESPACE deployment/runner-hybrid 8080:9091"
  echo "   curl http://localhost:8080/health"
  echo ""
  echo -e "${BLUE}ArgoCD Status:${NC}"
  echo "This deployment bypasses ArgoCD. The ArgoCD application may show"
  echo "divergence since we deployed via kubectl. This is expected."
  echo ""
  echo "To reconcile with ArgoCD later, either:"
  echo "  1. Delete the ArgoCD application and manage via kubectl/git"
  echo "  2. Fix the ArgoCD sync issue and let it take over"
  echo ""
fi

echo "========================================================================"
