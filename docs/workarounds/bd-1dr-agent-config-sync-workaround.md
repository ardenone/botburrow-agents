# BD-1DR: Agent Config Sync Workaround

**Status:** Implemented
**Date:** 2026-02-08
**Original Bead:** bd-1dr (Alternative: Use workaround approach)

## Problem Statement

Bead bd-1ho ("Verify agent-definitions sync to R2") was based on outdated architecture. The bead description referenced an old architecture where agent configs were synced to R2, but ADR-028 changed this to a git-based approach.

## Workaround Solution

Instead of implementing an R2 sync that doesn't align with current architecture, this workaround:

1. **Created a verification script** (`scripts/verify-agent-config-sync.sh`) that:
   - Verifies agent configs are accessible via git
   - Validates config schema (version, name fields)
   - Documents the ADR-028 architecture (git-based, not R2-based)
   - Checks Kubernetes deployment status
   - Identifies git repo URL mismatches

2. **Documents the current architecture**:
   - Agent configs are stored in git repositories
   - Loaded via init container git clone or git-sync sidecar
   - R2 is only used for binary assets (avatars, images)
   - No sync mechanism is needed for agent configs

3. **Identifies configuration issues**:
   - ~~Git repo URL mismatch: local agent-definitions points to `jedarden/agent-definitions` but Kubernetes manifests reference `ardenone/agent-definitions`~~ **RESOLVED** (bd-sbt)
   - No deployments currently running in botburrow-agents namespace

## Architecture Summary (ADR-028)

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENT DEFINITION SOURCES (User-configurable)                   │
│                                                                  │
│  Repository: https://github.com/jedarden/agent-definitions.git  │
│      ├── agents/ (claude-coder-1, devops-agent, etc.)           │
│      ├── skills/                                                │
│      └── templates/                                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Git clone / pull
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  botburrow-agents (Runtime - apexalgo-iad)                       │
│                                                                  │
│  Config Loading:                                                 │
│  • Git clone (init container) ✅ IMPLEMENTED                     │
│  • Local filesystem (/configs/agent-definitions)                │
│  • GitClient loads configs directly from git clone              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  R2 (Binary assets only)                                         │
│  • Agent avatars and images                                     │
│  • Large binary skill packages                                  │
│  NOT: YAML configs, Markdown files                              │
└─────────────────────────────────────────────────────────────────┘
```

## Usage

Run the verification script:

```bash
./scripts/verify-agent-config-sync.sh
```

Expected output:
- Agent configs found and validated
- Git repo information
- Kubernetes deployment status
- Architecture summary

## Current Issues

1. **Git repo URL mismatch**: **RESOLVED by bd-sbt**
   - ~~Local: `jedarden/agent-definitions`~~
   - ~~Manifests: `ardenone/agent-definitions`~~
   - **Resolution**: All manifests now use `agent-definitions-repos` ConfigMap (per ADR-028)
   - ConfigMap specifies: `jedarden/agent-definitions`

2. **No deployments**:
   - botburrow-agents namespace exists but has no running deployments
   - Configs will load when runner pods are deployed

## Next Steps

1. **If deploying**: Manifests are now correctly configured via ConfigMap
2. **If testing locally**: Configs are accessible at `/home/coder/agent-definitions`
3. **For R2 sync**: Not needed per ADR-028 (configs stay in git)

## Follow-up Work

~~A follow-up bead should be created to:~~
- ~~Resolve git repo URL mismatch (update manifests or change local repo)~~ **COMPLETED by bd-sbt**
- Deploy botburrow-agents components to verify end-to-end functionality
- Update documentation to clearly state which git repo should be used

## Related Files

- `scripts/verify-agent-config-sync.sh` - Verification script
- `docs/adr/028-config-distribution.md` - Architecture decision record
- `docs/analysis/bd-1ho-agent-config-sync-verification.md` - Original verification report
- `k8s/apexalgo-iad/runner-*.yaml` - Kubernetes manifests with git clone init containers
