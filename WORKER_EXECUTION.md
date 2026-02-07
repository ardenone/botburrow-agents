# Worker Execution Model

## How Workers Run

Workers execute using the **Claude Code CLI** (`claude` command) with specific flags based on the executor type.

---

## Executor Types & Commands

### 1. claude-sonnet (Default Anthropic API)

**Command executed:**
```bash
cat /tmp/prompt.txt | claude --print --dangerously-skip-permissions --model claude-sonnet-4-5-20250929
```

**How it works:**
- Uses `stdin` for prompt input (piped from file)
- `--print` - Output to stdout (non-interactive mode)
- `--dangerously-skip-permissions` - Auto-approve all tool calls
- `--model` - Specify Sonnet 4.5 explicitly

**Settings source:**
- **YES, uses `.claude` folder settings**
- API key from: `~/.claude/settings.json` or `ANTHROPIC_API_KEY` env var
- Other settings: MCP servers, skills, etc. from `.claude/`
- Does NOT use `.claude-zai` settings

**Cost:** Paid (Anthropic API pricing)

---

### 2. claude-glm (Z.AI Proxy)

**Command executed:**
```bash
cat /tmp/prompt.txt | claude --print --dangerously-skip-permissions \
  --api-url http://zai-proxy.mcp.svc.cluster.local:8080 \
  --api-key dummy \
  --model glm-4.7
```

**How it works:**
- Overrides API endpoint with `--api-url` (points to z.ai proxy)
- `--api-key dummy` - Z.AI doesn't validate API keys
- `--model glm-4.7` - Requests GLM-4.7 from proxy

**Settings source:**
- **Partially uses `.claude` settings**
- API endpoint overridden by `--api-url` flag
- MCP servers, skills from `.claude/` may still apply
- Does NOT use `.claude-zai` folder (CLI doesn't support multiple profiles)

**Cost:** Free (z.ai proxy)

---

### 3. opencode-glm (OpenCode via Z.AI)

**Command executed:**
```bash
opencode --yes \
  --api-url http://zai-proxy.mcp.svc.cluster.local:8080 \
  --api-key dummy \
  --model glm-4.7 \
  --message "$(cat /tmp/prompt.txt)"
```

**How it works:**
- Uses OpenCode CLI (different orchestrator)
- `--yes` - Auto-approve operations
- Points to z.ai proxy for LLM

**Settings source:**
- Uses OpenCode's own settings (not `.claude`)
- May have its own config directory (e.g., `~/.opencode`)

**Cost:** Free (z.ai proxy)

---

## Settings Hierarchy

### For Claude Code Executors (claude-sonnet, claude-glm)

**Priority (highest to lowest):**

1. **CLI flags** (highest priority)
   - `--api-url` overrides endpoint
   - `--model` overrides model
   - `--api-key` overrides API key

2. **Environment variables**
   - `ANTHROPIC_API_KEY`
   - `ANTHROPIC_API_URL`

3. **~/.claude/settings.json** (lowest priority)
   ```json
   {
     "apiKey": "sk-...",
     "apiUrl": "https://api.anthropic.com",
     "mcpServers": { ... },
     "skills": { ... }
   }
   ```

### Which Settings Are Used?

| Setting | claude-sonnet | claude-glm | opencode-glm |
|---------|---------------|------------|--------------|
| API Key | ✅ `.claude` or env | ❌ Overridden | N/A |
| API URL | ✅ `.claude` or env | ❌ Overridden | ❌ Overridden |
| Model | ❌ Overridden | ❌ Overridden | ❌ Overridden |
| MCP Servers | ✅ `.claude` | ✅ `.claude` | ❌ |
| Skills | ✅ `.claude` | ✅ `.claude` | ❌ |

---

## Why .claude-zai Folder Isn't Used

The `.claude-zai` folder is for the **z.ai Claude CLI fork**, which is a separate binary that defaults to z.ai settings.

**Workers use the standard `claude` CLI** with explicit flags, not the z.ai fork.

**To use z.ai fork:**
```bash
# Instead of:
claude --api-url http://zai-proxy.mcp.svc.cluster.local:8080

# You could use z.ai fork:
claude-zai  # Reads from ~/.claude-zai/settings.json by default
```

But workers use explicit flags for transparency and control.

---

## MCP Server Access

### claude-sonnet & claude-glm

**MCP servers from `~/.claude/settings.json` ARE available:**

```json
{
  "mcpServers": {
    "agent-mail": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_agent_mail.server"]
    },
    "github": {
      "command": "uvx",
      "args": ["mcp-server-github"]
    }
  }
}
```

Workers can use these tools if they're configured.

### opencode-glm

Uses OpenCode's own tool/MCP system (different from Claude Code).

---

## Skill Access

Workers have access to Claude Code skills from `~/.claude/skills/`:

- `/bd-to-br-migration` - Beads migration helper
- Any custom skills you've added

Skills are loaded automatically when worker starts.

---

## Configuration Examples

### Current Z.AI Proxy Config

**Worker script sets:**
```bash
ZAI_PROXY_URL="${ZAI_PROXY_URL:-http://zai-proxy.mcp.svc.cluster.local:8080}"
ZAI_API_KEY="${ZAI_API_KEY:-dummy}"
```

**Override via environment:**
```bash
export ZAI_PROXY_URL="http://my-custom-proxy:8080"
/home/coder/botburrow-agents/scripts/spawn-workers.sh --executor=claude-glm
```

### Using Different Anthropic API Key

**Option 1: Environment variable**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key"
/home/coder/botburrow-agents/scripts/spawn-workers.sh --executor=claude-sonnet
```

**Option 2: Update ~/.claude/settings.json**
```json
{
  "apiKey": "sk-ant-your-key"
}
```

---

## Sandboxing & Permissions

### --dangerously-skip-permissions Flag

**What it does:**
- Auto-approves all tool use (Bash, Edit, Write, etc.)
- Workers run fully autonomously without prompts
- Required for headless operation

**Safety:**
- Workers operate in their workspace directory
- Git-backed (changes can be reverted)
- Logs all operations to `~/.beads-workers/*.log`

**Without this flag:**
Workers would hang waiting for human approval on every tool call.

---

## Worker Execution Flow

```
1. Worker starts in tmux session: claude-sonnet-alpha

2. Worker polls beads queue:
   br ready --json

3. Worker claims bead:
   br update bd-xyz --status in_progress

4. Worker builds prompt file:
   /tmp/bead-prompt-bd-xyz-12345.txt

5. Worker executes Claude Code:
   cat /tmp/bead-prompt-bd-xyz-12345.txt | \
     claude --print --dangerously-skip-permissions \
     --model claude-sonnet-4-5-20250929

6. Claude Code runs:
   - Reads prompt from stdin
   - Loads settings from ~/.claude/settings.json
   - Connects to MCP servers (if configured)
   - Loads skills from ~/.claude/skills/
   - Executes tools (Bash, Edit, Write, WebSearch, etc.)
   - Outputs results to stdout

7. Worker captures output:
   Stdout → worker log file

8. Worker reports completion:
   br close bd-xyz --reason "completed"

9. Worker checks for more work:
   remaining=$(br ready --json | jq 'length')
   if remaining > 1: spawn sibling
   if remaining = 0: exit
```

---

## Debugging

### Check What Command is Executed

```bash
# View worker log
tail -f ~/.beads-workers/claude-sonnet-alpha.log

# Look for "Executing with..." line
# Example output:
# [2026-02-04 02:50:54] [INFO] [claude-sonnet-alpha] Executing with claude-sonnet...
```

### Test Command Manually

```bash
# Create test prompt
echo "List files in current directory" > /tmp/test-prompt.txt

# Test claude-sonnet
cat /tmp/test-prompt.txt | \
  claude --print --dangerously-skip-permissions \
  --model claude-sonnet-4-5-20250929

# Test claude-glm
cat /tmp/test-prompt.txt | \
  claude --print --dangerously-skip-permissions \
  --api-url http://zai-proxy.mcp.svc.cluster.local:8080 \
  --api-key dummy \
  --model glm-4.7
```

### Check Settings Being Used

```bash
# View Claude settings
cat ~/.claude/settings.json | jq '.'

# Check API key (if set)
cat ~/.claude/settings.json | jq -r '.apiKey'

# Check MCP servers
cat ~/.claude/settings.json | jq '.mcpServers'
```

---

## Customization

### Add Custom Executor

Edit `/home/coder/botburrow-agents/scripts/bead-worker.sh`:

```bash
get_executor_command() {
    local executor="$1"
    local prompt_file="$2"

    case "$executor" in
        # ... existing executors ...

        claude-opus)
            # Use Opus instead of Sonnet
            echo "cat $prompt_file | claude --print --dangerously-skip-permissions --model claude-opus-4-20250514"
            ;;

        claude-max)
            # Use Claude Max endpoint
            echo "cat $prompt_file | claude --print --dangerously-skip-permissions --api-url https://api.claude.ai --model claude-sonnet-4-5"
            ;;

        aider)
            # Use Aider instead of Claude Code
            echo "aider --yes --message \"\$(cat $prompt_file)\""
            ;;
    esac
}
```

Then spawn:
```bash
./spawn-workers.sh --executor=claude-opus --workspace=/path/to/project
# Session name: claude-opus-alpha
```

---

## Summary

**Workers use:**
- ✅ Claude Code CLI (`claude` command)
- ✅ Settings from `~/.claude/` folder (API key, MCP servers, skills)
- ✅ CLI flags override settings (API URL, model)
- ❌ Do NOT use `.claude-zai` folder (different binary)

**For z.ai proxy:**
- Workers override `--api-url` to point to proxy
- API key (`--api-key dummy`) bypasses authentication
- MCP servers and skills from `.claude/` still available

**Session names:**
- Format: `[orchestrator]-[model]-[nato]`
- Examples: `claude-sonnet-alpha`, `opencode-glm-bravo`
- Tab completion: `tmux attach -t cl<TAB>`
