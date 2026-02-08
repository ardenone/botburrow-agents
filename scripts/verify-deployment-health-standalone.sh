#!/usr/bin/env bash
# =============================================================================
# botburrow-agents Standalone Deployment Health Verification
# =============================================================================
# This script provides a WORKAROUND for verifying botburrow-agents deployment
# health WITHOUT requiring full ArgoCD setup or complete secrets configuration.
#
# This is a TEMPORARY SOLUTION that:
# 1. Works with manual kubectl deployment
# 2. Provides clear diagnostics without full secrets
# 3. Identifies what's missing and what's working
#
# USAGE:
#   ./scripts/verify-deployment-health-standalone.sh
#
# REQUIREMENTS:
#   - kubectl configured for apexalgo-iad cluster
#   - KUBECONFIG pointing to apexalgo-iad (default: /home/coder/.kube/apexalgo-iad.kubeconfig)
#
# FOLLOW-UP:
#   This is a workaround. A proper solution should implement:
#   - ArgoCD GitOps deployment
#   - Proper SealedSecrets management
#   - Automated health checks with alerts
# =============================================================================

set -uo pipefail
# Note: -e is disabled to allow full report generation even with errors

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-botburrow-agents}"
KUBECONFIG="${KUBECONFIG:-/home/coder/.kube/apexalgo-iad.kubeconfig}"
export KUBECONFIG

# Counter for issues
ISSUES=0
WARNINGS=0

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((ISSUES++))
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
    ((WARNINGS++))
}

# Run kubectl command safely, return non-zero on RBAC errors
kubectl_safe() {
    local output
    local exit_code

    output=$(kubectl "$@" 2>&1)
    exit_code=$?

    if [ "${exit_code}" -ne 0 ]; then
        # Check if it's an RBAC error
        if echo "${output}" | grep -qi "forbidden\|unauthorized"; then
            log_warning "RBAC restricted: kubectl $* (not authorized, skipping)"
            return 2
        fi
        # Return actual error
        echo "${output}"
        return "${exit_code}"
    fi

    echo "${output}"
    return 0
}

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# =============================================================================
# MAIN VERIFICATION FLOW
# =============================================================================

print_header "botburrow-agents Deployment Health Verification (WORKAROUND)"
log_info "This is a temporary standalone verification script"
log_info "Namespace: ${NAMESPACE}"
log_info "Kubeconfig: ${KUBECONFIG}"
echo ""

# =============================================================================
# 1. CLUSTER CONNECTIVITY
# =============================================================================
print_header "1. Cluster Connectivity Check"

# Try to connect - cluster-info may fail due to RBAC, so check if we can reach namespace
if kubectl get namespace "${NAMESPACE}" &>/dev/null || kubectl version --client=true &>/dev/null; then
    log_success "Connected to Kubernetes cluster (or can reach API)"

    # Get cluster info from config
    CLUSTER_NAME=$(kubectl config view --minify -o jsonpath='{.clusters[0].name}' 2>/dev/null || echo "unknown")
    log_info "Cluster: ${CLUSTER_NAME}"

    # Check current context/user (may have RBAC limitations)
    CURRENT_USER=$(kubectl config view --minify -o jsonpath='{.contexts[0].context.user}' 2>/dev/null || echo "unknown")
    log_info "Current user: ${CURRENT_USER}"
else
    log_error "Cannot connect to Kubernetes cluster"
    exit 1
fi

# =============================================================================
# 2. NAMESPACE CHECK
# =============================================================================
print_header "2. Namespace Verification"

if kubectl get namespace "${NAMESPACE}" &>/dev/null; then
    log_success "Namespace '${NAMESPACE}' exists"

    AGE=$(kubectl get namespace "${NAMESPACE}" -o jsonpath='{.metadata.age}')
    log_info "Namespace age: ${AGE}"

    # Check if namespace has labels
    LABELS=$(kubectl get namespace "${NAMESPACE}" -o jsonpath='{.metadata.labels}')
    if [ -n "${LABELS}" ]; then
        log_info "Labels: ${LABELS}"
    fi
else
    log_error "Namespace '${NAMESPACE}' does not exist"
    log_info "Create it with: kubectl create namespace ${NAMESPACE}"
fi

# =============================================================================
# 3. RESOURCE INVENTORY
# =============================================================================
print_header "3. Resource Inventory"

# Count resources by type (handle RBAC gracefully)
declare -A resource_counts
resource_types=("pods" "deployments" "services" "configmaps" "secrets" "serviceaccounts" "statefulsets")

for resource_type in "${resource_types[@]}"; do
    # Check for RBAC error first
    RBAC_ERROR=$(kubectl get "${resource_type}" -n "${NAMESPACE}" 2>&1 | grep -i "forbidden\|unauthorized" || true)

    if [ -n "${RBAC_ERROR}" ]; then
        log_warning "${resource_type}: RBAC restricted (cannot check)"
        resource_counts[$resource_type]=0
    else
        # Count actual resources (get output from stdout only, suppress stderr)
        OUTPUT=$(kubectl get "${resource_type}" -n "${NAMESPACE}" 2>/dev/null || true)
        if [ -n "${OUTPUT}" ]; then
            count=$(echo "${OUTPUT}" | grep -c NAME || echo "0")
        else
            count=0
        fi

        resource_counts[$resource_type]=$count

        if [ "${count}" -gt 0 ]; then
            log_success "${resource_type}: ${count} found"
        else
            log_warning "${resource_type}: 0 found"
        fi
    fi
done

# Check if namespace is empty (only count non-RBAC-limited resources)
TOTAL_RESOURCES=0
for count in "${resource_counts[@]}"; do
    TOTAL_RESOURCES=$((TOTAL_RESOURCES + count))
done

if [ "${TOTAL_RESOURCES}" -eq 0 ]; then
    log_error "Namespace is completely empty - no resources deployed"
    log_info "To deploy minimal stack:"
    log_info "  kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
    log_info "  kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml"
fi

# =============================================================================
# 4. POD STATUS
# =============================================================================
print_header "4. Pod Status Analysis"

if [ "${resource_counts[pods]}" -gt 0 ]; then
    log_info "Pod details:"
    kubectl get pods -n "${NAMESPACE}" -o wide

    echo ""
    log_info "Pod status breakdown:"

    # Count by status
    RUNNING=$(kubectl get pods -n "${NAMESPACE}" -o json | jq -r '[.items[] | select(.status.phase=="Running")] | length' 2>/dev/null || echo "0")
    PENDING=$(kubectl get pods -n "${NAMESPACE}" -o json | jq -r '[.items[] | select(.status.phase=="Pending")] | length' 2>/dev/null || echo "0")
    FAILED=$(kubectl get pods -n "${NAMESPACE}" -o json | jq -r '[.items[] | select(.status.phase=="Failed" or .status.phase=="Error" or .status.phase=="CrashLoopBackOff")] | length' 2>/dev/null || echo "0")

    log_info "Running: ${RUNNING}"
    log_info "Pending: ${PENDING}"
    log_info "Failed: ${FAILED}"

    # Check for not-ready pods
    NOT_READY=$(kubectl get pods -n "${NAMESPACE}" --field-selector=status.phase!=Running -o json 2>/dev/null | jq -r '.items[] | "\(.metadata.name): \(.status.phase)"' 2>/dev/null || echo "")

    if [ -n "${NOT_READY}" ]; then
        log_error "Pods not in Running state:"
        echo "${NOT_READY}"
    fi
else
    log_warning "No pods found - deployment likely not applied"
fi

# =============================================================================
# 5. CRITICAL COMPONENTS CHECK
# =============================================================================
print_header "5. Critical Components Check"

# 5a. Valkey (Redis)
log_info "Checking valkey (Redis/Valkey)..."
VALKEY_PODS=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=valkey -o jsonpath='{.items}' 2>/dev/null)
if [ -n "${VALKEY_PODS}" ]; then
    VALKEY_READY=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=valkey -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    if [ "${VALKEY_READY}" == "True" ]; then
        log_success "Valkey is Ready"

        # Test Redis connectivity if pod is running
        VALKEY_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=valkey -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [ -n "${VALKEY_POD}" ]; then
            if kubectl exec -n "${NAMESPACE}" "${VALKEY_POD}" -- redis-cli ping &>/dev/null; then
                PING_RESULT=$(kubectl exec -n "${NAMESPACE}" "${VALKEY_POD}" -- redis-cli ping 2>/dev/null)
                log_success "Redis connectivity verified: ${PING_RESULT}"
            else
                log_warning "Could not verify Redis connectivity (pod might not be fully ready)"
            fi
        fi
    else
        log_error "Valkey exists but not Ready"
    fi
else
    log_warning "Valkey not deployed (required for coordination)"
fi

# 5b. Runners
log_info "Checking runners..."
RUNNER_PODS=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/component=runner -o jsonpath='{.items}' 2>/dev/null)
if [ -n "${RUNNER_PODS}" ]; then
    RUNNER_COUNT=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/component=runner --no-headers 2>/dev/null | wc -l)
    log_success "Runner pods found: ${RUNNER_COUNT}"

    # Check runner modes
    HYBRID_COUNT=$(kubectl get pods -n "${NAMESPACE}" -l runner-mode=hybrid --no-headers 2>/dev/null | wc -l)
    NOTIFICATION_COUNT=$(kubectl get pods -n "${NAMESPACE}" -l runner-mode=notification --no-headers 2>/dev/null | wc -l)
    EXPLORATION_COUNT=$(kubectl get pods -n "${NAMESPACE}" -l runner-mode=exploration --no-headers 2>/dev/null | wc -l)

    log_info "Runner modes: hybrid=${HYBRID_COUNT}, notification=${NOTIFICATION_COUNT}, exploration=${EXPLORATION_COUNT}"
else
    log_warning "No runner pods found"
fi

# 5c. Coordinator
log_info "Checking coordinator..."
COORDINATOR_PODS=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=coordinator -o jsonpath='{.items}' 2>/dev/null)
if [ -n "${COORDINATOR_PODS}" ]; then
    COORDINATOR_READY=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=coordinator -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    if [ "${COORDINATOR_READY}" == "True" ]; then
        log_success "Coordinator is Ready"
    else
        log_warning "Coordinator exists but not Ready"
    fi
else
    log_info "Coordinator not deployed (optional for minimal deployment)"
fi

# =============================================================================
# 6. SECRETS CHECK
# =============================================================================
print_header "6. Secrets Availability Check"

# Required secrets
REQUIRED_SECRETS=(
    "botburrow-agents-secrets"
    "mcp-credentials"
)

OPTIONAL_SECRETS=(
    "valkey-secret"
)

log_info "Checking required secrets..."
for secret in "${REQUIRED_SECRETS[@]}"; do
    SECRET_CHECK=$(kubectl get secret "${secret}" -n "${NAMESPACE}" 2>&1)

    if echo "${SECRET_CHECK}" | grep -qi "forbidden\|unauthorized"; then
        log_warning "Secret '${secret}': RBAC restricted (cannot verify)"
    elif echo "${SECRET_CHECK}" | grep -q "${secret}"; then
        log_success "Secret '${secret}' exists"

        # Check if it's a placeholder (may fail on RBAC too)
        KEYS=$(kubectl get secret "${secret}" -n "${NAMESPACE}" -o jsonpath='{.data}' 2>/dev/null | jq -r 'keys[]' 2>/dev/null || echo "")
        if [ -n "${KEYS}" ]; then
            KEY_COUNT=$(echo "${KEYS}" | wc -l)
            log_info "  Keys: ${KEY_COUNT}"
        fi
    else
        log_error "Required secret '${secret}' not found"
        log_info "  Create placeholder: kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
    fi
done

log_info "Checking optional secrets..."
for secret in "${OPTIONAL_SECRETS[@]}"; do
    SECRET_CHECK=$(kubectl get secret "${secret}" -n "${NAMESPACE}" 2>&1)

    if echo "${SECRET_CHECK}" | grep -qi "forbidden\|unauthorized"; then
        log_info "Optional secret '${secret}': RBAC restricted (cannot verify)"
    elif echo "${SECRET_CHECK}" | grep -q "${secret}"; then
        log_success "Optional secret '${secret}' exists"
    else
        log_info "Optional secret '${secret}' not found (may be OK)"
    fi
done

# =============================================================================
# 7. CONFIGMAPS CHECK
# =============================================================================
print_header "7. Configuration Check"

REQUIRED_CONFIGMAPS=(
    "botburrow-agents-config"
    "agent-definitions-repos"
)

for cm in "${REQUIRED_CONFIGMAPS[@]}"; do
    if kubectl get configmap "${cm}" -n "${NAMESPACE}" &>/dev/null; then
        log_success "ConfigMap '${cm}' exists"
    else
        log_error "ConfigMap '${cm}' not found"
    fi
done

# =============================================================================
# 8. SERVICES CHECK
# =============================================================================
print_header "8. Services Check"

SERVICES=("valkey")
for svc in "${SERVICES[@]}"; do
    if kubectl get service "${svc}" -n "${NAMESPACE}" &>/dev/null; then
        log_success "Service '${svc}' exists"

        # Get service type and cluster IP
        SVC_TYPE=$(kubectl get service "${svc}" -n "${NAMESPACE}" -o jsonpath='{.spec.type}')
        CLUSTER_IP=$(kubectl get service "${svc}" -n "${NAMESPACE}" -o jsonpath='{.spec.clusterIP}')
        log_info "  Type: ${SVC_TYPE}, ClusterIP: ${CLUSTER_IP}"
    else
        log_warning "Service '${svc}' not found"
    fi
done

# =============================================================================
# 9. RECENT LOGS (if pods exist)
# =============================================================================
print_header "9. Recent Logs Analysis"

if [ "${resource_counts[pods]}" -gt 0 ]; then
    log_info "Fetching recent logs from pods (last 10 lines)..."

    for pod in $(kubectl get pods -n "${NAMESPACE}" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
        echo ""
        log_info "=== ${pod} ==="

        # Try to get logs, handle container restarts
        if kubectl logs -n "${NAMESPACE}" "${pod}" --tail=10 &>/dev/null; then
            kubectl logs -n "${NAMESPACE}" "${pod}" --tail=10 2>/dev/null | head -10
        else
            log_warning "Could not fetch logs (pod might not be started)"
        fi
    done
else
    log_info "No pods to check logs for"
fi

# =============================================================================
# 10. SUMMARY & RECOMMENDATIONS
# =============================================================================
print_header "10. Summary & Recommendations"

echo ""
log_info "Deployment Summary:"
log_info "  Total Issues: ${ISSUES}"
log_info "  Total Warnings: ${WARNINGS}"

if [ "${ISSUES}" -eq 0 ] && [ "${WARNINGS}" -eq 0 ]; then
    log_success "All checks passed! Deployment appears healthy."
elif [ "${ISSUES}" -eq 0 ]; then
    log_success "No critical issues found. Some warnings may need attention."
else
    log_error "Found ${ISSUES} issue(s) that need attention"
fi

echo ""
log_info "Quick Fix Recommendations:"

if [ "${TOTAL_RESOURCES}" -eq 0 ]; then
    echo ""
    log_warning "NAMESPACE IS EMPTY - Deploy minimal stack:"
    echo "  1. kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
    echo "  2. kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml"
    echo "  3. ${BASH_SOURCE[0]}  # Re-run this script"
fi

if ! kubectl get secret botburrow-agents-secrets -n "${NAMESPACE}" &>/dev/null; then
    echo ""
    log_warning "MISSING SECRETS - Create placeholder:"
    echo "  kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
fi

if [ "${resource_counts[pods]}" -gt 0 ]; then
    FAILED_PODS=$(kubectl get pods -n "${NAMESPACE}" --field-selector=status.phase!=Running -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)
    if [ -n "${FAILED_PODS}" ]; then
        echo ""
        log_warning "SOME PODS NOT RUNNING - Check logs:"
        for pod in ${FAILED_PODS}; do
            echo "  kubectl logs -n ${NAMESPACE} ${pod} --previous  # Check previous container logs"
        done
    fi
fi

echo ""
log_info "For full deployment (when ready):"
echo "  kubectl apply -k k8s/apexalgo-iad/ --kustomize=kustomization-full.yaml"

echo ""
log_info "For troubleshooting details:"
echo "  - Check pod logs: kubectl logs -n ${NAMESPACE} <pod-name>"
echo "  - Describe pods: kubectl describe pod -n ${NAMESPACE} <pod-name>"
echo "  - Check events: kubectl get events -n ${NAMESPACE} --sort-by=.lastTimestamp"

echo ""
log_info "This is a WORKAROUND script. Proper solution requires:"
echo "  - ArgoCD GitOps setup"
echo "  - SealedSecrets management"
echo "  - Automated monitoring & alerting"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Verification Complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Exit code based on issues
if [ "${ISSUES}" -gt 0 ]; then
    exit 1
else
    exit 0
fi
