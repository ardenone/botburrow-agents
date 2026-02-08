#!/usr/bin/env bash
# =============================================================================
# CREATE SEALEDSECRET FOR BOTBURROW AGENTS
# =============================================================================
#
# This script creates a SealedSecret from real credential values.
# Run this after obtaining all required credentials.
#
# PREREQUISITES:
#   1. kubeseal CLI installed (check: which kubeseal)
#   2. All credential values gathered (see SECRET_CREDENTIALS.md)
#   3. Access to apexalgo-iad cluster
#
# USAGE:
#   # Step 1: Fill in real values in the temp file
#   cp botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
#   vi /tmp/botburrow-agents-secret.yml  # Edit with real values
#
#   # Step 2: Run this script
#   ./create-sealedsecret.sh
#
#   # Step 3: Add to git and push
#   git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
#   git commit -m "feat: add SealedSecret for botburrow-agents"
#   git push
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEMPLATE_FILE="$PROJECT_ROOT/k8s/apexalgo-iad/botburrow-agents-secret.yml.template"
TEMP_SECRET="/tmp/botburrow-agents-secret.yml"
OUTPUT_FILE="$PROJECT_ROOT/k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check kubeseal
    if ! command -v kubeseal &> /dev/null; then
        log_error "kubeseal not found. Install from: https://github.com/bitnami-labs/sealed-secrets"
        exit 1
    fi
    log_info "✓ kubeseal found: $(which kubeseal)"

    # Check template file exists
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        log_error "Template file not found: $TEMPLATE_FILE"
        exit 1
    fi
    log_info "✓ Template file found"

    # Check if temp secret exists
    if [[ ! -f "$TEMP_SECRET" ]]; then
        log_error "Temp secret file not found: $TEMP_SECRET"
        log_info ""
        log_info "Please create it first:"
        log_info "  cp $TEMPLATE_FILE $TEMP_SECRET"
        log_info "  vi $TEMP_SECRET  # Fill in all REPLACE_* values"
        exit 1
    fi
    log_info "✓ Temp secret file found"

    # Check for placeholder values
    if grep -q "REPLACE_" "$TEMP_SECRET"; then
        log_warn "Found placeholder values in $TEMP_SECRET"
        log_info ""
        log_info "Please edit $TEMP_SECRET and replace all placeholder values:"
        grep "REPLACE_" "$TEMP_SECRET" | sed 's/^/  - /'
        log_info ""
        log_info "After editing, run this script again."
        exit 1
    fi
    log_info "✓ No placeholder values found"
}

# Get SealedSecret controller info
get_controller_info() {
    log_info "Detecting SealedSecret controller..."

    # Try to get controller info from local cluster config
    local controller_namespace="sealed-secrets"
    local controller_name="sealed-secrets"

    # Check if we can access the cluster
    if KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig kubectl get sealedsecrets -n "$controller_namespace" &> /dev/null 2>&1; then
        log_info "✓ SealedSecret controller found in namespace: $controller_namespace"
        echo "--controller-namespace=$controller_namespace"
        echo "--controller-name=$controller_name"
    else
        log_warn "Could not detect SealedSecret controller in cluster"
        log_info "Will use default controller namespace: sealed-secrets"
        echo "--controller-namespace=sealed-secrets"
        echo "--controller-name=sealed-secrets"
    fi
}

# Create SealedSecret
create_sealedsecret() {
    log_info "Creating SealedSecret..."

    local controller_args=($(get_controller_info))

    if kubeseal --format=yaml "${controller_args[@]}" < "$TEMP_SECRET" > "$OUTPUT_FILE"; then
        log_info "✓ SealedSecret created: $OUTPUT_FILE"
    else
        log_error "Failed to create SealedSecret"
        log_info ""
        log_info "Try running kubeseal manually:"
        log_info "  kubeseal --format=yaml ${controller_args[*]} < $TEMP_SECRET > $OUTPUT_FILE"
        exit 1
    fi
}

# Verify output
verify_output() {
    log_info "Verifying SealedSecret..."

    if [[ ! -f "$OUTPUT_FILE" ]]; then
        log_error "Output file not created: $OUTPUT_FILE"
        exit 1
    fi

    # Check if it's a valid SealedSecret
    if ! grep -q "kind: SealedSecret" "$OUTPUT_FILE"; then
        log_error "Output file is not a valid SealedSecret"
        exit 1
    fi

    # Check for encrypted data
    if ! grep -q "encryptedData:" "$OUTPUT_FILE"; then
        log_error "SealedSecret does not contain encrypted data"
        exit 1
    fi

    log_info "✓ SealedSecret is valid"

    # Show stats
    local secret_count=$(grep -c "kind: Secret" "$TEMP_SECRET")
    log_info "✓ Sealed $secret_count secret(s)"

    # Clean up temp file
    log_info ""
    log_warn "IMPORTANT: Delete the temp secret file with plaintext values:"
    log_info "  rm $TEMP_SECRET"
}

# Print next steps
print_next_steps() {
    log_info ""
    log_info "Next steps:"
    log_info ""
    log_info "1. Review the SealedSecret:"
    log_info "   cat $OUTPUT_FILE"
    log_info ""
    log_info "2. Add to kustomization.yaml if not already present:"
    log_info "   echo '- botburrow-agents-sealedsecret.yml' >> $PROJECT_ROOT/k8s/apexalgo-iad/kustomization-full.yaml"
    log_info ""
    log_info "3. Commit and push to Git:"
    log_info "   cd $PROJECT_ROOT"
    log_info "   git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml"
    log_info "   git commit -m 'feat: add SealedSecret for botburrow-agents'"
    log_info "   git push"
    log_info ""
    log_info "4. Apply to cluster (if using ArgoCD, it will sync automatically):"
    log_info "   kubectl apply -k $PROJECT_ROOT/k8s/apexalgo-iad/"
    log_info ""
}

# Main execution
main() {
    log_info "=== Botburrow Agents SealedSecret Creation ==="
    log_info ""

    check_prerequisites
    create_sealedsecret
    verify_output
    print_next_steps

    log_info "${GREEN}Done!${NC}"
}

main "$@"
