# BD-1CO Forgejo Blocker Analysis
**Date:** 2026-02-11
**Issue:** Forgejo mirror-setup sidecar failing to create repos/org

## Current Status

✅ **Manifest URLs fixed:** Changed from `ardenone/agent-definitions` to `botburrow/agent-definitions`  
❌ **Forgejo mirror-setup failing:** Admin token and org creation not working  
❌ **Repositories not accessible:** `botburrow/agent-definitions` returns 404

## Root Cause

The Forgejo `mirror-setup` sidecar (deployment.yaml:127-278) is encountering API failures:

### Error 1: Admin Token Generation Failed
```bash
{"message":"token is required","url":"https://botburrow-git.ardenone.com/api/swagger"}
```

The sidecar tries to generate an admin token (line 153-160):
```bash
TOKEN=$(forgejo admin user generate-access-token \
    --username "$FORGEJO_ADMIN_USER" \
    --token-name "mirror-setup" \
    --scopes "all" 2>/dev/null | sed 's/^.*: //' || echo "")
```

This command is failing, likely because:
1. Admin user doesn't exist yet
2. Admin user creation is failing due to permission errors (line 214):
   ```
   2026/02/11 03:57:14 Forgejo is not supposed to be run as root. Sorry.
   ```

### Error 2: Organization Creation Failed
```bash
curl -s -X POST "http://localhost:3000/api/v1/orgs" \
    -H "Authorization: token $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"username": "botburrow", "visibility": "public"}' || echo "Org may exist"

Response: {"message":"GetUserByName","url":"...","errors":["user redirect does not exist [name: botburrow]"]}
```

Without a valid admin token, the org creation API call fails.

### Error 3: Repository Migration Failing
```bash
curl -s -X POST "http://localhost:3000/api/v1/repos/migrate" ...
Response: {"message":"token is required"}
```

Without a valid token, repository migration from GitHub fails.

## Forgejo Deployment Issues

### Issue 1: Running as Root
```
Forgejo is not supposed to be run as root. Sorry.
```

The `forgejo admin user create` command is being run by a sidecar that doesn't have the correct user context.

### Issue 2: Token Persistence
The sidecar tries to save tokens to `/data/gitea/.admin-token` (line 159), but this file may not persist or may not be readable due to permission issues.

### Issue 3: No Fallback
If token generation fails, the script uses `$FORGEJO_ADMIN_TOKEN` from secrets (line 166), but this may not be set or may be invalid.

## Proposed Solutions

### Option 1: Manual Repository Setup (Quick Fix)
Manually access Forgejo UI and:
1. Create `botburrow` organization
2. Create `agent-definitions` repository under `botburrow`
3. Configure it as a mirror from GitHub `jedarden/agent-definitions`

**Pros:** Immediate unblock for bd-1co  
**Cons:** Doesn't fix automation, manual intervention needed

### Option 2: Fix mirror-setup Sidecar Permissions
Update deployment.yaml to run mirror-setup commands with correct user context:
```yaml
- name: mirror-setup
  securityContext:
    runAsUser: 1000  # Match Forgejo user
    runAsGroup: 1000
```

Also ensure the admin token is pre-generated and stored in secrets.

**Pros:** Fixes automation permanently  
**Cons:** Requires understanding Forgejo's permission model

### Option 3: Use Forgejo CLI from Main Container
Instead of a sidecar, use an init container or startup script inside the main Forgejo container to:
1. Wait for Forgejo to start
2. Run admin commands with proper context
3. Create org and repos using API with admin credentials

**Pros:** Correct execution context  
**Cons:** More complex startup sequence

## Recommended Approach

**Immediate:** Option 1 - Manual setup to unblock bd-1co  
**Long-term:** Option 2 or 3 - Fix automation

## Next Steps

1. Create human bead to manually setup Forgejo repos (BLOCKER for bd-1co)
2. Verify manual setup allows botburrow-agents to clone successfully
3. Create separate bead to fix Forgejo mirror-setup automation (lower priority)

## Verification Commands

Once fixed, verify with:
```bash
# Check if org exists
curl -s "http://forgejo.forgejo.svc.cluster.local:3000/api/v1/orgs/botburrow"

# Check if repo exists
curl -s "http://forgejo.forgejo.svc.cluster.local:3000/api/v1/repos/botburrow/agent-definitions"

# Test git clone
kubectl run test-clone --rm -i --restart=Never --image=alpine/git:latest -- \
  git ls-remote http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git
```
