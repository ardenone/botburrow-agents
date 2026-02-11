# Forgejo CrashLoopBackOff Fix - Analysis

## Problem
Forgejo deployment was failing with error:
```
s6-svscan: fatal: unable to open .s6-svscan/lock: Permission denied
```

## Root Cause
The container-level `securityContext` with `runAsUser: 1000` was forcing the container to run as UID 1000, but the Forgejo image (based on s6-overlay v3) has its own built-in user configuration that s6-overlay expects. When forced to run as a different user, s6-svscan could not create its runtime lock files.

## Solution
Removed the container-level `securityContext` from the forgejo container, allowing the image to use its default user configuration. The pod-level `fsGroup: 1000` ensures that volume ownership is still managed correctly for persistent data.

## Changes Made
1. Added `/run` volume mount for s6-overlay runtime state
2. Set `workingDir: /data` to ensure s6 has a writable directory
3. Pre-created `.s6-svscan` directory in init container
4. **Removed container-level securityContext** (final fix)

## Lessons Learned
- Container images with built-in init systems (like s6-overlay) may have specific user expectations
- Forcing a different user via securityContext can break init system functionality
- Let the image use its default user when the image manages its own user configuration
- Pod-level fsGroup is sufficient for volume ownership management

## Verification
```
$ kubectl get pods -n forgejo
NAME                       READY   STATUS    RESTARTS   AGE
forgejo-6bb5498f47-bj5gj   2/2     Running   0          2m

$ kubectl logs -n forgejo forgejo-6bb5498f47-bj5gj -c forgejo --tail=5
2026/02/11 03:58:20 ...go:102:func1() [I] router: completed GET /api/v1/version for x.x.x.x:47858, 200 OK
```

Forgejo is now successfully running and responding to API requests.
