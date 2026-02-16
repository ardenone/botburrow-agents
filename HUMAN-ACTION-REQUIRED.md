# 🚨 HUMAN ACTION REQUIRED

**Bead:** bd-3h3 - Update Docker Hub credentials (PAT required)
**Status:** Ready for human action
**Time:** 5-10 minutes

## Quick Start

See: `docs/fixes/bd-3h3-ACTIONABLE-SUMMARY.md`

## 5-Step Checklist

1. **Create Docker Hub PAT** (2 min)
   - URL: https://hub.docker.com/settings/security
   - Permissions: Read & Write
   - Name: github-actions-botburrow-agents

2. **Verify repository** (30 sec)
   - URL: https://hub.docker.com/u/ardenone
   - Repository: ardenone/botburrow-agents

3. **Update GitHub secret** (1 min)
   - URL: https://github.com/ardenone/botburrow-agents/settings/secrets/actions
   - Secret: DOCKERHUB_PASSWORD
   - Value: [PAT from step 1]

4. **Test workflow** (2 min)
   ```bash
   gh workflow run ci-cd.yml
   gh run watch
   ```

5. **Close bead** (10 sec)
   ```bash
   br close bd-3h3 --status completed
   ```

## Current Error

```
ERROR: failed to push docker.io/ardenone/botburrow-agents:b78a18d:
push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

**Latest Failed Run:** https://github.com/ardenone/botburrow-agents/actions/runs/22049644452

## Why This Requires Human

Workers cannot:
- Log into Docker Hub web UI
- Update GitHub repository secrets
- Create Personal Access Tokens

## Documentation

- **Quick Summary:** docs/fixes/bd-3h3-ACTIONABLE-SUMMARY.md
- **Detailed Guide:** docs/fixes/bd-3h3-HUMAN-ACTION-GUIDE.md
- **Root Cause:** docs/fixes/bd-31j-dockerhub-auth-analysis.md

---

**Worker:** Claude Sonnet 4.5
**Last Update:** 2026-02-16 04:02 UTC
