#!/bin/bash
# Worker Status - Monitor bead workers and queue status
#
# Usage:
#   ./worker-status.sh --workspace=/path/to/project

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE=""
REFRESH_INTERVAL="${REFRESH_INTERVAL:-0}"  # 0 = no refresh, >0 = continuous

# Parse arguments
for arg in "$@"; do
    case $arg in
        --workspace=*)
            WORKSPACE="${arg#*=}"
            shift
            ;;
        --refresh=*)
            REFRESH_INTERVAL="${arg#*=}"
            shift
            ;;
        --watch)
            REFRESH_INTERVAL=2
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
# Display Status
# ============================================================================

display_status() {
    clear 2>/dev/null || true

    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  Bead Worker Status                                            ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""

    # Workspace info
    echo "📁 Workspace: $WORKSPACE"
    echo ""

    # Beads queue status
    echo "📋 Beads Queue:"
    if [ -d "$WORKSPACE/.beads" ]; then
        cd "$WORKSPACE" || exit 1

        local total=$(br list --json 2>/dev/null | jq 'length' || echo "0")
        local ready=$(br ready --json 2>/dev/null | jq 'length' || echo "0")
        local in_progress=$(br list --json 2>/dev/null | jq '[.[] | select(.status == "in_progress")] | length' || echo "0")
        local closed=$(br list --json 2>/dev/null | jq '[.[] | select(.status == "closed")] | length' || echo "0")

        echo "   Total:       $total"
        echo "   Ready:       $ready"
        echo "   In Progress: $in_progress"
        echo "   Closed:      $closed"

        if [ "$ready" -gt 0 ]; then
            echo ""
            echo "   Ready beads:"
            br ready --json 2>/dev/null | jq -r '.[] | "     • \(.id) [P\(.priority)] - \(.title)"' || echo "     (none)"
        fi
    else
        echo "   ✗ Beads not initialized in workspace"
    fi

    echo ""

    # Worker sessions (detect by naming pattern: orchestrator-model-nato)
    echo "🤖 Active Workers:"
    local sessions=$(tmux list-sessions 2>/dev/null | grep -E "^(claude|opencode)-(glm|sonnet|opus)-" || echo "")

    if [ -z "$sessions" ]; then
        echo "   (no active workers)"
    else
        echo "$sessions" | while read -r line; do
            local session_name=$(echo "$line" | cut -d: -f1)
            local created=$(echo "$line" | grep -oP '\d+ windows \(created [^)]+\)' || echo "")
            echo "   • $session_name - $created"
        done

        local worker_count=$(echo "$sessions" | wc -l)
        echo ""
        echo "   Total active: $worker_count"
    fi

    echo ""

    # Recent worker logs
    echo "📝 Recent Activity:"
    if [ -d "$HOME/.beads/workers" ]; then
        local latest_logs=$(ls -t "$HOME/.beads/workers"/*.log 2>/dev/null | head -5)

        if [ -z "$latest_logs" ]; then
            echo "   (no logs found)"
        else
            echo "$latest_logs" | while read -r log_file; do
                local worker_name=$(basename "$log_file" .log)
                local last_line=$(tail -1 "$log_file" 2>/dev/null || echo "")

                if [ -n "$last_line" ]; then
                    echo "   $worker_name:"
                    echo "     $last_line"
                fi
            done
        fi
    else
        echo "   (no log directory)"
    fi

    echo ""

    # Commands
    if [ "$REFRESH_INTERVAL" -eq 0 ]; then
        echo "💡 Commands:"
        echo "   Watch mode:     $0 --workspace=$WORKSPACE --watch"
        echo "   Spawn workers:  ./spawn-workers.sh --workspace=$WORKSPACE"
        echo "   Attach worker:  tmux attach -t bead-worker-<id>"
        echo "   View logs:      tail -f ~/.beads/workers/<worker-id>.log"
    else
        echo "🔄 Refreshing every ${REFRESH_INTERVAL}s (Ctrl+C to stop)..."
    fi

    echo ""
}

# ============================================================================
# Main
# ============================================================================

if [ "$REFRESH_INTERVAL" -gt 0 ]; then
    # Continuous refresh mode
    while true; do
        display_status
        sleep "$REFRESH_INTERVAL"
    done
else
    # Single display
    display_status
fi
