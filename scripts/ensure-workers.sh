#!/bin/bash
# Ensure Workers - Auto-spawn first worker if none exist
# Called by interactive Claude Code session before creating beads
#
# Usage:
#   ./ensure-workers.sh --workspace=/path/to/project [--executor=TYPE]

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE=""
EXECUTOR="${EXECUTOR:-claude-glm}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPAWN_SCRIPT="$SCRIPT_DIR/spawn-workers.sh"

# Parse arguments
for arg in "$@"; do
    case $arg in
        --workspace=*)
            WORKSPACE="${arg#*=}"
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
    exit 1
fi

# ============================================================================
# Check for Existing Workers
# ============================================================================

count_active_workers() {
    # Count sessions matching: orchestrator-model-nato pattern
    tmux list-sessions 2>/dev/null | grep -cE "^(claude|opencode)-(glm|sonnet|opus)-" || echo "0"
}

# ============================================================================
# Main
# ============================================================================

worker_count=$(count_active_workers)

if [ "$worker_count" -eq 0 ]; then
    echo "📭 No active workers found. Spawning initial worker..."
    echo ""

    "$SPAWN_SCRIPT" \
        --workspace="$WORKSPACE" \
        --workers=1 \
        --executor="$EXECUTOR"

    echo ""
    echo "✅ Initial worker spawned"
else
    echo "✓ $worker_count active worker(s) already running"
fi
