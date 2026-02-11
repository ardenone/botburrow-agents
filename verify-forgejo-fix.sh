#!/bin/bash
# Verification script for bd-1co: Forgejo URL fix

echo "=== Checking botburrow-agents pod status ==="
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get pods -n botburrow-agents -o wide

echo ""
echo "=== Checking coordinator deployment URL ==="
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get deployment coordinator -n botburrow-agents -o jsonpath='{.spec.template.spec.initContainers[0].command}' | jq -r 'join(" ")'

echo ""
echo "=== Checking latest coordinator pod logs ==="
POD=$(kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get pods -n botburrow-agents -l app.kubernetes.io/name=coordinator --sort-by=.metadata.creationTimestamp | tail -1 | awk '{print $1}')
if [ -n "$POD" ]; then
  echo "Pod: $POD"
  kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig logs -n botburrow-agents $POD -c git-clone --tail=10
else
  echo "No coordinator pods found"
fi

echo ""
echo "=== Expected URL ==="
echo "http://forgejo.forgejo.svc.cluster.local:3000/ardenone/agent-definitions.git"
