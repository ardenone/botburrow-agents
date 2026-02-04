#!/bin/bash
# Worker Naming - Generate NATO alphabet session names
#
# Format: [orchestrator]-[model]-[nato]
# Examples: claude-sonnet-alpha, opencode-glm-bravo

# NATO phonetic alphabet
NATO_ALPHABET=(
    alpha bravo charlie delta echo foxtrot golf hotel india juliet
    kilo lima mike november oscar papa quebec romeo sierra tango
    uniform victor whiskey xray yankee zulu
)

# Get next available NATO code for a given prefix
get_next_nato_code() {
    local prefix="$1"  # e.g., "claude-sonnet"

    # Get existing sessions with this prefix
    local existing_sessions=$(tmux list-sessions 2>/dev/null | grep "^${prefix}-" | cut -d: -f1 || echo "")

    # Try each NATO code until we find an unused one
    for nato in "${NATO_ALPHABET[@]}"; do
        local session_name="${prefix}-${nato}"

        # Check if this session name is already in use
        if ! echo "$existing_sessions" | grep -q "^${session_name}$"; then
            echo "$session_name"
            return 0
        fi
    done

    # Fallback if all NATO codes are used (unlikely)
    echo "${prefix}-${RANDOM}"
}

# Map executor to short model name
get_model_short_name() {
    local executor="$1"

    case "$executor" in
        claude-glm)
            echo "glm"
            ;;
        claude-sonnet)
            echo "sonnet"
            ;;
        claude-opus)
            echo "opus"
            ;;
        opencode-glm)
            echo "opencode-glm"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Generate session name
generate_session_name() {
    local executor="$1"

    # Extract orchestrator and model
    case "$executor" in
        claude-*)
            local orchestrator="claude"
            local model=$(get_model_short_name "$executor")
            ;;
        opencode-*)
            local orchestrator="opencode"
            local model=$(get_model_short_name "$executor")
            ;;
        *)
            local orchestrator="unknown"
            local model="unknown"
            ;;
    esac

    # Build prefix
    local prefix="${orchestrator}-${model}"

    # Get next NATO code
    get_next_nato_code "$prefix"
}

# If run directly, generate name
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ -z "$1" ]; then
        echo "Usage: $0 <executor>"
        echo "Examples:"
        echo "  $0 claude-glm      # claude-glm-alpha"
        echo "  $0 claude-sonnet   # claude-sonnet-alpha"
        echo "  $0 opencode-glm    # opencode-glm-alpha"
        exit 1
    fi

    generate_session_name "$1"
fi
