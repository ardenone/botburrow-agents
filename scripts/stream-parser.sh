#!/bin/bash
# Bead Worker Stream Parser
# Parses Claude Code stream-json output and extracts structured information
# Based on marathon-coding stream-parser.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

# Track state
CURRENT_TOOL=""
IN_THINKING=false
HAS_ERROR=false
TOTAL_COST=0
INPUT_TOKENS=0
OUTPUT_TOKENS=0

# Process each line
while IFS= read -r line; do
    # Skip empty lines
    [ -z "$line" ] && continue

    # Try to parse as JSON
    if ! echo "$line" | jq -e . >/dev/null 2>&1; then
        # Not JSON, print as-is
        echo "$line"
        continue
    fi

    # Extract type
    TYPE=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)

    case "$TYPE" in
        "system")
            SUBTYPE=$(echo "$line" | jq -r '.subtype // empty' 2>/dev/null)
            if [ "$SUBTYPE" = "init" ]; then
                MODEL=$(echo "$line" | jq -r '.model // empty' 2>/dev/null)
                VERSION=$(echo "$line" | jq -r '.claude_code_version // empty' 2>/dev/null)
                echo -e "${MAGENTA}╔══ Worker Session ══╗${NC}"
                echo -e "${MAGENTA}│ Model:${NC} $MODEL"
                echo -e "${MAGENTA}│ Version:${NC} $VERSION"
                echo -e "${MAGENTA}╚═══════════════════════╝${NC}"
            fi
            ;;

        "assistant")
            CONTENT_TYPE=$(echo "$line" | jq -r '.message.content[0].type // empty' 2>/dev/null)

            case "$CONTENT_TYPE" in
                "text")
                    TEXT=$(echo "$line" | jq -r '.message.content[0].text // empty' 2>/dev/null)
                    if [ -n "$TEXT" ] && [ "$TEXT" != "null" ]; then
                        echo -e "${WHITE}$TEXT${NC}"
                    fi
                    ;;
                "tool_use")
                    TOOL_NAME=$(echo "$line" | jq -r '.message.content[0].name // empty' 2>/dev/null)
                    TOOL_INPUT=$(echo "$line" | jq -r '.message.content[0].input // {}' 2>/dev/null)

                    case "$TOOL_NAME" in
                        "Bash")
                            CMD=$(echo "$TOOL_INPUT" | jq -r '.command // empty' 2>/dev/null)
                            echo -e "${CYAN}▶ Bash: ${WHITE}$CMD${NC}"
                            ;;
                        "Read")
                            FILE=$(echo "$TOOL_INPUT" | jq -r '.file_path // empty' 2>/dev/null)
                            echo -e "${CYAN}▶ Read: ${WHITE}$FILE${NC}"
                            ;;
                        "Write")
                            FILE=$(echo "$TOOL_INPUT" | jq -r '.file_path // empty' 2>/dev/null)
                            echo -e "${CYAN}▶ Write: ${WHITE}$FILE${NC}"
                            ;;
                        "Edit")
                            FILE=$(echo "$TOOL_INPUT" | jq -r '.file_path // empty' 2>/dev/null)
                            echo -e "${CYAN}▶ Edit: ${WHITE}$FILE${NC}"
                            ;;
                        "WebSearch")
                            QUERY=$(echo "$TOOL_INPUT" | jq -r '.query // empty' 2>/dev/null)
                            echo -e "${CYAN}▶ WebSearch: ${WHITE}$QUERY${NC}"
                            ;;
                        "WebFetch")
                            URL=$(echo "$TOOL_INPUT" | jq -r '.url // empty' 2>/dev/null)
                            echo -e "${CYAN}▶ WebFetch: ${WHITE}$URL${NC}"
                            ;;
                        *)
                            echo -e "${CYAN}▶ Tool: $TOOL_NAME${NC}"
                            ;;
                    esac
                    ;;
            esac
            ;;

        "user")
            TOOL_RESULT_TYPE=$(echo "$line" | jq -r '.message.content[0].type // empty' 2>/dev/null)
            if [ "$TOOL_RESULT_TYPE" = "tool_result" ]; then
                IS_ERROR=$(echo "$line" | jq -r '.message.content[0].is_error // false' 2>/dev/null)

                if [ "$IS_ERROR" = "true" ]; then
                    HAS_ERROR=true
                    CONTENT=$(echo "$line" | jq -r '.message.content[0].content // empty' 2>/dev/null)
                    echo -e "${RED}✗ Error: ${CONTENT:0:100}...${NC}"
                else
                    echo -e "${GREEN}✓${NC}"
                fi
            fi
            ;;

        "content_block_delta")
            DELTA_TYPE=$(echo "$line" | jq -r '.delta.type // empty' 2>/dev/null)
            case "$DELTA_TYPE" in
                "text_delta")
                    TEXT=$(echo "$line" | jq -r '.delta.text // empty' 2>/dev/null)
                    if [ -n "$TEXT" ]; then
                        if [ "$IN_THINKING" = true ]; then
                            echo -ne "${MAGENTA}${DIM}$TEXT${NC}"
                        else
                            echo -ne "${WHITE}$TEXT${NC}"
                        fi
                    fi
                    ;;
            esac
            ;;

        "content_block_start")
            BLOCK_TYPE=$(echo "$line" | jq -r '.content_block.type // empty' 2>/dev/null)
            if [ "$BLOCK_TYPE" = "thinking" ]; then
                IN_THINKING=true
                echo -e "${MAGENTA}${DIM}[thinking]${NC}"
            fi
            ;;

        "content_block_stop")
            if [ "$IN_THINKING" = true ]; then
                IN_THINKING=false
                echo ""
            fi
            ;;

        "result")
            # Extract metrics
            COST=$(echo "$line" | jq -r '.cost_usd // 0' 2>/dev/null)
            INPUT_TOKENS=$(echo "$line" | jq -r '.usage.input_tokens // 0' 2>/dev/null)
            OUTPUT_TOKENS=$(echo "$line" | jq -r '.usage.output_tokens // 0' 2>/dev/null)
            DURATION=$(echo "$line" | jq -r '.duration_ms // 0' 2>/dev/null)

            echo ""
            echo -e "${GREEN}${BOLD}═══ Execution Complete ═══${NC}"
            [ "$COST" != "0" ] && echo -e "${GRAY}Cost: \$$COST${NC}"
            [ "$INPUT_TOKENS" != "0" ] && echo -e "${GRAY}Input: $INPUT_TOKENS tokens${NC}"
            [ "$OUTPUT_TOKENS" != "0" ] && echo -e "${GRAY}Output: $OUTPUT_TOKENS tokens${NC}"
            [ "$DURATION" != "0" ] && echo -e "${GRAY}Duration: ${DURATION}ms${NC}"
            ;;

        "error")
            HAS_ERROR=true
            ERROR=$(echo "$line" | jq -r '.error.message // .message // empty' 2>/dev/null)
            echo -e "${RED}${BOLD}ERROR: $ERROR${NC}"
            ;;
    esac
done

# Exit with error code if there were errors
if [ "$HAS_ERROR" = true ]; then
    exit 1
fi
