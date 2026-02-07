#!/bin/bash
# Bead Worker - Self-scaling autonomous worker for processing beads
#
# Usage:
#   ./bead-worker.sh --executor=claude-glm --workspace=/path/to/project
#   ./bead-worker.sh --executor=claude-sonnet --workspace=/path/to/project
#   ./bead-worker.sh --executor=opencode-glm --workspace=/path/to/project

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_ID="${WORKER_ID:-}"  # Will be set based on session name
EXECUTOR=""
WORKSPACE=""
LOG_FILE="${LOG_FILE:-}"  # Will be set after WORKER_ID is determined
MAX_ITERATIONS="${MAX_ITERATIONS:-100}"
SPAWN_THRESHOLD="${SPAWN_THRESHOLD:-1}"  # Spawn new worker if >1 beads remain
MAX_FAILURES="${MAX_FAILURES:-3}"  # Max failures before marking bead as blocked
SESSION_NAME="${SESSION_NAME:-}"  # Will be generated using NATO alphabet

# Parse arguments
for arg in "$@"; do
    case $arg in
        --executor=*)
            EXECUTOR="${arg#*=}"
            shift
            ;;
        --workspace=*)
            WORKSPACE="${arg#*=}"
            shift
            ;;
        --worker-id=*)
            WORKER_ID="${arg#*=}"
            shift
            ;;
        --session-name=*)
            SESSION_NAME="${arg#*=}"
            shift
            ;;
        --log-file=*)
            LOG_FILE="${arg#*=}"
            shift
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$EXECUTOR" ]; then
    echo "Error: --executor is required"
    echo "Options: claude-glm, claude-sonnet, opencode-glm"
    exit 1
fi

if [ -z "$WORKSPACE" ]; then
    echo "Error: --workspace is required"
    exit 1
fi

# Ensure workspace exists
if [ ! -d "$WORKSPACE" ]; then
    echo "Error: Workspace directory does not exist: $WORKSPACE"
    exit 1
fi

# Ensure workspace has beads initialized
if [ ! -d "$WORKSPACE/.beads" ]; then
    echo "Error: Workspace does not have beads initialized: $WORKSPACE"
    echo "Run: cd $WORKSPACE && br init"
    exit 1
fi

# Set SESSION_NAME if not provided (use current tmux session name)
if [ -z "$SESSION_NAME" ]; then
    SESSION_NAME="${TMUX_PANE:+$(tmux display-message -p '#S')}"
    if [ -z "$SESSION_NAME" ]; then
        # Generate session name using NATO alphabet
        source "$SCRIPT_DIR/worker-naming.sh"
        SESSION_NAME=$(generate_session_name "$EXECUTOR")
    fi
fi

# Set WORKER_ID from SESSION_NAME if not already set
if [ -z "$WORKER_ID" ]; then
    WORKER_ID="$SESSION_NAME"
fi

# Set LOG_FILE if not provided
if [ -z "$LOG_FILE" ]; then
    LOG_FILE="$HOME/.beads-workers/$WORKER_ID.log"
fi

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# ============================================================================
# Logging
# ============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] [$WORKER_ID] $message" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "$@"
}

log_error() {
    log "ERROR" "$@"
}

log_success() {
    log "SUCCESS" "$@"
}

# ============================================================================
# Executor Configuration
# ============================================================================

# Z.AI proxy configuration (GLM-4.7)
ZAI_PROXY_URL="${ZAI_PROXY_URL:-http://zai-proxy.mcp.svc.cluster.local:8080}"
ZAI_API_KEY="${ZAI_API_KEY:-dummy}"  # Z.AI doesn't validate API key

# Executor command builders
get_executor_command() {
    local executor="$1"
    local prompt_file="$2"

    case "$executor" in
        claude-glm)
            # Use .claude-zai config for z.ai GLM-4.7 proxy
            echo "export CLAUDE_CONFIG_DIR=/home/coder/.claude-zai && cat $prompt_file | claude --dangerously-skip-permissions --output-format stream-json --verbose --print"
            ;;
        claude-sonnet)
            # Use default .claude config for Anthropic API
            echo "export CLAUDE_CONFIG_DIR=/home/coder/.claude && cat $prompt_file | claude --dangerously-skip-permissions --output-format stream-json --verbose --print"
            ;;
        opencode-glm)
            # OpenCode via Z.AI proxy (no stream-json support)
            echo "opencode --yes --api-url $ZAI_PROXY_URL --api-key $ZAI_API_KEY --model glm-4.7 --message \"\$(cat $prompt_file)\""
            ;;
        *)
            log_error "Unknown executor: $executor"
            return 1
            ;;
    esac
}

# ============================================================================
# Bead Operations
# ============================================================================

get_ready_beads() {
    cd "$WORKSPACE" || return 1
    br ready --json 2>/dev/null || echo "[]"
}

count_ready_beads() {
    get_ready_beads | jq 'length'
}

get_next_bead() {
    get_ready_beads | jq -r '.[0] // empty'
}

claim_bead() {
    local bead_id="$1"
    cd "$WORKSPACE" || return 1
    br update "$bead_id" --status in_progress 2>&1 | tee -a "$LOG_FILE"
}

complete_bead() {
    local bead_id="$1"
    local reason="${2:-completed by worker}"
    cd "$WORKSPACE" || return 1
    # Clear failure counter on success
    br close "$bead_id" --reason "$reason" --notes "" 2>&1 | tee -a "$LOG_FILE"
}

# Increment failure counter stored in bead notes
get_failure_count() {
    local bead_id="$1"
    cd "$WORKSPACE" || return 1
    br show "$bead_id" --json 2>/dev/null | jq -r '.notes // ""' | grep -oE 'failures:[[:space:]]*[0-9]+' | grep -oE '[0-9]+' || echo "0"
}

# Format failure message with context
format_failure_message() {
    local bead_id="$1"
    local reason="$2"
    local exit_code="$3"
    local worker_id="$4"
    local executor="$5"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    cat <<EOF

---
❌ **Failure** at $timestamp
- Worker: $worker_id
- Executor: $executor
- Exit Code: $exit_code
- Reason: $reason

Last 10 lines of output:
$(tail -10 "$LOG_FILE" | grep -E "ERROR|WARN|failed" | tail -5 || echo "(No error details captured)")
EOF
}

fail_bead() {
    local bead_id="$1"
    local reason="${2:-failed}"
    local exit_code="${3:-1}"
    cd "$WORKSPACE" || return 1

    # Get current failure count
    local failure_count=$(get_failure_count "$bead_id")
    failure_count=$((failure_count + 1))

    log_error "Bead $bead_id failed (attempt $failure_count): $reason"

    # Add failure comment
    local failure_msg=$(format_failure_message "$bead_id" "$reason" "$exit_code" "$WORKER_ID" "$EXECUTOR")
    br comments add "$bead_id" "$failure_msg" 2>&1 | tee -a "$LOG_FILE"

    # Check if we should block this bead
    if [ "$failure_count" -ge "$MAX_FAILURES" ]; then
        log_error "Bead $bead_id exceeded max failures ($MAX_FAILURES). Marking as blocked."
        br update "$bead_id" \
            --status blocked \
            --notes "failures: $failure_count" 2>&1 | tee -a "$LOG_FILE"
        return 1
    fi

    # Reopen with updated failure count
    br update "$bead_id" \
        --status open \
        --notes "failures: $failure_count" 2>&1 | tee -a "$LOG_FILE"
}

# ============================================================================
# Worker Spawning
# ============================================================================

# Worker limits
MAX_GLM_WORKERS="${MAX_GLM_WORKERS:-10}"

count_glm_workers() {
    # Count all GLM workers (claude-glm + opencode-glm)
    tmux list-sessions 2>/dev/null | grep -cE "^(claude|opencode)-glm-" || echo "0"
}

check_glm_worker_limit() {
    local executor="$1"
    local current_glm_count=$(count_glm_workers)

    # Only check limit for GLM executors
    if [[ "$executor" =~ -glm$ ]]; then
        if [ "$current_glm_count" -ge "$MAX_GLM_WORKERS" ]; then
            log_info "GLM worker limit reached: $current_glm_count/$MAX_GLM_WORKERS. Skipping spawn."
            return 1
        fi
    fi
    return 0
}

spawn_worker() {
    local executor="$1"
    local workspace="$2"

    # Check worker limits before spawning
    if ! check_glm_worker_limit "$executor"; then
        return 1
    fi

    # Generate session name using NATO alphabet
    source "$SCRIPT_DIR/worker-naming.sh"
    local new_session_name=$(generate_session_name "$executor")

    log_info "Spawning new worker: $new_session_name (executor: $executor)"

    # Spawn in new tmux session
    tmux new-session -d -s "$new_session_name" \
        MAX_FAILURES="$MAX_FAILURES" \
        "$(realpath "$0")" \
        --executor="$executor" \
        --workspace="$workspace" \
        --session-name="$new_session_name"

    if [ $? -eq 0 ]; then
        log_success "Spawned worker in tmux session: $new_session_name"
        return 0
    else
        log_error "Failed to spawn worker"
        return 1
    fi
}

# ============================================================================
# Work Execution
# ============================================================================

execute_bead() {
    local bead="$1"

    # Parse bead details
    local bead_id=$(echo "$bead" | jq -r '.id')
    local bead_title=$(echo "$bead" | jq -r '.title')
    local bead_description=$(echo "$bead" | jq -r '.description')
    local current_failures=$(echo "$bead" | jq -r '.notes // ""' | grep -oE 'failures:[[:space:]]*[0-9]+' | grep -oE '[0-9]+' || echo "0")

    log_info "Processing bead: $bead_id - $bead_title (previous failures: $current_failures)"

    # Claim the bead
    claim_bead "$bead_id" || {
        log_error "Failed to claim bead: $bead_id"
        return 1
    }

    # Build prompt
    local prompt_file="/tmp/bead-prompt-$bead_id-$$.txt"
    cat > "$prompt_file" <<EOF
# Task: $bead_id

## Title
$bead_title

## Description
$bead_description

## Instructions
1. Implement the requirements described above
2. Run tests if applicable: pytest, npm test, cargo test, etc.
3. If tests pass or implementation is complete, the task is done
4. If you encounter blockers or need clarification, note them in your response
5. Commit changes with message: "feat($bead_id): $bead_title"

## Constraints
- Work in directory: $WORKSPACE
- This is bead ID: $bead_id
- Executor: $EXECUTOR
- Worker: $WORKER_ID

## Success Criteria
- Task requirements are met
- Tests pass (if applicable)
- Code is committed
- No compilation/runtime errors
EOF

    log_info "Executing with $EXECUTOR..."

    # Get executor command
    local exec_cmd=$(get_executor_command "$EXECUTOR" "$prompt_file")

    # Execute in workspace
    cd "$WORKSPACE" || return 1

    # Create temp file for execution output
    local exec_output="/tmp/bead-exec-$bead_id-$$.log"

    # Check if stream parser exists
    local parser_script=""
    case "$EXECUTOR" in
        claude-glm)
            parser_script="$HOME/claude-config/agents/claude-code-glm-4.7/stream-parser.sh"
            ;;
        claude-sonnet)
            parser_script="$HOME/claude-config/agents/claude-code-sonnet/stream-parser.sh"
            ;;
        claude-opus)
            parser_script="$HOME/claude-config/agents/claude-code-opus/stream-parser.sh"
            ;;
        opencode-glm)
            # OpenCode uses its own pattern-based parser (not stream-json)
            parser_script="$SCRIPT_DIR/stream-parser.sh"
            ;;
        *)
            # Fallback to local stream parser
            parser_script="$SCRIPT_DIR/stream-parser.sh"
            ;;
    esac
    local exit_code=0

    if [ -x "$parser_script" ]; then
        # Use stream parser for human-readable output
        eval "$exec_cmd" 2>&1 | tee -a "$LOG_FILE" | tee "$exec_output" | "$parser_script" || exit_code=$?
    else
        # Fallback to raw output
        eval "$exec_cmd" 2>&1 | tee -a "$LOG_FILE" | tee "$exec_output" || exit_code=$?
    fi

    # Cleanup prompt file
    rm -f "$prompt_file"

    # Save execution output for failure context (kept until next bead execution)
    local last_output="/tmp/bead-last-$bead_id.log"
    mv "$exec_output" "$last_output"

    # Check result
    if [ $exit_code -eq 0 ]; then
        log_success "Bead $bead_id completed successfully"
        complete_bead "$bead_id" "Completed by worker $WORKER_ID using $EXECUTOR"
        rm -f "$last_output"
        return 0
    else
        log_error "Bead $bead_id failed with exit code $exit_code"
        fail_bead "$bead_id" "Execution failed with exit code $exit_code (see last output for details)" "$exit_code"
        return 1
    fi
}

# ============================================================================
# Main Worker Loop
# ============================================================================

main() {
    log_info "Starting bead worker"
    log_info "Executor: $EXECUTOR"
    log_info "Workspace: $WORKSPACE"
    log_info "Log file: $LOG_FILE"
    log_info "Max failures before blocking: $MAX_FAILURES"

    local iteration=0

    while [ $iteration -lt $MAX_ITERATIONS ]; do
        iteration=$((iteration + 1))

        log_info "Iteration $iteration/$MAX_ITERATIONS"

        # Check for ready beads
        local bead_count=$(count_ready_beads)
        log_info "Ready beads: $bead_count"

        if [ "$bead_count" -eq 0 ]; then
            log_info "No beads available. Exiting."
            exit 0
        fi

        # Get next bead
        local bead=$(get_next_bead)

        if [ -z "$bead" ]; then
            log_info "No bead available (empty). Exiting."
            exit 0
        fi

        # Execute the bead
        execute_bead "$bead" || {
            log_error "Failed to execute bead. Continuing to next iteration."
            sleep 5
            continue
        }

        # Check if we should spawn another worker
        local remaining_beads=$(count_ready_beads)
        log_info "Remaining beads after completion: $remaining_beads"

        if [ "$remaining_beads" -gt "$SPAWN_THRESHOLD" ]; then
            log_info "Remaining beads ($remaining_beads) > threshold ($SPAWN_THRESHOLD). Spawning new worker."
            spawn_worker "$EXECUTOR" "$WORKSPACE" || {
                log_error "Failed to spawn new worker. Continuing."
            }
        fi

        # Small delay before next iteration
        sleep 2
    done

    log_info "Reached max iterations ($MAX_ITERATIONS). Exiting."
}

# ============================================================================
# Signal Handling
# ============================================================================

cleanup() {
    log_info "Received signal. Shutting down gracefully..."
    exit 0
}

trap cleanup SIGINT SIGTERM

# ============================================================================
# Entry Point
# ============================================================================

main "$@"
