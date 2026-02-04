#!/bin/bash
# br-create-with-worker - Create a bead and ensure workers exist
# Wrapper around `br create` that auto-spawns workers if needed
#
# Usage:
#   ./br-create-with-worker.sh "Task title" --priority=0 --workspace=/path/to/project

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE="${WORKSPACE:-$(pwd)}"
EXECUTOR="${EXECUTOR:-claude-glm}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENSURE_WORKERS_SCRIPT="$SCRIPT_DIR/ensure-workers.sh"

# Extract workspace from arguments if provided
for arg in "$@"; do
    case $arg in
        --workspace=*)
            WORKSPACE="${arg#*=}"
            ;;
        --executor=*)
            EXECUTOR="${arg#*=}"
            ;;
    esac
done

# ============================================================================
# Main
# ============================================================================

# Ensure workers exist before creating bead
"$ENSURE_WORKERS_SCRIPT" \
    --workspace="$WORKSPACE" \
    --executor="$EXECUTOR"

echo ""
echo "➕ Creating bead..."

# Change to workspace
cd "$WORKSPACE" || exit 1

# Filter out --workspace and --executor from args (br doesn't know about them)
br_args=()
for arg in "$@"; do
    case $arg in
        --workspace=*|--executor=*)
            # Skip these args
            ;;
        *)
            br_args+=("$arg")
            ;;
    esac
done

# Create the bead
br create "${br_args[@]}"

echo ""
echo "✅ Bead created and workers are active"
