# BD-1HE: Botburrow-Agents Deployment Health Verification - Research Index & Decision Guide

**Alternative Bead:** bd-1he
**Original Bead:** bd-38r - Verify botburrow-agents deployment health
**Research Approach:** research-only
**Date:** 2026-02-08
**Status:** Research Complete - Consolidated Index

---

## Executive Summary

This document serves as a **consolidated research index** for all existing documentation on botburrow-agents deployment health verification. Extensive research has already been conducted across multiple beads (bd-30r, bd-ced, bd-2lb, bd-2z6, etc.), and this document provides a navigable index with clear decision points.

### Key Finding

**The root cause of the deployment issue is that ArgoCD is NOT installed in the apexalgo-iad cluster.** All deployment manifests exist and are valid, but the GitOps automation cannot function because ArgoCD itself is not present.

### Current Deployment Status

| Aspect | Status |
|--------|--------|
| **Namespace** | `botburrow-agents` exists in apexalgo-iad cluster |
| **ArgoCD** | **NOT INSTALLED** in apexalgo-iad cluster |
| **Resources Deployed** | Zero - no deployments, services, or pods |
| **Git State** | All manifests exist in repo, pushed to GitHub |
| **Manifest Validity** | All manifests pass `kubectl apply --dry-run=client` |

---

## Research Document Index

### Primary Research Documents (Read These First)

| Document | Path | Focus | Length | Status |
|----------|------|-------|--------|--------|
| **Deployment Approaches** | `docs/research/bd-ced-deployment-approaches-comprehensive.md` | 7 deployment approaches comparison | 650+ lines | Complete |
| **Health Verification Approaches** | `docs/research/bd-30r-deployment-health-verification-approaches.md` | 6 health verification methods | 620+ lines | Complete |
| **Deployment Options** | `docs/research/bd-30r-deployment-verification-options.md` | Resolution options for deployment blocker | 530+ lines | Complete |
| **Original Verification Report** | `verification-report-bd-38r.md` | Current deployment state findings | 240+ lines | Complete |

### Supporting Research Documents

| Document | Path | Focus | Length | Status |
|----------|------|-------|--------|--------|
| **ArgoCD Research** | `docs/research/bd-2z6-argocd-deployment-approaches.md` | Comprehensive ArgoCD setup guide | 690+ lines | Complete |
| **Deployment Alternatives** | `docs/deployment-alternatives-research.md` | Alternative deployment methods | 400+ lines | Complete |
| **Simplified Approach** | `docs/research/bd-2yb-simplified-approach-summary.md` | Minimal deployment approach | 300+ lines | Complete |
| **SealedSecret Research** | `docs/research/bd-1dx-sealedsecret-creation-options.md` | Secrets management options | 200+ lines | Complete |

### Deployment Guides

| Document | Path | Focus | Usage |
|----------|------|-------|-------|
| **Minimal Deployment** | `k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md` | Minimal viable deployment | Quick start |
| **Simplified Deployment** | `docs/SIMPLIFIED_DEPLOYMENT.md` | Simplified deployment guide | Step-by-step |
| **Deployment Guide** | `docs/deployment/deployment.md` | Full deployment documentation | Comprehensive |
| **Workaround Summary** | `docs/workarounds/bd-cni-argocd-workaround.md` | ArgoCD bypass workaround | Immediate fix |

### Verification Tools

| Script | Path | Purpose | Usage |
|--------|------|---------|-------|
| **Deploy Workaround** | `scripts/deploy-workaround.sh` | Automated deployment via kubectl | `./scripts/deploy-workaround.sh` |
| **Simplified Health Check** | `scripts/simplified-health-check.sh` | Quick pod + metrics check | `./scripts/simplified-health-check.sh` |
| **Preflight Check** | `scripts/preflight-check.sh` | Pre-deployment validation | `./scripts/preflight-check.sh` |

---

## Quick Decision Guide

### Decision 1: How to Deploy?

**Choose based on your situation:**

| Situation | Recommended Approach | Document Reference |
|-----------|---------------------|-------------------|
| **Need deployment TODAY** | Approach 1: kubectl Apply | `docs/research/bd-ced-deployment-approaches-comprehensive.md#approach-1` |
| **Planning production deployment** | Approach 2: Install ArgoCD | `docs/research/bd-ced-deployment-approaches-comprehensive.md#approach-2` |
| **ArgoCD already installed** | Approach 4: Standalone App | `docs/research/bd-ced-deployment-approaches-comprehensive.md#approach-4` |
| **Prefer CI/CD over GitOps** | Approach 5: GitHub Actions | `docs/research/bd-ced-deployment-approaches-comprehensive.md#approach-5` |

### Decision 2: How to Verify Health?

**Choose based on verification needs:**

| Verification Need | Recommended Approach | Document Reference |
|-------------------|---------------------|-------------------|
| **Quick yes/no health check** | Approach 1: Simplified Check | `docs/research/bd-30r-deployment-health-verification-approaches.md#approach-1` |
| **Full system verification** | Approach 2: Comprehensive Check | `docs/research/bd-30r-deployment-health-verification-approaches.md#approach-2` |
| **Production monitoring** | Approach 3: K8s Probes + Alerts | `docs/research/bd-30r-deployment-health-verification-approaches.md#approach-3` |
| **Centralized health API** | Approach 4: External Service | `docs/research/bd-30r-deployment-health-verification-approaches.md#approach-4` |

---

## Deployment Approaches Summary

### Approach 1: Direct kubectl Apply (Recommended for Immediate Deployment)

**Use when:** You need deployment today, development/testing, getting unblocked

**Implementation:**
```bash
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh
```

**Pros:**
- Immediate deployment
- Simple and direct
- No additional infrastructure
- Already scripted

**Cons:**
- Not GitOps
- Manual updates required
- Drift risk

**Detailed Guide:** `docs/research/bd-ced-deployment-approaches-comprehensive.md#approach-1`

---

### Approach 2: Install ArgoCD (Recommended for Production)

**Use when:** Production deployment, true GitOps workflow, long-term maintainability

**Implementation:**
```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Create ApplicationSet for botburrow-agents
kubectl apply -f k8s/apexalgo-iad/argocd-applicationset.yaml
```

**Pros:**
- True GitOps
- Automated sync
- Self-healing
- Production-ready

**Cons:**
- Additional infrastructure
- Setup complexity
- Resource overhead

**Detailed Guide:** `docs/research/bd-ced-deployment-approaches-comprehensive.md#approach-2`

---

### Approach 3: Hybrid (Recommended for Balanced Approach)

**Use when:** Immediate need + long-term GitOps goal

**Phase 1 (Today):** Deploy via kubectl
```bash
./scripts/deploy-workaround.sh
```

**Phase 2 (Later):** Migrate to ArgoCD
```bash
# After Phase 1 validation
# Install ArgoCD and migrate resources
```

**Detailed Guide:** `docs/research/bd-ced-deployment-approaches-comprehensive.md#recommendations`

---

## Health Verification Approaches Summary

### Approach 1: Simplified Pod & Metrics Check

**Use when:** Quick verification, frequent checks, minimal overhead

**Implementation:**
```bash
./scripts/simplified-health-check.sh
```

**Status:** Already implemented

---

### Approach 2: Comprehensive System Health Check

**Use when:** Debugging, full system verification, incident investigation

**Covers:**
- Pod status
- Metrics endpoints
- Redis connectivity
- Leader election
- Work queues
- Hub API
- R2 connectivity

**Status:** Partially implemented

---

### Approach 3: Kubernetes Probes + Prometheus Alerts (Recommended for Production)

**Use when:** Production deployment, automatic recovery, continuous monitoring

**Components:**
- Liveness probes (already in manifests)
- Readiness probes (already in manifests)
- Prometheus alerts (to be created)

**Status:** Probes exist, alerts not yet defined

---

## Comparison Matrices

### Deployment Methods Comparison

| Approach | GitOps | Speed | Complexity | Infrastructure | Risk | Best For |
|----------|--------|-------|------------|----------------|------|----------|
| **1. kubectl Apply** | No | Fast | Low | None | Low | Immediate deployment |
| **2. Install ArgoCD** | Yes | Slow | Medium | ArgoCD | Low | Production GitOps |
| **3. Hybrid** | Yes (later) | Fast | Low-Medium | ArgoCD (later) | Low | Balanced approach |
| **4. Standalone App** | Yes | Medium | Low | ArgoCD | Low | Fine-grained control |
| **5. GitHub Actions** | No | Fast | Medium | GitHub | Medium | CI/CD focus |

### Health Verification Comparison

| Approach | Implementation | Runtime Cost | Comprehensive | Alerts | Best For |
|----------|----------------|--------------|---------------|--------|----------|
| **1. Simplified** | Low (done) | Low | No | Manual | Quick checks |
| **2. Comprehensive** | High | Low | Yes | Manual | Full verification |
| **3. K8s Probes + Alerts** | Medium | Low | Yes | Yes | Production |
| **4. External Service** | High | Medium | Yes | Custom | Centralized API |

---

## Bead Dependency Status

### Current Bead Chain

```
bd-1he (this research) - IN PROGRESS
  ↓ (informs decision on deployment method)
bd-38r (verify deployment) - CLOSED (deployment not found)
  ↓
bd-2f8 (fix deployment issues) - BLOCKED by bd-38r
  ↓
bd-13j (build and deploy) - BLOCKED by bd-2f8
```

### Related Beads

| Bead | Title | Status | Relationship |
|------|-------|--------|--------------|
| **bd-38r** | Verify botburrow-agents deployment health | CLOSED | Original bead (blocked) |
| **bd-30r** | Alternative: Research and document options | CLOSED | Previous research (bd-1he duplicate) |
| **bd-ced** | Alternative: Research and document options | CLOSED | Comprehensive deployment research |
| **bd-1v9** | Fix botburrow-agents deployment via ArgoCD | CLOSED | ArgoCD deployment bead |
| **bd-2f8** | Fix botburrow-agents deployment issues | BLOCKED | Depends on bd-38r |
| **bd-13j** | Build and deploy botburrow-agents updates | BLOCKED | Depends on bd-2f8 |

---

## Next Steps (Human Decision Required)

### Immediate Decision Needed

**Please choose ONE of the following deployment approaches:**

**A. Deploy via kubectl immediately** (Approach 1)
- Pro: Deployment works today
- Con: Not GitOps, manual updates
- Effort: 15-30 minutes
- Command: `./scripts/deploy-workaround.sh`

**B. Install ArgoCD then deploy** (Approach 2)
- Pro: True GitOps, automated
- Con: Setup time, infrastructure
- Effort: 1-2 hours
- Command: See `docs/research/bd-2z6-argocd-deployment-approaches.md`

**C. Hybrid approach** (Approach 3)
- Pro: Deploy now, GitOps later
- Con: Two-step process
- Effort: 15-30 min now, migration later
- Command: `./scripts/deploy-workaround.sh` now, ArgoCD later

**D. Alternative solution** (Specify)
- Please describe your preferred approach

### After Deployment Decision

Once deployment method is chosen and resources are deployed:

```bash
# Verify deployment health
./scripts/simplified-health-check.sh

# Full verification (optional)
./scripts/verify-deployment.sh
```

---

## Quick Reference Commands

### Check Current State
```bash
# Check if resources exist
kubectl get all -n botburrow-agents

# Check ArgoCD installation
kubectl get applications.argoproj.io -A
kubectl get namespace argocd
```

### Deploy via kubectl (Approach 1)
```bash
cd /home/coder/botburrow-agents
./scripts/deploy-workaround.sh

# Verify
kubectl get pods -n botburrow-agents
```

### Install ArgoCD (Approach 2)
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

---

## Related Documentation References

### For Deployment Decisions
1. `docs/research/bd-ced-deployment-approaches-comprehensive.md` - **START HERE** for deployment options
2. `docs/research/bd-2z6-argocd-deployment-approaches.md` - Comprehensive ArgoCD guide
3. `k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md` - Minimal deployment guide
4. `docs/SIMPLIFIED_DEPLOYMENT.md` - Simplified deployment steps

### For Health Verification Decisions
1. `docs/research/bd-30r-deployment-health-verification-approaches.md` - **START HERE** for verification options
2. `docs/research/bd-30r-deployment-verification-options.md` - Resolution options
3. `verification-report-bd-38r.md` - Original verification findings

### For Troubleshooting
1. `docs/operations/troubleshooting.md` - Troubleshooting guide
2. `docs/verification/quick-check.md` - Quick verification commands
3. `docs/verification/SIMPLIFIED-VERIFICATION.md` - Simplified verification

---

## Conclusion

This research index consolidates findings from multiple previous research beads (bd-30r, bd-ced, bd-2lb, bd-2z6, bd-2yb, bd-1dx) that have thoroughly documented:

1. **Deployment approaches** - 7 different methods for deploying botburrow-agents
2. **Health verification approaches** - 6 different methods for verifying deployment health
3. **Root cause analysis** - ArgoCD is not installed in apexalgo-iad cluster
4. **Implementation guides** - Step-by-step instructions for each approach

**Recommended Action:** Two-phase hybrid approach - deploy immediately via kubectl (Phase 1), then migrate to ArgoCD for production GitOps (Phase 2).

**Human Decision Required:** Choose deployment approach (A, B, C, or D) from the options above.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47)
**Bead:** bd-1he
**Status:** Research Complete - Awaiting Human Decision
