# Botburrow-Agents Build and Deploy: Alternative Approaches Research

**Date:** 2026-02-08
**Bead:** bd-3hi (Alternative: Research and document options)
**Original Bead:** bd-13j (Build and deploy botburrow-agents updates)

---

## Executive Summary

This document provides a comprehensive comparison of approaches for building and deploying botburrow-agents updates. The original task (bd-13j) involves a multi-step deployment process that currently requires significant manual intervention. This research identifies alternative approaches to improve automation, reliability, and maintainability.

---

## Current State Analysis

### Existing Deployment Flow (bd-13j)

The current deployment process documented in bd-13j involves these manual steps:

1. **Code Changes** - Update code in `botburrow-agents` repo
2. **Version Update** - Update VERSION file
3. **Local Testing** - Run `pytest tests/`
4. **Git Push** - Commit and push to GitHub
5. **CI/CD Build** - GitHub Actions builds Docker images (~5 min wait)
6. **Manual Verification** - Verify images pushed to Docker Hub
7. **Manifest Update** - Update manifests in separate `ardenone-cluster` repo
8. **Second Git Push** - Commit and push manifests
9. **ArgoCD Sync** - Wait for ArgoCD to sync to apexalgo-iad cluster
10. **Manual Monitoring** - Monitor rolling update
11. **Service Verification** - Verify no activation processing interruption

**Total Estimated Time:** 15-30 minutes (mostly waiting)
**Human Touch Points:** 5-6 (version update, verification, manifest update, monitoring)

### Existing Infrastructure

**CI/CD:**
- `.github/workflows/ci-cd.yml` - Builds Docker images on push to main
- `.github/workflows/deploy-kubernetes.yml` - Deploy to Kubernetes (with manual approval)

**Kubernetes:**
- Multiple kustomizations: `simplified`, `full`, `gitops`, `minimal`
- ArgoCD integration via `argocd-application.yaml`
- Health checks and sync wave annotations

**Version Management:**
- `VERSION` file (currently: 0.1.1)
- `pyproject.toml` version field

---

## Alternative Approaches

### Option 1: Enhanced GitHub Actions with Automated Manifest Updates

**Description:** Extend the existing CI/CD workflow to automatically update and commit manifest changes to the `ardenone-cluster` repository.

**Implementation:**
```yaml
# .github/workflows/ci-cd.yml (enhanced)
- name: Build and push images
  # Existing build step...

- name: Update manifests in ardenone-cluster
  run: |
    # Clone ardenone-cluster repo
    git clone https://github.com/jedarden/ardenone-cluster.git /tmp/ardenone-cluster
    cd /tmp/ardenone-cluster

    # Update image tags in manifests
    sed -i "s|newTag:.*|newTag: ${{ steps.version.outputs.tag }}|g" \
      cluster-configuration/apexalgo-iad/botburrow-agents/*.yaml

    # Commit and push
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git add cluster-configuration/apexalgo-iad/botburrow-agents/
    git commit -m "chore: Update botburrow-agents to ${{ steps.version.outputs.tag }}"
    git push
```

**Pros:**
- Eliminates manual manifest updates
- Ensures image tags stay synchronized
- Single git push triggers full deployment
- Reduces human error in manifest updates
- Maintains GitOps principles

**Cons:**
- Requires GitHub Actions PAT with write access to ardenone-cluster
- Cross-repo automation complexity
- Still requires ArgoCD to be functional
- Debugging cross-repo issues can be complex

**Risk Level:** Medium (cross-repo automation, credentials management)

**Suitable For:** Teams comfortable with cross-repo automation and using ArgoCD

---

### Option 2: Monorepo with GitOps

**Description:** Move Kubernetes manifests into the `botburrow-agents` repository, enabling true GitOps without cross-repo coordination.

**Implementation:**
```
botburrow-agents/
├── k8s/
│   ├── base/           # Base manifests
│   ├── overlays/
│   │   ├── apexalgo-iad/
│   │   └── ardenone/
│   └── helm-chart/     # Optional Helm chart
├── src/
├── tests/
└── .github/
    └── workflows/
        └── ci-cd.yml
```

**ArgoCD Application:**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: botburrow-agents
spec:
  source:
    repoURL: https://github.com/jedarden/botburrow-agents
    targetRevision: main
    path: k8s/overlays/apexalgo-iad
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**Pros:**
- Single source of truth for code and infrastructure
- Automatic GitOps sync on every push
- No cross-repo coordination needed
- Version tagging can trigger image updates
- Simplifies rollback (git revert)

**Cons:**
- Major repository restructuring
- Breaks existing ArgoCD ApplicationSet pattern
- May require team workflow changes
- Security concerns if manifests are in public repo

**Risk Level:** Medium (major restructuring)

**Suitable For:** Teams wanting simplified GitOps workflow

---

### Option 3: Semantic Release with Automated Versioning

**Description:** Implement semantic-release to automatically handle version bumps, CHANGELOG generation, and Git tags based on commit messages.

**Implementation:**
```yaml
# .releaserc
{
  "branches": ["main"],
  "plugins": [
    "@semantic-release/commit-analyzer",
    "@semantic-release/release-notes-generator",
    "@semantic-release/changelog",
    ["semantic-release-pypi", {
      "pypiPublish": false,
      "twineArguments": ["--repository", "botburrow"]
    }],
    "@semantic-release/git",
    "@semantic-release/github"
  ]
}
```

**Commit Conventions:**
```bash
git commit -m "feat: Add new activation handler"
git commit -m "fix: Resolve memory leak in coordinator"
git commit -m "chore: Update dependencies"
```

**Pros:**
- Automated version bumps (no manual VERSION file updates)
- Consistent versioning based on semantic versioning
- Automatic CHANGELOG generation
- Git tags created automatically
- Industry-standard approach

**Cons:**
- Requires team to follow commit conventions
- Additional tooling dependency
- Learning curve for semantic versioning
- May conflict with existing workflow

**Risk Level:** Low (tooling addition)

**Suitable For:** Teams wanting automated version management

---

### Option 4: Git Tag-Driven Deployment

**Description:** Trigger deployments only on Git tags, not on every push to main. Tags trigger both image build and ArgoCD sync.

**Implementation:**
```yaml
# .github/workflows/deploy.yml
on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    steps:
      - name: Extract version from tag
        run: echo "VERSION=${GITHUB_REF#refs/tags/}" >> $GITHUB_ENV
```

**ArgoCD Application:**
```yaml
spec:
  source:
    targetRevision: main  # Or specific tag for versioned deployments
```

**Workflow:**
```bash
# Development happens on main
git add .
git commit -m "feat: Add feature"
git push

# When ready to deploy:
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

**Pros:**
- Explicit deployment control (no accidental deployments)
- Tags provide natural version markers
- Can build multiple tags for different environments
- Simple to understand and implement

**Cons:**
- Requires manual tag creation step
- Tags can be forgotten
- Doesn't solve manifest update issue
- Still need separate manifest updates

**Risk Level:** Low

**Suitable For:** Teams wanting explicit deployment control

---

### Option 5: Kustomize Image Tag Automation

**Description:** Use ArgoCD's image update mechanism to automatically update image tags in Git without manual intervention.

**Implementation:**
```yaml
# ArgoCD Application with image auto-update
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: botburrow-agents
spec:
  source:
    repoURL: https://github.com/jedarden/ardenone-cluster
    targetRevision: main
    path: cluster-configuration/apexalgo-iad/botburrow-agents
  images:
  - name: ghcr.io/botburrow/botburrow-agents
    imageTag: latest  # ArgoCD can update this automatically
```

**Enable Image Updater:**
```yaml
# argocd-image-updater ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-image-updater-config
data:
  log.level: debug
  images:
  - image_name: ghcr.io/botburrow/botburrow-agents
    pull_secret: botburrow-agents-pull-secret
```

**Pros:**
- Automatic image tag updates in Git
- No manual manifest editing needed
- ArgoCD-managed (native integration)
- Supports multiple update strategies (latest, semantic)

**Cons:**
- Requires argocd-image-updater installation
- Adds complexity to ArgoCD setup
- Depends on ArgoCD being fully functional
- May create many git commits

**Risk Level:** Medium

**Suitable For:** Teams invested in ArgoCD ecosystem

---

### Option 6: Pre-Merge Deployment Verification

**Description:** Add deployment verification step that runs on pull requests before merge, ensuring deployment will succeed.

**Implementation:**
```yaml
# .github/workflows/pr-verification.yml
on:
  pull_request:
    branches: [main]
    paths:
      - 'k8s/**'
      - 'src/**'

jobs:
  verify-deployment:
    steps:
      - name: Build test image
        run: docker build -t test-image .

      - name: Dry-run kubectl apply
        run: |
          kubectl apply -k k8s/apexalgo-iad/ --dry-run=server

      - name: Validate manifests
        run: |
          kubeval k8s/apexalgo-iad/*.yaml

      - name: Check resource quotas
        run: |
          # Verify deployment fits within quotas
```

**Pros:**
- Catch deployment issues before merge
- Prevents broken deployments
- Increases confidence in changes
- Faster feedback for developers

**Cons:**
- Longer PR check times
- May require test cluster access
- Doesn't automate actual deployment
- Additional CI/CD complexity

**Risk Level:** Low

**Suitable For:** Teams wanting to reduce deployment failures

---

### Option 7: Blue-Green Deployment Strategy

**Description:** Implement blue-green deployments to eliminate activation processing interruption during rollouts.

**Implementation:**
```yaml
# Two deployments: botburrow-agents-blue and botburrow-agents-green
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: botburrow-agents
spec:
  strategy:
    blueGreen:
      activeService: botburrow-agents-active
      previewService: botburrow-agents-preview
      autoPromotionEnabled: false
      scaleDownDelaySeconds: 30
```

**Workflow:**
1. Deploy new version to "green" environment
2. Run smoke tests on green
3. Switch service selector from blue to green
4. Monitor for issues
5. Rollback by switching back to blue if needed

**Pros:**
- Zero downtime deployments
- Instant rollback capability
- Can test new version before switching traffic
- No activation processing interruption

**Cons:**
- Requires double resource capacity
- More complex deployment setup
- Requires Argo Rollouts or similar tool
- Higher infrastructure cost

**Risk Level:** Medium (complexity, cost)

**Suitable For:** Production systems requiring zero downtime

---

### Option 8: Simplified Single-Image Deployment

**Description:** Consolidate all components (coordinator, runners) into a single container image with role-based startup.

**Implementation:**
```dockerfile
# Single Dockerfile with multiple entrypoints
FROM python:3.12-slim
# ... install dependencies ...

ENTRYPOINT ["python", "-m", "botburrow_agents.cli"]

# Launch via command:
# botburrow-agents coordinator
# botburrow-agents runner --type hybrid
```

**Deployment:**
```yaml
# Single deployment with multiple replicas
apiVersion: apps/v1
kind: Deployment
metadata:
  name: botburrow-agents
spec:
  replicas: 5
  template:
    spec:
      containers:
      - name: agent
        command: ["botburrow-agents"]
        args: ["runner", "--mode", "$(RUNNER_MODE)"]
        env:
        - name: RUNNER_MODE
          valueFrom:
            configMapKeyRef:
              name: runner-config
              key: mode
```

**Pros:**
- Simpler build process (single image)
- Easier version management
- Reduced deployment complexity
- Lower registry storage costs

**Cons:**
- Less flexible scaling (can't scale coordinator vs runners independently)
- Single point of failure if image has issues
- May not fit current architecture
- Refactoring required

**Risk Level:** Medium (architectural change)

**Suitable For:** Teams wanting simpler deployment model

---

### Option 9: Automated Health Check Rollbacks

**Description:** Enhance existing health check infrastructure to automatically rollback deployments on failure detection.

**Implementation:**
```yaml
# Enhanced ArgoCD health checks
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: botburrow-agents-health-check
spec:
  metrics:
  - name: activation-processing
    interval: 30s
    count: 10
    failureLimit: 3
    provider:
      prometheus:
        address: http://prometheus.monitoring:9090
        query: |
          rate(botburrow_activations_processed_total[5m])
  - name: error-rate
    interval: 30s
    count: 10
    failureLimit: 3
    consecutiveErrorLimit: 2
    provider:
      prometheus:
        query: |
          rate(botburrow_errors_total[5m])
```

**Pros:**
- Automatic rollback on issues
- Reduced manual monitoring
- Faster failure detection
- Protects production from bad deployments

**Cons:**
- Requires Prometheus metrics
- Complex to configure correctly
- May rollback for transient issues
- Additional infrastructure dependency

**Risk Level:** Low (infrastructure improvement)

**Suitable For:** Production deployments requiring reliability

---

### Option 10: Staged Rollout with Progressive Delivery

**Description:** Implement progressive delivery using canary deployments or feature flags.

**Implementation (Canary):**
```yaml
# Argo Rollouts with canary
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: botburrow-agents
spec:
  strategy:
    canary:
      steps:
      - setWeight: 10
      - analysis:
          templates:
          - templateName: activation-rate-check
      - setWeight: 25
      - pause: {duration: 10m}
      - setWeight: 50
      - pause: {duration: 10m}
      - setWeight: 100
```

**Pros:**
- Gradual rollout reduces risk
- Can test new versions with real traffic
- Automatic rollback if issues detected
- Fine-grained control over rollout

**Cons:**
- More complex deployment setup
- Requires Argo Rollouts
- Longer rollout duration
- Additional monitoring requirements

**Risk Level:** Medium

**Suitable For:** Critical production deployments

---

## Comparison Matrix

| Approach | Automation | GitOps | Complexity | Risk | Time Saved |
|----------|------------|--------|------------|------|------------|
| 1. Enhanced GitHub Actions | High | Yes | Medium | Medium | High |
| 2. Monorepo | High | Yes | High | Medium | High |
| 3. Semantic Release | Medium | Yes | Low | Low | Medium |
| 4. Git Tag-Driven | Low | Yes | Low | Low | None |
| 5. Kustomize Auto-Update | High | Yes | Medium | Medium | High |
| 6. Pre-Merge Verification | Medium | Yes | Low | Low | Medium |
| 7. Blue-Green | High | Yes | High | Medium | None |
| 8. Single Image | High | Partial | Medium | Medium | Medium |
| 9. Auto Rollback | High | Yes | Low | Low | Medium |
| 10. Progressive Delivery | High | Yes | High | Medium | None |

---

## Recommendations

### Quick Win: **Option 3 (Semantic Release)**

**Rationale:**
- Low risk, easy to implement
- Automates VERSION file updates
- Industry-standard approach
- Minimal workflow disruption

**Implementation Steps:**
```bash
npm install -D semantic-release @semantic-release/git @semantic-release/changelog
# Create .releaserc with configuration
# Update commit conventions
# Enable GitHub Actions workflow
```

---

### Medium-Term: **Option 1 (Enhanced GitHub Actions)**

**Rationale:**
- Eliminates manual manifest updates
- Leverages existing CI/CD infrastructure
- Maintains GitOps principles
- High time savings

**Implementation Steps:**
1. Create GitHub PAT with write access to `ardenone-cluster`
2. Add PAT to botburrow-agents repository secrets
3. Update `.github/workflows/ci-cd.yml` with manifest update step
4. Test with dry-run mode first

---

### Long-Term: **Option 2 (Monorepo) or Option 5 (Kustomize Auto-Update)**

**Rationale:**
- True GitOps with single source of truth
- Eliminates cross-repo coordination entirely
- Simplifies long-term maintenance
- Industry best practice

**Decision Factors:**
- Choose **Monorepo** if team can handle repository restructuring
- Choose **Kustomize Auto-Update** if ArgoCD is working well

---

## Implementation Path (Recommended)

### Phase 1: Immediate Improvements (Week 1)
1. **Implement Semantic Release** (Option 3)
   - Automate version bumps
   - Generate CHANGELOG
   - Remove manual VERSION updates

2. **Add Pre-Merge Verification** (Option 6)
   - Dry-run kubectl apply on PRs
   - Validate manifests
   - Catch issues early

### Phase 2: Automation (Week 2-3)
3. **Enhanced GitHub Actions** (Option 1)
   - Automate manifest updates
   - Cross-repo automation
   - Reduce manual steps

### Phase 3: Reliability (Week 4)
4. **Auto Rollback** (Option 9)
   - Implement health check analysis
   - Automatic rollback on failure
   - Protect production

### Phase 4: Advanced (Future)
5. **Monorepo Migration** (Option 2) OR **Kustomize Auto-Update** (Option 5)
   - True GitOps
   - Single source of truth
   - Simplified operations

---

## Risk Mitigation

### Cross-Repo Automation (Option 1)
- Use GitHub App instead of PAT for better security
- Implement dry-run mode for testing
- Add approval gates for critical changes
- Monitor automation logs

### Monorepo Migration (Option 2)
- Plan migration carefully with team
- Test in separate branch first
- Ensure RBAC permissions are correct
- Document new workflow

### Semantic Release (Option 3)
- Train team on commit conventions
- Enable commitlint to enforce conventions
- Start with automated release notes only
- Gradually enable full automation

---

## Success Criteria

Implementing these alternatives should result in:

1. **Reduced Deployment Time:** From 15-30 minutes to <5 minutes
2. **Fewer Manual Steps:** From 5-6 touch points to 1-2
3. **Reduced Human Error:** Automated version tags and manifest updates
4. **Better Reliability:** Health checks and auto-rollback
5. **Improved Developer Experience:** Clear commit conventions, automated changelog

---

## Appendix: Example Workflow Comparison

### Current Workflow (bd-13j)
```bash
# 1. Make code changes
vim src/botburrow_agents/coordinator/main.py

# 2. Update VERSION (manual)
echo "0.1.2" > VERSION

# 3. Run tests (manual)
pytest tests/

# 4. Commit and push (manual)
git add .
git commit -m "feat: Add new feature"
git push

# 5. Wait 5 min for CI/CD build...
# 6. Verify images pushed (manual)
docker pull ghcr.io/botburrow/botburrow-agents:latest

# 7. Update manifests in ANOTHER repo (manual)
cd ../ardenone-cluster
vim cluster-configuration/apexalgo-iad/botburrow-agents/coordinator.yaml
git add .
git commit -m "chore: Update image tag"
git push

# 8. Wait for ArgoCD sync...
# 9. Monitor rolling update (manual)
kubectl get pods -n botburrow-agents -w

# 10. Verify service health (manual)
./scripts/verify-deployment.sh
```

### Proposed Workflow (with Options 1 + 3)
```bash
# 1. Make code changes
vim src/botburrow_agents/coordinator/main.py

# 2. Commit with semantic message (VERSION automated)
git add .
git commit -m "feat: Add new activation handler"

# 3. Run tests (automated in PR checks)
# Tests run automatically in GitHub Actions

# 4. Push (triggers everything)
git push

# Done! CI/CD automatically:
# - Bumps version to 0.2.0
# - Runs tests
# - Builds image
# - Updates manifests in ardenone-cluster
# - ArgoCD syncs automatically

# 5. Monitor (optional)
kubectl get pods -n botburrow-agents
```

---

**Document Status:** Complete
**Next Action:** Human review and decision on implementation path
