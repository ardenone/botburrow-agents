#!/usr/bin/env bash
# Minimal botburrow-agents deployment verification script
# Run from devpod on ardenone-cluster targeting apexalgo-iad

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cluster config
KUBECONFIG="${KUBECONFIG:-/home/coder/.kube/apexalgo-iad.kubeconfig}"
NAMESPACE="${NAMESPACE:-botburrow-agents}"

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_kubectl() {
    info "Checking kubectl access to apexalgo-iad..."
    if kubectl --kubeconfig="$KUBECONFIG" get nodes &>/dev/null; then
        info "✓ kubectl access working"
        return 0
    else
        error "✗ Cannot access apexalgo-iad cluster"
        return 1
    fi
}

check_namespace() {
    info "Checking namespace: $NAMESPACE"
    if kubectl --kubeconfig="$KUBECONFIG" get namespace "$NAMESPACE" &>/dev/null; then
        # Check if namespace is empty
        local resource_count
        resource_count=$(kubectl --kubeconfig="$KUBECONFIG" get all -n "$NAMESPACE" -o json 2>/dev/null | jq '.items | length' || echo "0")
        if [ "$resource_count" -eq 0 ]; then
            warn "✗ Namespace exists but is empty ($resource_count resources)"
            info "  Run: kubectl --kubeconfig=$KUBECONFIG apply -k k8s/apexalgo-iad/"
            return 1
        fi
        info "✓ Namespace exists with resources"
        return 0
    else
        warn "✗ Namespace does not exist - deployment not applied"
        info "  Run: kubectl --kubeconfig=$KUBECONFIG apply -f k8s/apexalgo-iad/namespace.yaml"
        return 1
    fi
}

check_pods() {
    info "Checking pods in namespace: $NAMESPACE"
    local pods
    pods=$(kubectl --kubeconfig="$KUBECONFIG" get pods -n "$NAMESPACE" -o json 2>/dev/null || echo '{"items":[]}')

    local count
    count=$(echo "$pods" | jq '.items | length')

    if [ "$count" -eq 0 ]; then
        warn "✗ No pods found in namespace"
        return 1
    fi

    info "Found $count pod(s):"
    echo "$pods" | jq -r '.items[] | "  \(.metadata.name): \(.status.phase)"'

    local running
    running=$(echo "$pods" | jq '[.items[] | select(.status.phase == "Running")] | length')

    if [ "$running" -eq "$count" ]; then
        info "✓ All pods running ($running/$count)"
        return 0
    else
        warn "✗ Some pods not running ($running/$count running)"
        return 1
    fi
}

check_services() {
    info "Checking services in namespace: $NAMESPACE"
    local services
    services=$(kubectl --kubeconfig="$KUBECONFIG" get svc -n "$NAMESPACE" -o json 2>/dev/null || echo '{"items":[]}')

    local count
    count=$(echo "$services" | jq '.items | length')

    if [ "$count" -eq 0 ]; then
        warn "✗ No services found"
        return 1
    fi

    info "✓ Found $count service(s)"
    echo "$services" | jq -r '.items[] | "  \(.metadata.name): \(.spec.type)"'
    return 0
}

check_valkey() {
    info "Checking Valkey/Redis connectivity"
    local valkey_pod
    valkey_pod=$(kubectl --kubeconfig="$KUBECONFIG" get pods -n "$NAMESPACE" -l app=valkey -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -z "$valkey_pod" ]; then
        warn "✗ No Valkey pod found"
        return 1
    fi

    if kubectl --kubeconfig="$KUBECONFIG" exec -n "$NAMESPACE" "$valkey_pod" -- redis-cli ping &>/dev/null; then
        info "✓ Valkey responding to PING"
        return 0
    else
        warn "✗ Valkey not responding"
        return 1
    fi
}

check_coordinator_leader() {
    info "Checking coordinator leader election"
    local leader_log
    leader_log=$(kubectl --kubeconfig="$KUBECONFIG" logs -n "$NAMESPACE" -l app.kubernetes.io/name=coordinator --tail=100 2>/dev/null | grep -i "became_leader\|is_leader" || echo "")

    if [ -n "$leader_log" ]; then
        info "✓ Coordinator leader election active"
        return 0
    else
        warn "✗ No leader election log found (may be starting up)"
        return 1
    fi
}

main() {
    info "=== botburrow-agents Deployment Verification ==="
    echo ""

    local checks_passed=0
    local checks_total=0

    # Prerequisites
    checks_total=$((checks_total + 1))
    if check_kubectl; then
        checks_passed=$((checks_passed + 1))
    fi
    echo ""

    # Only continue if kubectl works
    if ! check_kubectl 2>/dev/null; then
        error "Cannot proceed without kubectl access"
        exit 1
    fi

    # Namespace check
    checks_total=$((checks_total + 1))
    if check_namespace; then
        checks_passed=$((checks_passed + 1))
    else
        warn "Skipping remaining checks - namespace not deployed"
        info "Run: kubectl --kubeconfig=$KUBECONFIG apply -k k8s/apexalgo-iad/"
        exit 1
    fi
    echo ""

    # Pods check
    checks_total=$((checks_total + 1))
    if check_pods; then
        checks_passed=$((checks_passed + 1))
    fi
    echo ""

    # Services check
    checks_total=$((checks_total + 1))
    if check_services; then
        checks_passed=$((checks_passed + 1))
    fi
    echo ""

    # Valkey check
    checks_total=$((checks_total + 1))
    if check_valkey; then
        checks_passed=$((checks_passed + 1))
    fi
    echo ""

    # Coordinator leader check
    checks_total=$((checks_total + 1))
    if check_coordinator_leader; then
        checks_passed=$((checks_passed + 1))
    fi
    echo ""

    # Summary
    info "=== Verification Summary: $checks_passed/$checks_total checks passed ==="

    if [ "$checks_passed" -eq "$checks_total" ]; then
        info "✓ All checks passed!"
        exit 0
    else
        warn "✗ Some checks failed"
        exit 1
    fi
}

main "$@"
