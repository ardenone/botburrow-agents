#!/bin/bash
# =============================================================================
# Simplified Deployment Verification Script
# =============================================================================
# Validates the minimal botburrow-agents deployment without ArgoCD dependency.
# This is the simplified scope alternative to bd-38r verification.
#
# Usage:
#   ./scripts/verify-simplified-deployment.sh [--namespace botburrow-agents]
#
# Requirements:
#   - kubectl configured for apexalgo-iad cluster
#   - Minimal deployment applied (kustomization-minimal.yaml)
#
# What's verified (simplified scope):
#   - Namespace exists
#   - Core deployments ready (valkey, runner-hybrid)
#   - Pods running
#   - Valkey connectivity
#   - Runner -> Valkey connectivity
#
# What's deferred (not checked here):
#   - ArgoCD sync (not used in minimal deployment)
#   - Coordinator leader election (not in minimal stack)
#   - R2 connectivity (requires real credentials)
#   - Hub API connectivity (requires real credentials)
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${1:-botburrow-agents}"
KUBECONFIG="${KUBECONFIG:-/home/coder/.kube/apexalgo-iad.kubeconfig}"
EXIT_CODE=0

# Info functions
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
success() { echo -e "${GREEN}  ✓${NC} $1"; }
failure() { echo -e "${RED}  ✗${NC} $1"; }

# Function to check resource exists
check_resource() {
    local resource_type="$1"
    local resource_name="$2"
    local namespace="$3"

    if kubectl get "$resource_type" "$resource_name" -n "$namespace" &>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to check deployment readiness
check_deployment_ready() {
    local deployment="$1"
    local namespace="$2"

    local ready=$(kubectl get deployment "$deployment" -n "$namespace" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired=$(kubectl get deployment "$deployment" -n "$namespace" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")

    if [ "$ready" == "$desired" ] && [ "$ready" != "0" ]; then
        success "Deployment $deployment ready ($ready/$desired replicas)"
        return 0
    else
        failure "Deployment $deployment not ready ($ready/$desired replicas)"
        return 1
    fi
}

# Function to check pod status
check_pods_running() {
    local label="$1"
    local namespace="$2"
    local component_name="$3"

    local pods=$(kubectl get pods -n "$namespace" -l "$label" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)
    local count=0
    local ready_count=0

    if [ -z "$pods" ]; then
        failure "No $component_name pods found"
        return 1
    fi

    for pod in $pods; do
        count=$((count + 1))
        local ready=$(kubectl get pod "$pod" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
        if [ "$ready" == "True" ]; then
            ready_count=$((ready_count + 1))
        fi
    done

    if [ "$ready_count" -eq "$count" ]; then
        success "$component_name pods: $ready_count/$count ready"
        return 0
    else
        failure "$component_name pods: $ready_count/$count ready"
        return 1
    fi
}

# Main verification
main() {
    echo "=========================================="
    info "Simplified Deployment Verification"
    echo "Namespace: $NAMESPACE"
    echo "Cluster: apexalgo-iad"
    echo "=========================================="
    echo

    # Check 1: Namespace exists
    info "1. Checking namespace..."
    if kubectl get namespace "$NAMESPACE" &>/dev/null; then
        success "Namespace $NAMESPACE exists"
    else
        failure "Namespace $NAMESPACE NOT found"
        error "  Create with: kubectl create namespace $NAMESPACE"
        EXIT_CODE=1
    fi
    echo

    # Check 2: Namespace has resources
    info "2. Checking namespace has resources..."
    local resource_count
    resource_count=$(kubectl get all -n "$NAMESPACE" -o json 2>/dev/null | jq '.items | length' 2>/dev/null || echo "0")
    resource_count=$(echo "$resource_count" | tr -d '[:space:]')
    if [ "$resource_count" -gt 0 ] 2>/dev/null; then
        success "Namespace has $resource_count resources"
    else
        failure "Namespace is empty (0 resources)"
        error "  Deploy minimal stack: kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml"
        EXIT_CODE=1
    fi
    echo

    # Only continue if namespace has resources
    if [ "${resource_count:-0}" -eq 0 ] 2>/dev/null; then
        echo "=========================================="
        error "Verification failed: Namespace empty"
        echo "=========================================="
        exit 1
    fi

    # Check 3: Core deployments exist and are ready
    info "3. Checking core deployments..."
    for deployment in valkey runner-hybrid; do
        if check_resource "deployment" "$deployment" "$NAMESPACE"; then
            check_deployment_ready "$deployment" "$NAMESPACE" || EXIT_CODE=1
        else
            failure "Deployment $deployment NOT found"
            EXIT_CODE=1
        fi
    done
    echo

    # Check 4: Pods are running
    info "4. Checking pod status..."
    check_pods_running "app=valkey" "$NAMESPACE" "Valkey" || EXIT_CODE=1
    check_pods_running "app.kubernetes.io/name=runner-hybrid" "$NAMESPACE" "Runner-Hybrid" || EXIT_CODE=1
    echo

    # Check 5: Services exist
    info "5. Checking services..."
    for service in valkey; do
        if check_resource "service" "$service" "$NAMESPACE"; then
            success "Service $service exists"
        else
            failure "Service $service NOT found"
            EXIT_CODE=1
        fi
    done
    echo

    # Check 6: ConfigMaps exist
    info "6. Checking ConfigMaps..."
    local configmaps_found=0
    for cm in botburrow-agents-config agent-definitions-repos agent-permissions; do
        if check_resource "configmap" "$cm" "$NAMESPACE"; then
            configmaps_found=$((configmaps_found + 1))
        fi
    done
    if [ "$configmaps_found" -eq 3 ]; then
        success "All ConfigMaps present (3/3)"
    else
        warn "Some ConfigMaps missing ($configmaps_found/3)"
    fi
    echo

    # Check 7: Valkey connectivity
    info "7. Checking Valkey connectivity..."
    local valkey_pod
    valkey_pod=$(kubectl get pods -n "$NAMESPACE" -l app=valkey -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -n "$valkey_pod" ]; then
        if kubectl exec -n "$NAMESPACE" "$valkey_pod" -- redis-cli ping &>/dev/null; then
            success "Valkey responding to PING"
        else
            failure "Valkey not responding to PING"
            EXIT_CODE=1
        fi
    else
        warn "Cannot test Valkey (no pod found)"
    fi
    echo

    # Check 8: Runner -> Valkey connectivity
    info "8. Checking Runner -> Valkey connectivity..."
    local runner_pod
    runner_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=runner-hybrid -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -n "$runner_pod" ]; then
        if kubectl exec -n "$NAMESPACE" "$runner_pod" -- nc -z -w5 valkey 6379 &>/dev/null; then
            success "Runner can reach Valkey:6379"
        else
            failure "Runner cannot reach Valkey:6379"
            EXIT_CODE=1
        fi
    else
        warn "Cannot test connectivity (no runner pod found)"
    fi
    echo

    # Summary
    echo "=========================================="
    if [ $EXIT_CODE -eq 0 ]; then
        info "✓ All checks passed!"
        info "Simplified deployment is healthy."
        echo
        info "Next steps:"
        info "  1. Populate real secrets (replace placeholders)"
        info "  2. Test agent execution"
        info "  3. Scale runners if needed"
    else
        error "✗ Some checks failed"
        echo
        info "Common fixes:"
        info "  - Apply secrets: kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
        info "  - Deploy stack: kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml"
        info "  - Check logs: kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=runner-hybrid --tail=50"
    fi
    echo "=========================================="

    exit $EXIT_CODE
}

# Run main function
main "$@"
