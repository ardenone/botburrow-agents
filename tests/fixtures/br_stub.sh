#!/usr/bin/env bash
# Test double for the `br` bead CLI, used by the bead-health test suites.
#
# The health-check scripts shell out to `br`. On this box that resolves to
# bead-rs; in CI containers it resolves to nothing. Running the real CLI
# against a fixture workspace would couple the tests to one backend's schema
# and output format, and the corrupted states under test (in_progress with no
# claimant) are exactly the states the real CLI refuses to create. So the
# stub serves bead state from a JSON file the test controls.
#
# Supported subcommands — only what the scripts under test actually call:
#   br init
#   br list [--status <status>] --all --json
#   br show <id> --json
#   br update <id> --status open
#   br create --title T [--priority N] [--type T] [--description D]
#   br stats --json
#
# Environment:
#   BR_STUB_STATE  (required) JSON array file holding the bead state
#   BR_STUB_STATS  (optional) JSON file returned by `br stats --json`
#   BR_STUB_LOG    (optional) file receiving one line per invocation
#
# Anything else exits 64 so script drift fails loudly instead of quietly
# comparing against an empty result.

set -euo pipefail

if [ -n "${BR_STUB_LOG:-}" ]; then
    printf '%s\n' "br $*" >> "$BR_STUB_LOG"
fi

STATE_FILE="${BR_STUB_STATE:?BR_STUB_STATE is required}"

cmd="${1:-}"
shift || true

next_bead_id() {
    local n
    n=$(jq 'length' "$STATE_FILE")
    printf 'bd-test%04d' "$((n + 1))"
}

case "$cmd" in
    init)
        mkdir -p .beads
        ;;

    list)
        status_filter=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --status)
                    status_filter="$2"
                    shift 2
                    ;;
                --all | --json)
                    shift
                    ;;
                *)
                    echo "br-stub: unknown list flag: $1" >&2
                    exit 64
                    ;;
            esac
        done
        if [ -n "$status_filter" ]; then
            jq -c --arg s "$status_filter" '[.[] | select(.status == $s)]' "$STATE_FILE"
        else
            jq -c '.' "$STATE_FILE"
        fi
        ;;

    show)
        bead_id="${1:-}"
        shift || true
        while [ $# -gt 0 ]; do
            case "$1" in
                --json) shift ;;
                *) echo "br-stub: unknown show flag: $1" >&2; exit 64 ;;
            esac
        done
        if [ -z "$bead_id" ]; then
            echo "br-stub: show requires a bead id" >&2
            exit 64
        fi
        jq -c --arg id "$bead_id" '.[] | select(.id == $id)' "$STATE_FILE"
        ;;

    update)
        bead_id="${1:-}"
        shift || true
        new_status=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --status) new_status="$2"; shift 2 ;;
                *) echo "br-stub: unknown update flag: $1" >&2; exit 64 ;;
            esac
        done
        if [ -z "$bead_id" ] || [ -z "$new_status" ]; then
            echo "br-stub: update requires <id> --status <status>" >&2
            exit 64
        fi
        # Resetting to open also clears claim metadata — that is what "open"
        # means for a previously claimed bead and what the auto-fix path
        # relies on.
        jq -c --arg id "$bead_id" --arg s "$new_status" '
            map(if .id == $id
                then .status = $s | .claimed_by = null | .claim_timestamp = null
                else . end)' "$STATE_FILE" > "$STATE_FILE.tmp"
        mv "$STATE_FILE.tmp" "$STATE_FILE"
        ;;

    create)
        title="" priority="2" issue_type="task" description=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --title) title="$2"; shift 2 ;;
                --priority) priority="$2"; shift 2 ;;
                --type) issue_type="$2"; shift 2 ;;
                --description) description="$2"; shift 2 ;;
                *) echo "br-stub: unknown create flag: $1" >&2; exit 64 ;;
            esac
        done
        bead_id=$(next_bead_id)
        jq -c --arg id "$bead_id" --arg title "$title" --arg priority "$priority" \
            --arg type "$issue_type" --arg desc "$description" \
            '. + [{id: $id, title: $title, status: "open", priority: ($priority | tonumber),
                   issue_type: $type, claimed_by: null, claim_timestamp: null,
                   description: $desc}]' "$STATE_FILE" > "$STATE_FILE.tmp"
        mv "$STATE_FILE.tmp" "$STATE_FILE"
        echo "Created issue $bead_id"
        ;;

    stats)
        while [ $# -gt 0 ]; do
            case "$1" in
                --json) shift ;;
                *) echo "br-stub: unknown stats flag: $1" >&2; exit 64 ;;
            esac
        done
        if [ -n "${BR_STUB_STATS:-}" ]; then
            cat "$BR_STUB_STATS"
        else
            echo '{"total_claims": 0, "successful_claims": 0}'
        fi
        ;;

    *)
        echo "br-stub: unsupported subcommand: $cmd" >&2
        exit 64
        ;;
esac
