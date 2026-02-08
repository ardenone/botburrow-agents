#!/bin/bash
# GitOps Deployment Verification Script for botburrow-agents
#
# This script verifies that the GitOps deployment was successful
# by checking pod status, health endpoints, and connectivity.
#
# Usage:
#   ./scripts/verify-gitops-deployment.sh [--namespace botburrow-agents] [--cluster apexalgo-iad]
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#   2 - Usage error

set -euo pipefail

# Default values
NAMESPACE="${NAMESPACE:-botburrow-agents}"
CLUSTER="${CLUSTER:-apexalgo-iad}"
VERBOSE="${VERBOSE:-0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_debug() {
    if [ "$VERBOSE" -ge 1 ]; then
        echo -e "[DEBUG] $*"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace|-n)
            NAMESPACE="$2"
            shift 2
            ;;
        --cluster|-c)
            CLUSTER="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--namespace NAMESPACE] [--cluster CLUSTER] [--verbose]"
            echo ""
            echo "Options:"
            echo "  -n, --namespace NAMESPACE  Kubernetes namespace (default: botburrow-agents)"
            echo "  -c, --cluster CLUSTER      Cluster name (default: apexalgo-iad)"
            echo "  -v, --verbose              Enable verbose output"
            echo "  -h, --help                 Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 2
            ;;
    esac
done

# Verify kubectl is available
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Verify we can access the cluster
log_info "Verifying cluster access to $CLUSTER..."
if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot access cluster $CLUSTER"
    exit 1
fi
log_info "Cluster access verified"

# Check namespace exists
log_info "Checking namespace $NAMESPACE..."
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    log_error "Namespace $NAMESPACE does not exist"
    exit 1
fi
log_info "Namespace $NAMESPACE exists"

# Track overall status
ALL_CHECKS_PASSED=true

# Function to check pod status
check_pods() {
    log_info "Checking pod status..."

    # Get all pods
    local pods
    pods=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')

    if [ -z "$pods" ]; then
        log_error "No pods found in namespace $NAMESPACE"
        ALL_CHECKS_PASSED=false
        return 1
    fi

    # Check each pod
    local failed_pods=0
    for pod in $pods; do
        local phase
        phase=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.phase}')

        local ready
        ready=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')

        log_debug "Pod $pod: phase=$phase, ready=$ready"

        if [ "$phase" != "Running" ] || [ "$ready" != "True" ]; then
            log_error "Pod $pod is not healthy (phase=$phase, ready=$ready)"
            failed_pods=$((failed_pods + 1))
            ALL_CHECKS_PASSED=false
        else
            log_info "Pod $pod is healthy"
        fi
    done

    if [ $failed_pods -eq 0 ]; then
        log_info "All pods are healthy"
    else
        log_error "$failed_pods pod(s) are not healthy"
    fi

    # Display pod status
    log_debug "Pod status:"
    kubectl get pods -n "$NAMESPACE"
}

# Function to check deployments
check_deployments() {
    log_info "Checking deployment status..."

    local deployments
    deployments=$(kubectl get deployments -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')

    if [ -z "$deployments" ]; then
        log_warn "No deployments found in namespace $NAMESPACE"
        return 0
    fi

    local failed_deployments=0
    for deployment in $deployments; do
        local ready
        ready=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')

        local desired
        desired=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')

        log_debug "Deployment $deployment: ready=$ready, desired=$desired"

        if [ "$ready" != "$desired" ]; then
            log_error "Deployment $deployment is not ready (ready=$ready, desired=$desired)"
            failed_deployments=$((failed_deployments + 1))
            ALL_CHECKS_PASSED=false
        else
            log_info "Deployment $deployment is ready"
        fi
    done

    if [ $failed_deployments -eq 0 ]; then
        log_info "All deployments are ready"
    else
        log_error "$failed_deployments deployment(s) are not ready"
    fi
}

# Function to check health endpoints
check_health_endpoints() {
    log_info "Checking health endpoints..."

    # Check coordinator health
    local coordinator_pod
    coordinator_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=coordinator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

    if [ -n "$coordinator_pod" ]; then
        log_debug "Checking coordinator health endpoint..."

        if kubectl exec -n "$NAMESPACE" "$coordinator_pod" -- curl -s http://localhost:9090/health &> /dev/null; then
            log_info "Coordinator health endpoint is responding"
        else
            log_error "Coordinator health endpoint is not responding"
            ALL_CHECKS_PASSED=false
        fi
    else
        log_warn "No coordinator pod found"
    fi

    # Check runner health
    local runner_pod
    runner_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=runner -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

    if [ -n "$runner_pod" ]; then
        log_debug "Checking runner health endpoint..."

        if kubectl exec -n "$NAMESPACE" "$runner_pod" -- curl -s http://localhost:9091/health &> /dev/null; then
            log_info "Runner health endpoint is responding"
        else
            log_error "Runner health endpoint is not responding"
            ALL_CHECKS_PASSED=false
        fi
    else
        log_warn "No runner pod found"
    fi
}

# Function to check Valkey connectivity
check_valkey() {
    log_info "Checking Valkey connectivity..."

    local valkey_pod
    valkey_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=valkey -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

    if [ -n "$valkey_pod" ]; then
        log_debug "Pinging Valkey..."

        if kubectl exec -n "$NAMESPACE" "$valkey_pod" -- redis-cli ping | grep -q PONG; then
            log_info "Valkey is responding"
        else
            log_error "Valkey is not responding"
            ALL_CHECKS_PASSED=false
        fi
    else
        log_warn "No Valkey pod found"
    fi
}

# Function to check HPA status
check_hpa() {
    log_info "Checking HPA status..."

    local hpa_exists
    hpa_exists=$(kubectl get hpa -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)

    if [ -n "$hpa_exists" ]; then
        log_debug "HPA resources found"
        kubectl get hpa -n "$NAMESPACE"
    else
        log_debug "No HPA resources found"
    fi
}

# Function to check recent logs for errors
check_logs_for_errors() {
    log_info "Checking recent logs for errors..."

    local pods
    pods=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')

    local error_count=0
    for pod in $pods; do
        log_debug "Checking logs for pod $pod..."

        # Check last 50 lines for ERROR or CRITICAL
        local errors
        errors=$(kubectl logs --tail=50 -n "$NAMESPACE" "$pod" 2>&1 | grep -iE "(ERROR|CRITICAL|Traceback)" || true)

        if [ -n "$errors" ]; then
            log_warn "Found errors in logs for pod $pod:"
            echo "$errors" | head -5
            error_count=$((error_count + 1))
        fi
    done

    if [ $error_count -eq 0 ]; then
        log_info "No errors found in recent logs"
    else
        log_warn "Errors found in $error_count pod(s)"
    fi
}

# Main verification flow
main() {
    log_info "Starting GitOps deployment verification..."
    log_info "Namespace: $NAMESPACE"
    log_info "Cluster: $CLUSTER"
    echo ""

    check_pods
    check_deployments
    check_health_endpoints
    check_valkey
    check_hpa
    check_logs_for_errors

    echo ""
    log_info "Verification complete"

    if [ "$ALL_CHECKS_PASSED" = true ]; then
        log_info "✓ All checks passed"
        exit 0
    else
        log_error "✗ Some checks failed"
        exit 1
    fi
}

# Run main function
main "$@"
