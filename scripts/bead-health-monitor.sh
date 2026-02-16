#!/bin/bash
# Bead Health Monitor - Periodic health check runner
#
# Runs health checks on all workspaces with beads every 5 minutes.
# Can be added to cron or run in a loop.
#
# Usage:
#   ./bead-health-monitor.sh [--interval=300]
#   ./bead-health-monitor.sh --once  # Run once and exit

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERVAL=300  # 5 minutes
RUN_ONCE=false

# Known workspaces (add more as needed)
WORKSPACES=(
    "/home/coder/botburrow-agents"
    "/home/coder/botburrow-hub"
    "/home/coder/AMAIL"
    "/home/coder/ardenone-cluster"
)

# Parse arguments
for arg in "$@"; do
    case $arg in
        --interval=*)
            INTERVAL="${arg#*=}"
            shift
            ;;
        --once)
            RUN_ONCE=true
            shift
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--interval=300] [--once]"
            exit 1
            ;;
    esac
done

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2
}

# Check if directory has beads initialized
has_beads() {
    local workspace="$1"
    [ -d "$workspace/.beads" ]
}

# Run health check for a workspace
check_workspace() {
    local workspace="$1"

    if [ ! -d "$workspace" ]; then
        log_info "Workspace does not exist: $workspace (skipping)"
        return 0
    fi

    if ! has_beads "$workspace"; then
        log_info "Workspace does not have beads: $workspace (skipping)"
        return 0
    fi

    log_info "Checking workspace: $workspace"

    if [ -x "$SCRIPT_DIR/bead-health-check.sh" ]; then
        "$SCRIPT_DIR/bead-health-check.sh" --workspace="$workspace" --auto-fix || {
            log_error "Health check failed for $workspace"
            return 1
        }
    else
        log_error "Health check script not found: $SCRIPT_DIR/bead-health-check.sh"
        return 1
    fi

    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    log_info "Starting bead health monitor"
    log_info "Interval: ${INTERVAL}s"
    log_info "Run once: $RUN_ONCE"
    log_info "Workspaces: ${#WORKSPACES[@]}"

    while true; do
        log_info "=== Running health checks ==="

        local failed_count=0

        for workspace in "${WORKSPACES[@]}"; do
            check_workspace "$workspace" || failed_count=$((failed_count + 1))
        done

        if [ $failed_count -eq 0 ]; then
            log_info "All health checks passed ✅"
        else
            log_error "Health checks failed for $failed_count workspace(s) ❌"
        fi

        if [ "$RUN_ONCE" = true ]; then
            log_info "Single run complete. Exiting."
            exit $failed_count
        fi

        log_info "Next check in ${INTERVAL}s..."
        sleep "$INTERVAL"
    done
}

main
