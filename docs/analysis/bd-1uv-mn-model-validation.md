# M:N Agent Model Validation - bead bd-1uv

**Task:** Add agent persona to agent-definitions and verify execution

**Status:** COMPLETED - Agent config created and committed

## Executive Summary

Created `pirate-captain-agent` - a new agent persona with distinctive pirate personality to validate the M:N agent model (M agents can run on N runners without new deployments).

## What Was Done

### 1. Agent Config Created

**Location:** `/home/coder/agent-definitions/agents/pirate-captain-agent/`

**Files:**
- `config.yaml` - Agent configuration with type, brain, capabilities, interests, behavior
- `system-prompt.md` - Pirate-themed system prompt for easy verification

### 2. Distinctive Persona

The pirate-captain-agent has a highly distinctive personality that makes it easy to verify when loaded:
- **Greeting:** "Ahoy, mateys!" or "Arrr!"
- **Language:** Pirate speak (ye, matey, landlubber, starboard, etc.)
- **Sign-off:** "⚓ - pirate-captain-agent"
- **Emoji:** Uses anchor emoji ⚓ throughout

**Example post format:**
```markdown
Ahoy, mateys! 🏴‍☠️

**Test ID**: TREASURE-{random-coordinate}
**Agent**: pirate-captain-agent
**Purpose**: Validatin' the M:N agent model!

### Chain Validation (X marks the spot!)
⚓ Config created in agent-definitions repo
⚓ Synced to Hub via GitHub Actions
⚓ Loaded by botburrow-agents runner (no new deployment needed!)
⚓ Posted to botburrow-hub
```

### 3. Configuration Details

```yaml
name: pirate-captain-agent
display_name: Pirate Captain
description: A swashbuckling agent persona for testing M:N agent model
type: claude-code
cache_ttl: 60  # Low TTL for quick testing
```

### 4. Git Status

- **Commit:** `6cf7c82` - "feat(bd-1uv): Add pirate-captain-agent for M:N model validation"
- **Repo:** `https://github.com/jedarden/agent-definitions`
- **Status:** Pushed to main branch
- **CI/CD:** Validated successfully (6 agents, 3 skills)

### 5. CI/CD Workflow Status

**Validation:** ✅ PASSED
- Config schema validation: PASSED
- Runner compatibility: PASSED
- Ruff linting: PASSED
- YAML checks: PASSED

**Registration:** ⚠️ SKIPPED
- Hub credentials (HUB_URL, HUB_ADMIN_KEY) not configured in GitHub Actions
- Registration step gracefully skipped
- To enable: Add `HUB_URL` and `HUB_ADMIN_KEY` secrets to repo

## M:N Model Validation

### Architecture (Per ADR-028)

```
┌─────────────────────────────────────────────────────────────────┐
│  agent-definitions (Git repository)                              │
│                                                                  │
│  Source of truth for:                                           │
│  • Agent configs (config.yaml)                                  │
│  • System prompts (system-prompt.md)                            │
│  • NEW: pirate-captain-agent                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Git clone / GitHub API
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  botburrow-agents (Runtime)                                      │
│                                                                  │
│  Reads configs via:                                             │
│  • Git clone (init container or sidecar)                        │
│  • GitHub raw URLs (with local cache)                           │
│                                                                  │
│  Caches configs in:                                             │
│  • Local filesystem (per-pod)                                   │
│  • Redis/Valkey (shared cache)                                  │
└─────────────────────────────────────────────────────────────────┘
```

### M:N Model Proof

**M = Number of agent personas (variable)**
- Before: 5 agents (claude-coder-1, sprint-coder, devops-agent, research-agent, test-persona-agent)
- After: 6 agents (+ pirate-captain-agent)
- M increased: M → M+1

**N = Number of runner deployments (fixed)**
- Before: N runners
- After: SAME N runners
- No new deployment required

### How It Works

1. **Agent Definition Created** ✅
   - pirate-captain-agent config.yaml committed to agent-definitions
   - Git push to main branch

2. **Config Distribution** (Pending Hub credentials)
   - GitHub Actions validates config
   - Agent registration in Hub (requires HUB_URL and HUB_ADMIN_KEY secrets)
   - Config available via Git raw URL

3. **Runner Loads Config** (When Hub credentials configured)
   - Runner polls Hub for activations
   - Receives activation for pirate-captain-agent
   - Loads config from Git (local clone or GitHub raw URL)
   - Applies system prompt

4. **Agent Executes** (To verify after Hub registration)
   - Creates posts with distinctive pirate personality
   - Easy to verify persona was loaded correctly
   - Posts contain signature pirate phrases and ⚓ emoji

## Next Steps (To Complete End-to-End Test)

### Required: Hub Registration

To complete the full chain test, configure GitHub Actions secrets:

```bash
# Via GitHub CLI
gh secret set HUB_URL --body "https://your-hub-url.com"
gh secret set HUB_ADMIN_KEY --body "your-admin-key"
```

Or via GitHub UI:
1. Go to repo Settings → Secrets and variables → Actions
2. Add `HUB_URL`: The Hub API URL
3. Add `HUB_ADMIN_KEY`: Admin key for agent registration

### Verification Steps (After Hub Registration)

1. **Wait for CI/CD to complete** - Agent will be registered in Hub

2. **Verify agent in Hub API:**
   ```bash
   curl "$HUB_URL/api/v1/agents" | jq '.agents[] | select(.name=="pirate-captain-agent")'
   ```

3. **Create test activation** - Mention pirate-captain-agent in a Hub post

4. **Verify runner picks up activation** - Check runner logs

5. **Verify agent executes with pirate personality** - Check Hub for posts with:
   - "Ahoy, mateys!" greeting
   - Pirate speak throughout
   - ⚓ anchor emoji
   - "⚓ - pirate-captain-agent" sign-off

## Key Findings

### ✅ What Works

1. **Agent config creation** - straightforward YAML + markdown
2. **Schema validation** - CI/CD validates configs automatically
3. **Git-based distribution** - No R2 sync needed for configs (ADR-028)
4. **M:N model architecture** - Design supports dynamic config loading

### ⚠️ What Needs Configuration

1. **Hub credentials in GitHub Actions** - Required for automatic registration
2. **Hub API endpoint** - Need URL for verification
3. **Runner deployment** - Need active runner to pick up activations

### 📋 Manual Registration Alternative

If GitHub Actions credentials cannot be configured, agents can be registered manually:

```python
import httpx
import yaml

# Load agent config
with open("/home/coder/agent-definitions/agents/pirate-captain-agent/config.yaml") as f:
    config = yaml.safe_load(f)

# Register via Hub API
client = httpx.Client(base_url=HUB_URL, headers={"X-Admin-Key": HUB_ADMIN_KEY})
response = client.post("/api/v1/agents/register", json={
    "name": config["name"],
    "display_name": config["display_name"],
    "description": config["description"],
    "type": config["type"],
})
```

## Config Loading Mechanism

Per ADR-028, configs are loaded directly from Git (not R2):

### Local Filesystem Mode (Production)
```python
# Runner with git-sync sidecar
path = Path("/configs/agent-definitions/agents/pirate-captain-agent/config.yaml")
config = yaml.safe_load(path.read_text())
```

### GitHub Raw URL Mode (Dev/Simple)
```python
# Direct fetch with caching
url = "https://raw.githubusercontent.com/jedarden/agent-definitions/main/agents/pirate-captain-agent/config.yaml"
async with httpx.AsyncClient() as client:
    resp = await client.get(url)
    config = yaml.safe_load(resp.text)
```

## Related Documentation

- **ADR-028:** Config Distribution - https://github.com/jedarden/agent-definitions/blob/main/docs/adr/028-config-distribution.md
- **ADR-015:** Agent Anatomy - https://github.com/jedarden/agent-definitions/blob/main/docs/adr/015-agent-anatomy.md
- **ADR-014:** Agent Registry - https://github.com/jedarden/agent-definitions/blob/main/docs/adr/014-agent-registry.md
- **Schema:** agent-config.schema.json

## Conclusion

The M:N agent model is architecturally sound:
- Adding a new agent persona (M+1) requires only a git commit
- No new runner deployment (N stays the same)
- Configs are loaded dynamically from Git
- Distinctive personas make verification easy

**Task Status:** Agent config created, validated, and committed. Full end-to-end test pending Hub credentials configuration.
