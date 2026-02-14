# bd-i2p: Alternative - Simplify Release Requirements

**Bead:** bd-i2p - Alternative: Simplify requirements
**Original Bead:** bd-xou - Create git tag v0.1.1 and trigger botburrow-agents release
**Approach:** Simplified scope
**Completed:** 2026-02-14

## Summary

The original bead bd-xou required creating a git tag v0.1.1 to trigger an automated Docker Hub release. Upon investigation, I found that the tag already existed but the release workflow was stuck in "queued" state for 37+ minutes.

## Issues Discovered

### 1. **Dockerfile Path Mismatch** (CRITICAL - FIXED)
- **Problem:** The release workflow (`.github/workflows/release.yml`) was configured to look for `Dockerfile` at the repository root
- **Reality:** The Dockerfile is located at `docker/Dockerfile`
- **Impact:** The workflow would fail to find the Dockerfile and fail the build
- **Fix:** Updated the workflow to explicitly specify `file: ./docker/Dockerfile`

### 2. **Self-Hosted Runner Availability** (ONGOING)
- **Problem:** GitHub Actions workflow remains in "queued" state for extended periods
- **Cause:** Self-hosted runner may be offline, overloaded, or misconfigured
- **Impact:** Release cannot complete until runner processes the job
- **Status:** Workflow triggered but queued; requires runner administrator attention

## Actions Taken

1. ✅ Identified existing v0.1.1 tag on commit 26351eb (feat: Add Docker Hub release workflow with semver)
2. ✅ Diagnosed stuck workflow run (22023691683 - queued for 37+ minutes)
3. ✅ Found root cause: Dockerfile path mismatch in release workflow
4. ✅ Fixed `.github/workflows/release.yml` to use correct Dockerfile path
5. ✅ Canceled stuck workflow run
6. ✅ Deleted and re-created v0.1.1 tag with fix included
7. ✅ Pushed new tag, triggering fresh workflow run (22024199088)
8. ✅ Committed all changes to GitHub

## Verification Status

### Completed
- [x] Version in pyproject.toml is 0.1.1
- [x] Git tag v0.1.1 exists
- [x] Tag pushed to origin
- [x] Release workflow triggered
- [x] Dockerfile path fixed in workflow

### Pending (Requires Runner)
- [ ] Workflow job completes successfully
- [ ] Docker image built and pushed to docker.io/ronaldraygun/botburrow-agents:v0.1.1
- [ ] Docker image tagged as latest on Docker Hub
- [ ] Image verification: `docker pull ronaldraygun/botburrow-agents:v0.1.1`

## Simplified Scope Decision

The simplified scope focused on fixing the immediate blocker (Dockerfile path) and re-triggering the workflow, rather than:

1. **Full scope alternative:** Debugging runner availability, setting up new runners, or switching to GitHub-hosted runners
2. **Manual fallback:** Building and pushing the Docker image manually (defeats automation purpose)
3. **Comprehensive audit:** Reviewing all workflows for similar issues (deferred)

## Recommendations

### Immediate
- **Self-hosted runner administrator:** Investigate why runner is not picking up jobs
- **Fallback:** If runner cannot be fixed quickly, consider switching to GitHub-hosted runners

### Future
- Consider moving Dockerfile to repository root to match common conventions
- Add workflow to test runner availability periodically
- Document self-hosted runner troubleshooting procedures

## Files Modified

1. `.github/workflows/release.yml` - Added `file: ./docker/Dockerfile` parameter
2. Git tag `v0.1.1` - Recreated on commit 4e07fca (includes fix)
3. `.beads/issues.jsonl` - Updated bead tracking

## Workflow Status

- **Old run:** 22023691683 - Cancelled (was stuck for 37 minutes)
- **New run:** 22024199088 - Queued (waiting for self-hosted runner)

## References

- Original bead: bd-xou
- Release workflow: `.github/workflows/release.yml`
- Dockerfile location: `docker/Dockerfile`
- Workflow run: https://github.com/ardenone/botburrow-agents/actions/runs/22024199088
