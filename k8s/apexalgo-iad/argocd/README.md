# ArgoCD GitOps Installation for botburrow-agents

**Cluster:** apexalgo-iad
**Repository:** https://github.com/ardenone/botburrow-agents.git
**Status:** Ready for Cluster-Admin Deployment

---

## Quick Start

```bash
# 1. Install ArgoCD (cluster-admin required)
kubectl apply -f namespace.yaml
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 2. Create secrets (cluster-admin required)
kubectl apply -f ../botburrow-agents-secrets-PLACEHOLDER.yml
kubectl create secret generic mcp-credentials -n botburrow-agents --from-literal=...

# 3. Deploy ApplicationSet
kubectl apply -f applicationset.yaml

# 4. Verify
kubectl get pods -n argocd
kubectl get applications.argoproj.io -n argocd
kubectl get all -n botburrow-agents
```

---

## Files

| File | Description |
|------|-------------|
| `namespace.yaml` | ArgoCD namespace |
| `install.yaml` | Installation instructions and verification script |
| `applicationset.yaml` | ApplicationSet for botburrow-agents |
| `ingress.yaml` | Traefik IngressRoute (optional) |
| `kustomization.yaml` | Kustomize configuration |
| `DEPLOYMENT-GUIDE.md` | Comprehensive deployment guide |

---

## Documentation

See `DEPLOYMENT-GUIDE.md` for detailed installation instructions.

---

## Access ArgoCD UI

```bash
# Port-forward
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d

# Open https://localhost:8080
# Login: admin (password from above)
```

---

## References

- ArgoCD Docs: https://argo-cd.readthedocs.io/
- ApplicationSet: https://argocd-applicationset.readthedocs.io/
- Deployment Guide: `DEPLOYMENT-GUIDE.md`
