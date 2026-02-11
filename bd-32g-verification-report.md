# bd-32g Verification Report: botburrow-agents Pod Status

**Date:** 2026-02-11
**Worker:** claude-code-sonnet
**Bead:** bd-32g (Verify botburrow-agents pods start successfully)

---

## Executive Summary

**Status:** ❌ BLOCKED - Pods still failing after prerequisite beads marked closed
**Root Cause:** Prerequisites NOT actually completed (beads closed prematurely)

### Current Pod Status
```
NAME                                    READY   STATUS
coordinator-7c895c5d75-2c7h7            0/1     Init:CrashLoopBackOff
coordinator-git-sync-546b455d8c-tltpr   0/2     ImagePullBackOff
runner-exploration-6fbf8fcbdf-km85p     0/1     Init:CrashLoopBackOff
runner-git-sync-6cb8cf8745-xsp2x        1/2     ImagePullBackOff
runner-hybrid-678744589f-7pddp          0/1     Init:CrashLoopBackOff
runner-notification-5b4f9c8754-dj9g4    0/1     Init:CrashLoopBackOff
skill-sync-bf4cb6649-5v9k2              0/1     ImagePullBackOff
valkey-d4fc4c84d-ttdzw                  1/1     Running ✅
```

---

## Issue #1: ArgoCD Not Synced ❌

### Problem
Manifests in git were updated (commit 47cb246d3) but running deployments still use old image.

**Git Manifest (correct):**
```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

**Running Deployment (incorrect):**
```yaml
image: docker.io/ronaldraygun/botburrow-agents:latest
```

### Evidence
```bash
# Git manifest check
$ grep "image:" /home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/*.yaml
image: ghcr.io/ardenone/botburrow-agents:latest  # ✅ Correct in git

# Running deployment check
$ kubectl get deployment coordinator -n botburrow-agents -o jsonpath='{.spec.template.spec.containers[0].image}'
docker.io/ronaldraygun/botburrow-agents:latest  # ❌ Wrong in cluster
```

### Impact
- All main container images fail to pull: "authorization failed, repository does not exist"
- Pods stuck in ImagePullBackOff

### Required Action
**BLOCKER:** ArgoCD sync required for botburrow-agents Application

---

## Issue #2: Forgejo Repository Not Found ❌

### Problem
Init containers fail to clone agent-definitions from Forgejo.

**Error:**
```
Cloning into '/configs/agent-definitions'...
remote: Not found.
fatal: repository 'http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git/' not found
```

### Evidence
```bash
$ kubectl logs coordinator-7c895c5d75-2c7h7 -n botburrow-agents -c git-clone --tail=5
Cloning into '/configs/agent-definitions'...
remote: Not found.
fatal: repository 'http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git/' not found
```

### Root Cause
Bead bd-13t was marked CLOSED with "waiting-human" label, meaning the manual Forgejo setup is still pending.

**Status:** bd-13t shows "verified" label but repository still doesn't exist.

### Impact
- All pods with git-clone init containers fail (coordinators, runners)
- Pods stuck in Init:CrashLoopBackOff

### Required Action
**BLOCKER:** Human must manually create botburrow org and agent-definitions repo in Forgejo

---

## Blockers Summary

| Blocker | Type | Description | Owner |
|---------|------|-------------|-------|
| ArgoCD sync | Automation | Sync botburrow-agents Application | Worker |
| Forgejo repo | Manual Setup | Create botburrow/agent-definitions | Human (bd-13t) |

---

## Recommended Resolution

### Step 1: Trigger ArgoCD Sync
Try to trigger sync for botburrow-agents Application via ArgoCD API or CLI.

### Step 2: Verify Images Exist
Check if ghcr.io/ardenone/botburrow-agents:latest is pullable.

### Step 3: Wait for Forgejo
bd-13t is already marked "waiting-human" - human action required.

---

## Validation Commands

```bash
# Check pod status
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get pods -n botburrow-agents

# Check deployment images
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get deployment -n botburrow-agents -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.template.spec.containers[0].image}{"\n"}{end}'

# Check init container logs
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig logs <pod-name> -n botburrow-agents -c git-clone

# Verify Forgejo repo exists
curl -I http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions
```
