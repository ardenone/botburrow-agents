#!/usr/bin/env bash
# =============================================================================
# ARGOCD INSTALLATION SCRIPT
# =============================================================================
#
# This script installs ArgoCD in the apexalgo-iad cluster and configures
# the ApplicationSet for botburrow-agents GitOps deployment.
#
# USAGE:
#   ./install.sh [options]
#
# OPTIONS:
#   --skip-ingress    Skip IngressRoute creation
#   --dry-run         Show what would be done without executing
#   --help            Show this help message
#
# PREREQUISITES:
#   - kubectl configured for apexalgo-iad cluster
#   - Cluster-admin permissions
#   - Internet access to download ArgoCD manifests
#
# =============================================================================

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ARGOCD_VERSION="stable"
ARGOCD_NAMESPACE="argocd"
ARGOCD_MANIFEST_URL="https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
SKIP_INGRESS=false
DRY_RUN=false

# =============================================================================
# FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl first."
        exit 1
    fi

    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot access cluster. Please configure kubectl for apexalgo-iad."
        exit 1
    fi

    # Check for cluster-admin permissions
    log_info "Checking for cluster-admin permissions..."
    if ! kubectl auth can-i create namespaces &> /dev/null; then
        log_error "Insufficient permissions. Cluster-admin access required."
        log_error "Current permissions:"
        kubectl auth can-i --list 2>&1 | grep -E "(namespaces|crd|clusterrole)" || true
        exit 1
    fi

    log_info "Prerequisites check passed."
}

install_argocd() {
    log_info "Installing ArgoCD ${ARGOCD_VERSION}..."

    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Would create namespace ${ARGOCD_NAMESPACE}"
        log_warn "DRY RUN: Would apply ArgoCD manifest from ${ARGOCD_MANIFEST_URL}"
        return
    fi

    # Create namespace
    if kubectl get namespace "${ARGOCD_NAMESPACE}" &> /dev/null; then
        log_warn "Namespace ${ARGOCD_NAMESPACE} already exists. Skipping creation."
    else
        log_info "Creating namespace ${ARGOCD_NAMESPACE}..."
        kubectl create namespace "${ARGOCD_NAMESPACE}"
    fi

    # Download and apply ArgoCD manifest
    log_info "Downloading ArgoCD manifest..."
    local manifest_file="/tmp/argocd-install-${ARGOCD_VERSION}.yaml"

    if [ ! -f "$manifest_file" ]; then
        curl -sSL -o "$manifest_file" "${ARGOCD_MANIFEST_URL}"
    fi

    log_info "Applying ArgoCD manifest..."
    kubectl apply -n "${ARGOCD_NAMESPACE}" -f "$manifest_file"

    log_info "Waiting for ArgoCD pods to be ready..."
    kubectl wait --for=condition=ready pod \
        -l app.kubernetes.io/part-of=argocd \
        -n "${ARGOCD_NAMESPACE}" \
        --timeout=300s

    log_info "ArgoCD installed successfully."
}

verify_installation() {
    log_info "Verifying ArgoCD installation..."

    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Would verify ArgoCD installation"
        return
    fi

    # Check pods
    log_info "Checking ArgoCD pods..."
    kubectl get pods -n "${ARGOCD_NAMESPACE}"

    # Check deployments
    log_info "Checking ArgoCD deployments..."
    kubectl get deployments -n "${ARGOCD_NAMESPACE}"

    # Check CRDs
    log_info "Checking ArgoCD CRDs..."
    local crd_count
    crd_count=$(kubectl get crd | grep -c "argoproj.io" || true)
    log_info "Found ${crd_count} ArgoCD CRDs."

    # Get initial admin password
    log_info "Retrieving initial admin password..."
    if kubectl get secret argocd-initial-admin-secret -n "${ARGOCD_NAMESPACE}" &> /dev/null; then
        local password
        password=$(kubectl get secret argocd-initial-admin-secret -n "${ARGOCD_NAMESPACE}" \
            -o jsonpath='{.data.password}' | base64 -d)
        log_info "Initial admin password: ${password}"
        log_warn "IMPORTANT: Change this password after first login!"
    else
        log_warn "Initial admin secret not found. It may still be creating."
    fi

    log_info "Verification complete."
}

configure_applicationset() {
    log_info "Configuring ApplicationSet for botburrow-agents..."

    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Would apply ApplicationSet manifest"
        return
    fi

    local applicationset_manifest="${SCRIPT_DIR}/applicationset.yaml"

    if [ ! -f "$applicationset_manifest" ]; then
        log_error "ApplicationSet manifest not found: ${applicationset_manifest}"
        exit 1
    fi

    log_info "Applying ApplicationSet manifest..."
    kubectl apply -f "$applicationset_manifest"

    log_info "Waiting for ApplicationSet to be processed..."
    sleep 5

    log_info "Checking ApplicationSet..."
    kubectl get applicationset -n "${ARGOCD_NAMESPACE}"

    log_info "Checking generated Application..."
    kubectl get application -n "${ARGOCD_NAMESPACE}"

    log_info "ApplicationSet configured successfully."
}

configure_ingress() {
    if [ "$SKIP_INGRESS" = true ]; then
        log_info "Skipping IngressRoute configuration (--skip-ingress flag set)."
        return
    fi

    log_info "Configuring IngressRoute for external access..."

    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Would apply IngressRoute manifest"
        return
    fi

    local ingress_manifest="${SCRIPT_DIR}/ingress.yaml"

    if [ ! -f "$ingress_manifest" ]; then
        log_warn "IngressRoute manifest not found: ${ingress_manifest}"
        log_warn "Skipping IngressRoute configuration."
        return
    fi

    log_info "Applying IngressRoute manifest..."
    kubectl apply -f "$ingress_manifest"

    log_info "IngressRoute configured successfully."
    log_info "ArgoCD UI will be available at: https://argocd.apexalgo.ardenone.com"
    log_warn "Make sure DNS is configured for this hostname."
}

print_summary() {
    log_info "=================================="
    log_info "Installation Summary"
    log_info "=================================="
    log_info ""
    log_info "ArgoCD Namespace: ${ARGOCD_NAMESPACE}"
    log_info "ArgoCD Version: ${ARGOCD_VERSION}"
    log_info ""
    log_info "Access ArgoCD UI:"
    log_info "  Port-forward: kubectl port-forward svc/argocd-server -n ${ARGOCD_NAMESPACE} 8080:443"
    log_info "  Then open: https://localhost:8080"
    log_info ""
    log_info "  External (if IngressRoute configured): https://argocd.apexalgo.ardenone.com"
    log_info ""
    log_info "Initial credentials:"
    log_info "  Username: admin"
    log_info "  Password: (see above or run: kubectl get secret argocd-initial-admin-secret -n ${ARGOCD_NAMESPACE} -o jsonpath='{.data.password}' | base64 -d)"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Login to ArgoCD UI"
    log_info "  2. Change admin password"
    log_info "  3. Verify botburrow-agents Application is syncing"
    log_info "  4. Check ApplicationSet status"
    log_info ""
    log_info "Useful commands:"
    log_info "  kubectl get pods -n ${ARGOCD_NAMESPACE}"
    log_info "  kubectl get application -n ${ARGOCD_NAMESPACE}"
    log_info "  kubectl get applicationset -n ${ARGOCD_NAMESPACE}"
    log_info ""
    log_info "For CLI access:"
    log_info "  argocd login localhost:8080 --insecure --username admin --password <password>"
    log_info "  argocd app list"
    log_info "  argocd app get botburrow-agents"
    log_info ""
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    log_info "ArgoCD Installation Script for botburrow-agents"
    log_info "================================================"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-ingress)
                SKIP_INGRESS=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo ""
                echo "Options:"
                echo "  --skip-ingress    Skip IngressRoute creation"
                echo "  --dry-run         Show what would be done without executing"
                echo "  --help            Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN MODE: No changes will be made"
    fi

    check_prerequisites
    install_argocd
    verify_installation
    configure_applicationset
    configure_ingress
    print_summary

    log_info "Installation complete!"
}

# Run main function
main "$@"
