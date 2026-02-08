#!/bin/bash
# =============================================================================
# Minimal Deployment Verification Script
# =============================================================================
# Validates that the minimal botburrow-agents deployment is healthy.
#
# Usage:
#   ./scripts/verify-minimal-deployment.sh [--namespace botburrow-agents]
#
# Requirements:
#   - kubectl configured for apexalgo-iad cluster
#   - Permissions to get pods, services, configmaps, secrets in target namespace
# =============================================================================

set -euo pipefail

NAMESPACE="${1:-botburrow-agents}"
EXIT_CODE=0

echo "=========================================="
echo "Verifying Minimal Deployment"
echo "Namespace: $NAMESPACE"
echo "=========================================="
echo

# Function to check resource exists and is ready
check_resource() {
    local resource_type="$1"
    local resource_name="$2"
    local namespace="$3"

    if kubectl get "$resource_type" "$resource_name" -n "$namespace" &>/dev/null; then
        echo "✓ $resource_type/$resource_name exists"
        return 0
    else
        echo "✗ $resource_type/$resource_name NOT found"
        return 1
    fi
}

# Function to check pod readiness
check_pod_ready() {
    local pod_name="$1"
    local namespace="$2"

    local ready=$(kubectl get pod "$pod_name" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
    if [ "$ready" == "True" ]; then
        echo "  ✓ Pod $pod_name is Ready"
        return 0
    else
        echo "  ✗ Pod $pod_name is NOT Ready"
        return 1
    fi
}

# Check namespace exists
echo "1. Checking namespace..."
if kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo "✓ Namespace $NAMESPACE exists"
else
    echo "✗ Namespace $NAMESPACE NOT found"
    echo "  Create with: kubectl create namespace $NAMESPACE"
    EXIT_CODE=1
fi
echo

# Check deployments
echo "2. Checking deployments..."
for deployment in valkey runner-hybrid; do
    if check_resource "deployment" "$deployment" "$NAMESPACE"; then
        # Check replicas
        local replicas=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
        local ready=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
        echo "  Replicas: ${ready:-0}/$replicas"
    else
        EXIT_CODE=1
    fi
done
echo

# Check services
echo "3. Checking services..."
for service in valkey coordinator; do
    check_resource "service" "$service" "$NAMESPACE" || EXIT_CODE=1
done
echo

# Check ConfigMaps
echo "4. Checking ConfigMaps..."
for cm in botburrow-agents-config agent-definitions-repos agent-permissions; do
    check_resource "configmap" "$cm" "$NAMESPACE" || EXIT_CODE=1
done
echo

# Check Secrets
echo "5. Checking Secrets..."
for secret in botburrow-agents-secrets mcp-credentials; do
    if check_resource "secret" "$secret" "$NAMESPACE"; then
        # Check if secrets have placeholder values
        local hub_key=$(kubectl get secret "$secret" -n "$NAMESPACE" -o jsonpath='{.data.HUB_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        if [[ "$hub_key" == *"placeholder"* ]]; then
            echo "  ⚠ Secret $secret contains placeholder values"
            echo "    Update with: kubectl edit secret $secret -n $NAMESPACE"
        fi
    else
        EXIT_CODE=1
    fi
done
echo

# Check pod status
echo "6. Checking pod status..."
pods=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')
if [ -z "$pods" ]; then
    echo "✗ No pods found in namespace $NAMESPACE"
    EXIT_CODE=1
else
    pod_count=0
    ready_count=0
    for pod in $pods; do
        pod_count=$((pod_count + 1))
        if check_pod_ready "$pod" "$NAMESPACE"; then
            ready_count=$((ready_count + 1))
        else
            EXIT_CODE=1
        fi
    done
    echo "  Pods: $ready_count/$pod_count ready"
fi
echo

# Check RBAC
echo "7. Checking RBAC..."
if check_resource "serviceaccount" "botburrow-agents" "$NAMESPACE"; then
    check_resource "role" "botburrow-agents" "$NAMESPACE" || EXIT_CODE=1
    check_resource "rolebinding" "botburrow-agents" "$NAMESPACE" || EXIT_CODE=1
else
    EXIT_CODE=1
fi
echo

# Check if valkey is reachable from runner pods
echo "8. Checking valkey connectivity..."
runner_pods=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=runner-hybrid -o jsonpath='{.items[*].metadata.name}')
if [ -n "$runner_pods" ]; then
    for pod in $runner_pods; do
        if kubectl exec -n "$NAMESPACE" "$pod" -- nc -z -w5 valkey 6379 &>/dev/null; then
            echo "  ✓ Pod $pod can reach valkey:6379"
        else
            echo "  ✗ Pod $pod CANNOT reach valkey:6379"
            EXIT_CODE=1
        fi
        break  # Check only first pod
    done
else
    echo "  ⚠ No runner pods found"
fi
echo

# Summary
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ All checks passed!"
    echo "Minimal deployment is healthy."
else
    echo "✗ Some checks failed."
    echo "Review the output above for details."
    echo
    echo "Common fixes:"
    echo "  - Apply secrets: kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml"
    echo "  - Check logs: kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=runner-hybrid --tail=50"
    echo "  - Restart: kubectl rollout restart deployment/runner-hybrid -n $NAMESPACE"
fi
echo "=========================================="

exit $EXIT_CODE
