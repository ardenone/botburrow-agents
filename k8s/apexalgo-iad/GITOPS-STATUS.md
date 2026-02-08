# ArgoCD GitOps Status Update for bd-3kh

**Date**: 2026-02-08
**Bead**: bd-3kh - Fix ArgoCD ApplicationSet sync for botburrow-agents deployment
**Status**: In Progress - Pending ArgoCD sync verification

## Summary of Investigation

### Architecture Discovery

1. **ArgoCD Location**: ArgoCD is NOT installed in either ardenone-cluster or apexalgo-iad clusters. It runs externally and manages these clusters as remote destinations.

2. **ApplicationSet Location**: The ArgoCD ApplicationSet is configured in the `ardenone-cluster` repository:
   - Path: `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/apexalgo-iad-applicationset.yml`
   - Repository: https://github.com/ardenone/ardenone-cluster

3. **ApplicationSet Generator**: Uses Git directory generator to scan `cluster-configuration/apexalgo-iad/*` directories and creates Applications named `{{path.basename}}-ns-apexalgo-iad`

4. **Application Naming**: For `botburrow-agents` directory, the Application is named `botburrow-agents-ns-apexalgo-iad`

### Root Cause Analysis

The botburrow-agents namespace exists with ArgoCD tracking annotations but contains zero resources. Investigation revealed:

1. **Namespace Created Successfully**: The namespace `botburrow-agents` exists in apexalgo-iad cluster with annotation:
   ```
   argocd.argoproj.io/tracking-id: botburrow-agents-ns-apexalgo-iad:/Namespace:/botburrow-agents
   ```
   This confirms ArgoCD ApplicationSet created the namespace.

2. **Resources Not Deployed**: Despite the namespace existing, no other resources (Deployments, Services, etc.) are present.

3. **Configuration Issues Found and Fixed**:
   - **Issue 1**: A `kustomization.yaml` file was present in the directory, which is incompatible with ArgoCD's directory mode (where kustomization.yaml is treated as a regular resource and fails).
     - **Fix**: Removed kustomization.yaml

   - **Issue 2**: ServiceMonitor resources require `monitoring.coreos.com/v1` CRD which is not installed in apexalgo-iad cluster.
     - **Fix**: Renamed servicemonitor.yaml to servicemonitor.yaml.disabled

4. **SealedSecret Permission Issue**: The botburrow-agents-sealedsecret.yml exists but cannot be applied by the devpod-observer service account due to RBAC restrictions. This must be applied by ArgoCD (which has appropriate permissions).

### Changes Made

**ardenone-cluster repository commits**:
1. `f66d708d9` - Added kustomization.yaml (later reverted)
2. `88cd29f47` - Added SealedSecret to kustomization resources (later reverted)
3. `be819f30e` - Removed kustomization.yaml and disabled ServiceMonitor

### Current State

**Files in ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/**:
```
botburrow-agents-sealedsecret.yml  # SealedSecret for botburrow-agents secrets
configmap.yaml                      # ConfigMaps for configuration
coordinator-git-sync.yaml          # Git-sync coordinator deployment
coordinator.yaml                    # Coordinator deployment
hpa.yaml                           # HorizontalPodAutoscaler resources
namespace.yml                      # Namespace definition (already applied)
rbac.yaml                          # RBAC (ServiceAccount, Role, RoleBinding)
runner-exploration.yaml            # Exploration runner deployment
runner-git-sync.yaml               # Git-sync runner deployment
runner-hybrid.yaml                 # Hybrid runner deployment
runner-notification.yaml           # Notification runner deployment
skill-sync.yaml                    # Skill sync deployment
valkey.yaml                        # Valkey (Redis) deployment and service
servicemonitor.yaml.disabled       # Disabled (CRD not installed)
```

All remaining YAML files pass `kubectl --dry-run=client` validation.

### Verification Needed

Since ArgoCD is running externally and we don't have direct API access, the following needs to be verified:

1. **Check ArgoCD Application Status**:
   ```bash
   # From a system with ArgoCD CLI access:
   argocd app get botburrow-agents-ns-apexalgo-iad
   argocd app sync botburrow-agents-ns-apexalgo-iad
   ```

2. **Check Application Sync Status**:
   - Verify the Application is not in an error state
   - Check if there are any sync errors preventing resource deployment
   - Verify the SealedSecret was applied successfully (it should create the `botburrow-agents-secrets` Secret)

3. **Check Resource Status in apexalgo-iad**:
   ```bash
   export KUBECONFIG=/path/to/apexalgo-iad.kubeconfig
   kubectl get all -n botburrow-agents
   kubectl get sealedsecrets -n botburrow-agents
   kubectl get secrets -n botburrow-agents
   ```

### Possible Remaining Issues

1. **SealedSecret Controller**: Verify SealedSecret controller is running in apexalgo-iad cluster
   ```bash
   kubectl get pods -n sealed-secrets
   ```

2. **Application Sync Errors**: The ArgoCD Application might be in a failed state due to:
   - Permission issues
   - Invalid manifests
   - Prerequisite resources not available

3. **ArgoCD Sync Wave Issues**: Resources might be stuck waiting for dependencies

### Next Steps

1. **Direct ArgoCD Access**: Need access to ArgoCD UI or CLI to check Application status and trigger manual sync if needed

2. **Manual Verification**: If ArgoCD still doesn't sync after fixes, manually apply resources:
   ```bash
   export KUBECONFIG=/path/to/apexalgo-iad.kubeconfig
   kubectl apply -f /home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/
   ```

3. **Consider Alternative Approach**: If ArgoCD continues to have issues, the workaround deployment script (`scripts/deploy-workaround.sh`) can be used until ArgoCD is fixed.

### Related Beads

- **bd-3kh**: Current bead - Fix ArgoCD ApplicationSet sync
- **bd-1v9**: Original bead - Fix botburrow-agents deployment via ArgoCD
- **bd-cni**: Workaround deployment - kubectl-based deployment script
- **bd-3e3**: Infrastructure readiness and credential configuration

### Files Modified

1. `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/`:
   - Removed: kustomization.yaml
   - Renamed: servicemonitor.yaml → servicemonitor.yaml.disabled

2. Commits pushed to ardenone-cluster repository:
   - `f66d708d9`: feat(bd-3kh): Add kustomization.yaml to fix ArgoCD ApplicationSet sync
   - `88cd29f47`: fix(bd-3kh): Add SealedSecret to kustomization resources
   - `be819f30e`: fix(bd-3kh): Remove kustomization and disable ServiceMonitor for directory mode

## Conclusion

The root cause of the ArgoCD sync failure was identified as incompatible resources (kustomization.yaml in directory mode, ServiceMonitor without CRD). These have been fixed and committed to the ardenone-cluster repository.

However, without direct access to ArgoCD to verify the sync status and trigger a manual sync if needed, we cannot confirm that resources are being deployed. The next step requires either:
1. Direct ArgoCD access to check/trigger sync
2. Waiting for ArgoCD's automatic sync cycle (typically 3-5 minutes)
3. Manual deployment using the workaround script if urgent

The namespace exists with correct ArgoCD tracking annotations, indicating the ApplicationSet is functional. The fixes applied should resolve the sync issues.
