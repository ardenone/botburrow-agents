#!/bin/bash
# Spawn Workers - Launch initial bead workers in tmux
#
# Usage:
#   ./spawn-workers.sh --workspace=/path/to/project
#   ./spawn-workers.sh --workspace=/path/to/project --workers=3 --executor=claude-glm

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE=""
NUM_WORKERS="${NUM_WORKERS:-1}"
EXECUTOR="${EXECUTOR:-claude-glm}"
MAX_FAILURES="${MAX_FAILURES:-3}"  # Max failures before blocking a bead
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_SCRIPT="$SCRIPT_DIR/bead-worker.sh"

# Worker limits
MAX_GLM_WORKERS="${MAX_GLM_WORKERS:-10}"  # Max GLM-4.7 workers across all orchestrators

# Parse arguments
for arg in "$@"; do
    case $arg in
        --workspace=*)
            WORKSPACE="${arg#*=}"
            shift
            ;;
        --workers=*)
            NUM_WORKERS="${arg#*=}"
            shift
            ;;
        --executor=*)
            EXECUTOR="${arg#*=}"
            shift
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# Validate
if [ -z "$WORKSPACE" ]; then
    echo "Error: --workspace is required"
    echo ""
    echo "Usage:"
    echo "  $0 --workspace=/path/to/project [--workers=N] [--executor=TYPE]"
    echo ""
    echo "Options:"
    echo "  --workspace   Path to project with beads initialized"
    echo "  --workers     Number of initial workers to spawn (default: 1)"
    echo "  --executor    Executor type: claude-glm, claude-sonnet, opencode-glm (default: claude-glm)"
    echo ""
    echo "Environment Variables:"
    echo "  MAX_FAILURES  Max failures before marking bead as blocked (default: 3)"
    exit 1
fi

if [ ! -f "$WORKER_SCRIPT" ]; then
    echo "Error: Worker script not found: $WORKER_SCRIPT"
    exit 1
fi

if [ ! -d "$WORKSPACE/.beads" ]; then
    echo "Error: Workspace does not have beads initialized: $WORKSPACE"
    echo "Run: cd $WORKSPACE && br init"
    exit 1
fi

# ============================================================================
# Worker Limit Checks
# ============================================================================

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
            echo "⚠️  GLM worker limit reached: $current_glm_count/$MAX_GLM_WORKERS"
            echo "   Cannot spawn more GLM workers (claude-glm or opencode-glm)"
            echo "   Increase limit with: MAX_GLM_WORKERS=20 $0 ..."
            return 1
        fi
    fi
    return 0
}

# ============================================================================
# Spawn Workers
# ============================================================================

# Check worker limits before spawning
if ! check_glm_worker_limit "$EXECUTOR"; then
    exit 1
fi

echo "🚀 Spawning $NUM_WORKERS bead workers"
echo "   Workspace: $WORKSPACE"
echo "   Executor: $EXECUTOR"

# Show current worker counts for GLM executors
if [[ "$EXECUTOR" =~ -glm$ ]]; then
    current_glm=$(count_glm_workers)
    echo "   GLM workers: $current_glm/$MAX_GLM_WORKERS (before spawning)"
fi

echo ""

# Source naming helper
source "$SCRIPT_DIR/worker-naming.sh"

for i in $(seq 1 "$NUM_WORKERS"); do
    # Generate session name using NATO alphabet
    session_name=$(generate_session_name "$EXECUTOR")

    echo "[$i/$NUM_WORKERS] Spawning worker: $session_name"

    tmux new-session -d -s "$session_name" \
        MAX_FAILURES="$MAX_FAILURES" \
        "$WORKER_SCRIPT" \
        --executor="$EXECUTOR" \
        --workspace="$WORKSPACE" \
        --session-name="$session_name"

    if [ $? -eq 0 ]; then
        echo "           ✓ Session: $session_name"
    else
        echo "           ✗ Failed to spawn worker"
    fi

    # Small delay between spawns
    sleep 0.5
done

echo ""
echo "✅ Spawned $NUM_WORKERS workers"
echo ""
echo "📊 Management commands:"
echo "   List sessions:  tmux list-sessions"
echo "   Attach to worker: tmux attach -t <TAB>  # Tab completion!"
echo "   Example:        tmux attach -t claude-sonnet-alpha"
echo "   Monitor logs:   tail -f ~/.beads-workers/*.log"
echo ""
echo "🔍 Check worker status:"
echo "   ./worker-status.sh --workspace=$WORKSPACE"
