# Bead Workers - Self-Scaling Autonomous Worker Pool

**Status:** Implemented and ready for testing

---

## Overview

A self-scaling worker pool that processes beads autonomously:

1. **Interactive Claude** (you) creates beads
2. **First worker auto-spawns** when you create a bead
3. **Workers process beads** autonomously in separate tmux sessions
4. **Auto-scaling**: Workers spawn siblings when queue grows, exit when empty
5. **Multi-executor support**: GLM-4.7, Sonnet 4.5, OpenCode

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  You (Interactive Claude Code)                              │
│  br create "task" → Auto-spawns first worker if needed     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Beads Queue (.beads/issues.jsonl)                          │
│  Git-versioned, persistent task list                        │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┬────────────┐
        ▼                         ▼            ▼
┌──────────────┐         ┌──────────────┐  ┌──────────────┐
│ Worker 1     │         │ Worker 2     │  │ Worker 3     │
│ (tmux)       │────────▶│ (tmux)       │─▶│ (tmux)       │
│ claude-glm   │ spawns  │ claude-glm   │  │ opencode-glm │
└──────┬───────┘         └──────┬───────┘  └──────┬───────┘
       │                        │                 │
       └────────────────────────┴─────────────────┘
                        │
          If beads > 1: spawn +1 worker
          If beads = 0: exit
```

---

## Worker Behavior

### Lifecycle

1. **Startup**: Worker starts, logs to `~/.beads-workers/<id>.log`
2. **Poll**: Check `br ready --json` for available beads
3. **Claim**: `br update <id> --status in_progress`
4. **Execute**: Run Claude/OpenCode with task prompt
5. **Report**: `br close <id> --reason "completed"`
6. **Scale Decision**:
   - If remaining beads > 1: Spawn sibling worker
   - If remaining beads = 0: Exit gracefully
7. **Repeat**: Loop back to step 2

### Scaling Logic

```bash
# After completing a bead:
remaining_beads=$(br ready --json | jq 'length')

if [ $remaining_beads -gt 1 ]; then
    # Queue is growing, spawn helper
    spawn_worker()
elif [ $remaining_beads -eq 0 ]; then
    # Queue is empty, exit
    exit 0
else
    # Queue stable (1 bead), continue alone
    continue
fi
```

This creates **organic elasticity**:
- 0 beads → 0 workers (cost = $0)
- 1 bead → 1 worker
- 5 beads → Multiple workers spawn dynamically
- Work completes → Workers exit naturally

---

## Executors

Three executor types are supported:

### 1. claude-glm (Default)
- **LLM**: GLM-4.7 via z.ai proxy
- **Cost**: Free (z.ai proxy)
- **Speed**: Fast
- **Best for**: General tasks, experimentation

```bash
# Command executed:
claude --print --dangerously-skip-permissions \
  --api-url http://zai-proxy.mcp.svc.cluster.local:8080 \
  --api-key dummy \
  --model glm-4.7 \
  --prompt "$(cat prompt.txt)"
```

### 2. claude-sonnet
- **LLM**: Claude Sonnet 4.5 (official Anthropic API)
- **Cost**: Paid (Anthropic pricing)
- **Speed**: Medium
- **Best for**: Complex reasoning, production work

```bash
# Command executed:
claude --print --dangerously-skip-permissions \
  --model claude-sonnet-4-5-20250929 \
  --prompt "$(cat prompt.txt)"
```

### 3. opencode-glm
- **LLM**: GLM-4.7 via z.ai proxy
- **Tool**: OpenCode instead of Claude Code
- **Cost**: Free (z.ai proxy)
- **Best for**: Alternative workflow, comparison testing

```bash
# Command executed:
opencode --yes \
  --api-url http://zai-proxy.mcp.svc.cluster.local:8080 \
  --api-key dummy \
  --model glm-4.7 \
  --message "$(cat prompt.txt)"
```

---

## Quick Start

### 1. Create Beads (Auto-Spawns Workers)

```bash
cd ~/botburrow-hub

# This wrapper ensures workers exist before creating bead
./scripts/br-create-with-worker.sh "Add media upload endpoint" \
  --priority=0 \
  --workspace=$(pwd) \
  --executor=claude-glm
```

**What happens:**
1. Script checks for active workers: `tmux list-sessions | grep bead-worker`
2. If none found: Spawns first worker in tmux session
3. Creates the bead: `br create "Add media upload endpoint" --priority=0`
4. Worker picks up bead and starts processing

### 2. Monitor Workers

```bash
# One-time status
./scripts/worker-status.sh --workspace=$(pwd)

# Watch mode (refreshes every 2s)
./scripts/worker-status.sh --workspace=$(pwd) --watch
```

**Output:**
```
╔════════════════════════════════════════════════════════════════╗
║  Bead Worker Status                                            ║
╚════════════════════════════════════════════════════════════════╝

📁 Workspace: /home/coder/botburrow-hub

📋 Beads Queue:
   Total:       5
   Ready:       3
   In Progress: 2
   Closed:      0

   Ready beads:
     • bd-10w [P1] - Add beads integration to Hub API
     • bd-274 [P1] - Add beads task queue
     • bd-3mt [P2] - Add completion reporting

🤖 Active Workers:
   • bead-worker-worker-1738637152-init-1
   • bead-worker-worker-1738637160-spawned

   Total active: 2
```

### 3. Attach to Worker (Watch Live)

```bash
# List all worker sessions
tmux list-sessions | grep bead-worker

# Attach to specific worker
tmux attach -t bead-worker-worker-1738637152-init-1

# Detach: Ctrl+B, D
```

### 4. View Logs

```bash
# Tail latest worker log
tail -f ~/.beads-workers/*.log

# Tail specific worker
tail -f ~/.beads-workers/worker-1738637152-init-1.log
```

---

## Manual Worker Management

### Spawn Workers Manually

```bash
# Spawn 3 workers with GLM-4.7
./scripts/spawn-workers.sh \
  --workspace=/home/coder/botburrow-hub \
  --workers=3 \
  --executor=claude-glm

# Spawn 1 worker with Sonnet
./scripts/spawn-workers.sh \
  --workspace=/home/coder/botburrow-agents \
  --workers=1 \
  --executor=claude-sonnet
```

### Stop Workers

```bash
# Stop specific worker
tmux kill-session -t bead-worker-worker-123456

# Stop all workers
tmux kill-session -t bead-worker-*

# Workers will exit naturally when queue is empty
```

---

## Shell Aliases

Add to your `~/.bashrc`:

```bash
# Bead worker shortcuts
alias bw-status='~/botburrow-agents/scripts/worker-status.sh --workspace=$(pwd)'
alias bw-watch='~/botburrow-agents/scripts/worker-status.sh --workspace=$(pwd) --watch'
alias bw-spawn='~/botburrow-agents/scripts/spawn-workers.sh --workspace=$(pwd)'
alias bw-create='~/botburrow-agents/scripts/br-create-with-worker.sh'
alias bw-logs='tail -f ~/.beads-workers/*.log'

# Quick bead creation with auto-worker spawn
bc() {
    ~/botburrow-agents/scripts/br-create-with-worker.sh "$@" --workspace=$(pwd)
}
```

**Usage:**
```bash
bc "Fix authentication bug" --priority=0
bw-status
bw-watch
```

---

## Integration with ccdash

Workers are named with the prefix `bead-worker-` so ccdash can detect them:

```bash
# ccdash should detect sessions matching:
tmux list-sessions | grep "^bead-worker-"
```

**Session naming format:**
```
bead-worker-<worker-id>
  ├── worker-1738637152-init-1      (initial worker)
  ├── worker-1738637160-spawned      (auto-spawned worker)
  └── worker-1738637165-spawned      (auto-spawned worker)
```

ccdash can:
- List all active bead workers
- Show worker status
- Attach to worker sessions
- Monitor worker activity

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ZAI_PROXY_URL` | `http://zai-proxy.mcp.svc.cluster.local:8080` | Z.AI proxy endpoint |
| `ZAI_API_KEY` | `dummy` | API key for z.ai (not validated) |
| `MAX_ITERATIONS` | `100` | Max loops before worker exits |
| `SPAWN_THRESHOLD` | `1` | Spawn new worker if beads > N |

### Customizing Executors

Edit `bead-worker.sh` function `get_executor_command()`:

```bash
get_executor_command() {
    local executor="$1"
    local prompt_file="$2"

    case "$executor" in
        claude-glm)
            echo "claude --print --dangerously-skip-permissions \
                --api-url $ZAI_PROXY_URL \
                --api-key $ZAI_API_KEY \
                --model glm-4.7 \
                --prompt \"\$(cat $prompt_file)\""
            ;;
        # Add custom executors here
        my-custom-executor)
            echo "my-tool --input \"\$(cat $prompt_file)\""
            ;;
    esac
}
```

---

## Example Workflow

### Morning: Plan Work

```bash
cd ~/botburrow-hub

# Create beads for today's work
bc "Add rate limiting middleware" --priority=0
bc "Implement Redis caching" --priority=1
bc "Write E2E tests for auth" --priority=2

# Check status
bw-status
```

**Output:**
```
📭 No active workers found. Spawning initial worker...
✅ Initial worker spawned

➕ Creating bead...
Created bd-abc: Add rate limiting middleware

✅ Bead created and workers are active
```

### Midday: Check Progress

```bash
bw-status
```

**Output:**
```
📋 Beads Queue:
   Total:       3
   Ready:       1
   In Progress: 1
   Closed:      1

🤖 Active Workers:
   • bead-worker-worker-1738637152-init-1
   • bead-worker-worker-1738637160-spawned

   Total active: 2
```

### End of Day: Review Work

```bash
cd ~/botburrow-hub
br list

# Sync to git
br sync --flush-only
git add .beads/issues.jsonl
git commit -m "Daily task updates"
git push
```

---

## Troubleshooting

### Workers Not Spawning

```bash
# Check if tmux is available
which tmux

# Check for existing sessions
tmux list-sessions

# Check worker script permissions
ls -la ~/botburrow-agents/scripts/bead-worker.sh

# Try spawning manually
~/botburrow-agents/scripts/spawn-workers.sh \
  --workspace=$(pwd) \
  --workers=1 \
  --executor=claude-glm
```

### Workers Failing

```bash
# Check logs
tail -100 ~/.beads-workers/*.log

# Common issues:
# 1. Z.AI proxy not accessible
curl http://zai-proxy.mcp.svc.cluster.local:8080/health

# 2. Beads not initialized
cd ~/botburrow-hub && br init

# 3. Claude Code not in PATH
which claude

# 4. Workspace directory doesn't exist
ls -la ~/botburrow-hub
```

### Workers Not Exiting

```bash
# Workers should exit when queue is empty
# If stuck, kill manually:
tmux kill-session -t bead-worker-worker-123456

# Or kill all:
pkill -f bead-worker.sh
```

---

## Performance Considerations

### Cost

- **GLM-4.7 (via z.ai)**: Free, unlimited
- **Sonnet 4.5**: ~$3 per million input tokens, ~$15 per million output tokens

**Example cost per bead:**
- Small task (10K tokens): ~$0.03
- Medium task (50K tokens): ~$0.15
- Large task (200K tokens): ~$0.60

### Scaling

- **1 worker**: Processes beads sequentially
- **Auto-scaling**: Workers = min(beads_ready, beads_ready)
- **Max workers**: Limited by tmux/system resources

**Recommended:**
- Start with 1-2 workers
- Let auto-scaling handle burst workloads
- Monitor with `bw-watch`

---

## Next Steps

1. **Test the system**:
   ```bash
   cd ~/botburrow-hub
   bc "Test task" --priority=0
   bw-watch
   ```

2. **Create real beads**:
   ```bash
   bc "Implement WebSocket reconnection" --priority=0
   bc "Add consumption warnings" --priority=1
   ```

3. **Monitor and iterate**:
   - Watch workers process beads
   - Adjust SPAWN_THRESHOLD if needed
   - Add custom executors

4. **Integrate with Git**:
   ```bash
   br sync --flush-only
   git add .beads/
   git commit -m "Track bead progress"
   ```

---

## Files

```
botburrow-agents/scripts/
├── bead-worker.sh              # Core worker loop
├── spawn-workers.sh            # Spawn initial workers
├── worker-status.sh            # Monitor workers and queue
├── ensure-workers.sh           # Auto-spawn if none exist
└── br-create-with-worker.sh    # Wrapper: create bead + ensure workers

Logs:
~/.beads-workers/
└── worker-*.log                # Individual worker logs
```

---

**Ready to start?**

```bash
cd ~/botburrow-hub
bc "Your first task" --priority=0
bw-watch
```
