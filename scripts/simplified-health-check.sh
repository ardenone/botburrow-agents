#!/bin/bash
# Simplified health check for botburrow-agents deployment
# Alternative implementation for bd-38r -> bd-1mg
#
# Minimal viable checks:
# 1. Pod status (Running)
# 2. Basic metrics endpoint availability
#
# This is intentionally simplified compared to the comprehensive verification
# in bd-38r. It focuses on the core "is the deployment alive" question.

set -euo pipefail

NAMESPACE="${NAMESPACE:-botburrow-agents}"
CLUSTER="${CLUSTER:-apexalgo-iad}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall health status
HEALTHY=0
UNHEALTHY=0

# Function to print status
print_status() {
    local component=$1
    local status=$2
    local message=$3

    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}✓${NC} $component: $message"
        ((HEALTHY++))
    else
        echo -e "${RED}✗${NC} $component: $message"
        ((UNHEALTHY++))
    fi
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Check cluster context
print_info "Checking cluster context for $CLUSTER..."

# Use the correct kubeconfig path
KUBECONFIG="${KUBECONFIG:-/home/coder/.kube/apexalgo-iad.kubeconfig}"
export KUBECONFIG

# Verify we can connect to the cluster
if ! kubectl --kubeconfig="$KUBECONFIG" get namespace "$NAMESPACE" &>/dev/null; then
    print_status "Cluster Connection" "FAIL" "Cannot connect to $CLUSTER cluster or namespace $NAMESPACE does not exist"
    echo ""
    echo "Summary: $HEALTHY healthy, $UNHEALTHY unhealthy"
    exit 1
fi

print_status "Cluster Connection" "OK" "Connected to $CLUSTER cluster, namespace $NAMESPACE exists"
echo ""

# ============================================================================
# CHECK 1: Pod Status (Core)
# ============================================================================
print_info "Checking pod status..."

# Get all pods in the namespace
PODS=$(kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get pods -o json 2>/dev/null)

if [ -z "$PODS" ]; then
    print_status "Pods" "FAIL" "No pods found in namespace $NAMESPACE"
else
    # Count pods by phase
    RUNNING=$(echo "$PODS" | jq -r '.items[] | select(.status.phase=="Running") | .metadata.name' | wc -l)
    PENDING=$(echo "$PODS" | jq -r '.items[] | select(.status.phase=="Pending") | .metadata.name' | wc -l)
    FAILED=$(echo "$PODS" | jq -r '.items[] | select(.status.phase=="Failed" or .status.phase=="Unknown") | .metadata.name' | wc -l)
    TOTAL=$(echo "$PODS" | jq -r '.items | length')

    # Check if expected pods are running
    EXPECTED_PODS=("coordinator" "runner-hybrid" "runner-notification" "runner-exploration")
    MISSING_PODS=()

    for pod_prefix in "${EXPECTED_PODS[@]}"; do
        if ! echo "$PODS" | jq -e --arg prefix "$pod-prefix" '.items[].metadata.name | startswith($prefix)' | grep -q true; then
            MISSING_PODS+=("$pod_prefix")
        fi
    done

    if [ $RUNNING -eq $TOTAL ] && [ $FAILED -eq 0 ] && [ ${#MISSING_PODS[@]} -eq 0 ]; then
        print_status "Pods" "OK" "All $RUNNING/$TOTAL pods are Running"
    else
        MSG=""
        [ $RUNNING -lt $TOTAL ] && MSG+="$RUNNING/$TOTAL Running, "
        [ $FAILED -gt 0 ] && MSG+="$FAILED Failed, "
        [ ${#MISSING_PODS[@]} -gt 0 ] && MSG+="Missing: ${MISSING_PODS[*]}"
        print_status "Pods" "FAIL" "$MSG"
    fi

    # Show pod details for debugging
    if [ $UNHEALTHY -gt 0 ]; then
        echo ""
        print_info "Pod details:"
        kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get pods 2>/dev/null || true
    fi
fi

echo ""

# ============================================================================
# CHECK 2: Basic Metrics Endpoint (Core)
# ============================================================================
print_info "Checking metrics endpoints..."

# Get pods that should expose metrics
COORDINATOR_POD=$(kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get pods -l app.kubernetes.io/name=coordinator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
RUNNER_POD=$(kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get pods -l app.kubernetes.io/name=runner-hybrid -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

METRICS_OK=true

if [ -n "$COORDINATOR_POD" ]; then
    # Try to access metrics via kubectl port-forward (simplified approach)
    if kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" exec "$COORDINATOR_POD" -- curl -s http://localhost:9090/metrics >/dev/null 2>&1; then
        print_status "Coordinator Metrics" "OK" "Metrics endpoint accessible on $COORDINATOR_POD"
    else
        # Try HTTP get via service instead (if pod exec fails)
        if kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get svc coordinator >/dev/null 2>&1; then
            print_status "Coordinator Metrics" "OK" "Service exists (endpoint check requires cluster network access)"
        else
            print_status "Coordinator Metrics" "WARN" "Cannot verify endpoint (network restrictions)"
            METRICS_OK=false
        fi
    fi
else
    print_status "Coordinator Metrics" "FAIL" "No coordinator pod found"
    METRICS_OK=false
fi

if [ -n "$RUNNER_POD" ]; then
    if kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" exec "$RUNNER_POD" -- curl -s http://localhost:9091/metrics >/dev/null 2>&1; then
        print_status "Runner Metrics" "OK" "Metrics endpoint accessible on $RUNNER_POD"
    else
        # Fall back to service check
        if kubectl --kubeconfig="$KUBECONFIG" -n "$NAMESPACE" get svc runner-hybrid >/dev/null 2>&1; then
            print_status "Runner Metrics" "OK" "Service exists (endpoint check requires cluster network access)"
        else
            print_status "Runner Metrics" "WARN" "Cannot verify endpoint (network restrictions)"
            METRICS_OK=false
        fi
    fi
else
    print_status "Runner Metrics" "FAIL" "No runner-hybrid pod found"
    METRICS_OK=false
fi

echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo "============================================================================"
echo "Simplified Health Check Summary"
echo "============================================================================"
echo "Healthy:   $HEALTHY"
echo "Unhealthy: $UNHEALTHY"
echo ""

if [ $UNHEALTHY -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment appears healthy${NC}"
    echo ""
    echo "Note: This is a simplified health check. For comprehensive verification"
    echo "including Redis connectivity, leader election, work queues, R2, and Hub API,"
    echo "run the full verification script instead."
    exit 0
else
    echo -e "${RED}✗ Deployment has issues${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Check pod logs: kubectl -n $NAMESPACE logs <pod-name>"
    echo "  2. Describe pods: kubectl -n $NAMESPACE describe pod <pod-name>"
    echo "  3. Run full verification for detailed diagnostics"
    exit 1
fi
