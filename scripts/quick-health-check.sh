#!/usr/bin/env bash
# Quick health check for botburrow-agents deployment
# Minimal viable verification - checks pods are running and logs are accessible

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

main() {
    info "=== botburrow-agents Quick Health Check ==="
    echo ""

    # Check 1: Verify namespace exists
    info "Checking namespace: $NAMESPACE"
    if ! kubectl --kubeconfig="$KUBECONFIG" get namespace "$NAMESPACE" &>/dev/null; then
        error "✗ Namespace does not exist"
        info "  Run: kubectl --kubeconfig=$KUBECONFIG apply -k k8s/apexalgo-iad/"
        exit 1
    fi
    info "✓ Namespace exists"
    echo ""

    # Check 2: Verify pods exist and are running
    info "Checking pods..."
    local pods
    pods=$(kubectl --kubeconfig="$KUBECONFIG" get pods -n "$NAMESPACE" -o json 2>/dev/null || echo '{"items":[]}')

    local count
    count=$(echo "$pods" | jq '.items | length')

    if [ "$count" -eq 0 ]; then
        error "✗ No pods found"
        exit 1
    fi

    info "Found $count pod(s):"
    echo "$pods" | jq -r '.items[] | "  \(.metadata.name): \(.status.phase)"'

    local running
    running=$(echo "$pods" | jq '[.items[] | select(.status.phase == "Running")] | length')

    if [ "$running" -lt "$count" ]; then
        warn "⚠ Some pods not running ($running/$count running)"
        info ""
        info "Pod details:"
        kubectl --kubeconfig="$KUBECONFIG" get pods -n "$NAMESPACE" || true
    else
        info "✓ All pods running ($running/$count)"
    fi
    echo ""

    # Check 3: Verify logs are accessible (quick check - no errors)
    info "Checking logs for recent errors..."
    local has_errors=0
    while IFS= read -r pod; do
        if [ -n "$pod" ]; then
            local errors
            errors=$(kubectl --kubeconfig="$KUBECONFIG" logs -n "$NAMESPACE" "$pod" --tail=20 2>/dev/null | grep -i "error\|exception\|failed" || echo "")
            if [ -n "$errors" ]; then
                warn "⚠ $pod: Found errors in logs"
                echo "$errors" | head -5 | sed 's/^/    /'
                has_errors=1
            fi
        fi
    done < <(echo "$pods" | jq -r '.items[].metadata.name')

    if [ "$has_errors" -eq 0 ]; then
        info "✓ No errors found in recent logs"
    fi
    echo ""

    # Summary
    info "=== Summary ==="
    if [ "$running" -eq "$count" ] && [ "$has_errors" -eq 0 ]; then
        info "✓ Deployment is healthy"
        exit 0
    else
        warn "⚠ Deployment needs attention"
        exit 1
    fi
}

main "$@"
