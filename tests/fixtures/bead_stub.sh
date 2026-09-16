#!/usr/bin/env bash
# Test double for the `bead` CLI (bead-rs), used by the bead-health suites.
#
# The health-check scripts shell out to `bead`. On this box that resolves to
# bead-rs; in CI containers it resolves to nothing. Running the real CLI
# against a fixture workspace would couple the tests to one backend's schema
# and output format, and the corrupt states under test (in_progress with no
# assignee) are exactly the states the real CLI refuses to create. So the
# stub serves bead state from a JSON file the test controls.
#
# Supported subcommands — only what the scripts under test actually call,
# matching bead-rs's real output shapes (list = JSONL, watchdog = one JSON
# object):
#   bead list --status <status> --json --limit <n>
#   bead watchdog --json --threshold <n>h [--dry-run]
#   bead update <id> --status open
#   bead create --issue-type T --priority N --title T --description D
#               --unique-ref NS:KEY
#
# Environment:
#   BEAD_STUB_STATE         (required) JSON array file holding the bead state
#   BEAD_STUB_LOG           (optional) file receiving one line per invocation
#   BEAD_STUB_FAIL_LIST     (optional) if set, `list` exits 70 — CLI failure
#   BEAD_STUB_FAIL_WATCHDOG (optional) if set, `watchdog` exits 70
#   BEAD_STUB_HELD_IDS      (optional) comma-separated ids the watchdog
#                           reports in lease_valid_but_stale instead of
#                           releasing
#
# Anything else exits 64 so script drift fails loudly instead of quietly
# comparing against an empty result.

set -euo pipefail

if [ -n "${BEAD_STUB_LOG:-}" ]; then
    printf '%s\n' "bead $*" >> "$BEAD_STUB_LOG"
fi

STATE_FILE="${BEAD_STUB_STATE:?BEAD_STUB_STATE is required}"

cmd="${1:-}"
shift || true

next_bead_id() {
    local n
    n=$(jq 'length' "$STATE_FILE")
    printf 'bd-test%04d' "$((n + 1))"
}

# bead-rs stamps updated_at with nanosecond precision
# (2026-09-16T03:35:35.023668126Z); fromdateiso8601 wants whole seconds, so
# strip the fractional part before parsing.
age_seconds_of_bead='(now - ((.updated_at // "1970-01-01T00:00:00Z") | sub("\\.[0-9]+"; "") | fromdateiso8601))'

case "$cmd" in
    list)
        [ -n "${BEAD_STUB_FAIL_LIST:-}" ] && exit 70
        status_filter=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --status)
                    status_filter="$2"
                    shift 2
                    ;;
                --limit)
                    shift 2   # consume the value; fixture stores are tiny
                    ;;
                --json)
                    shift
                    ;;
                *)
                    echo "bead-stub: unknown list flag: $1" >&2
                    exit 64
                    ;;
            esac
        done
        # bead-rs prints JSONL: one object per line.
        if [ -n "$status_filter" ]; then
            jq -c --arg s "$status_filter" '.[] | select(.status == $s)' "$STATE_FILE"
        else
            jq -c '.[]' "$STATE_FILE"
        fi
        ;;

    watchdog)
        [ -n "${BEAD_STUB_FAIL_WATCHDOG:-}" ] && exit 70
        threshold_hours=4 dry_run=false
        while [ $# -gt 0 ]; do
            case "$1" in
                --threshold)
                    threshold_hours="${2%h}"
                    shift 2
                    ;;
                --dry-run) dry_run=true; shift ;;
                --json) shift ;;
                *) echo "bead-stub: unknown watchdog flag: $1" >&2; exit 64 ;;
            esac
        done
        held_ids="${BEAD_STUB_HELD_IDS:-}"
        # Stale = in_progress longer than the threshold (updated_at is the
        # fixture's stand-in for last activity), mirroring bead-rs's
        # age-based detection. Liveness is simulated through
        # BEAD_STUB_HELD_IDS: listed ids keep a valid lease (reported under
        # lease_valid_but_stale, never released); every other stale bead is
        # released unless --dry-run.
        report=$(jq --argjson th "$threshold_hours" --arg held "$held_ids" "
            (\$held | split(\",\") | map(select(length > 0))) as \$held
            | ([.[] | select(.status == \"in_progress\")
                | . + {age_seconds: $age_seconds_of_bead}]) as \$scanned
            | ([\$scanned[] | select(.age_seconds > (\$th * 3600))]) as \$stale
            | {
                total_scanned: (\$scanned | length),
                stale_beads: [\$stale[] | {id, title, assignee,
                    hours_since_update: (.age_seconds / 3600)}],
                released_beads: [\$stale[]
                    | select((.id as \$bid | \$held | contains([\$bid])) | not) | .id],
                lease_valid_but_stale: [\$stale[]
                    | select(.id as \$bid | \$held | contains([\$bid])) | .id]
            }" "$STATE_FILE")
        # Apply releases to the state file unless dry-run.
        if [ "$dry_run" = false ]; then
            jq -c --argjson th "$threshold_hours" --arg held "$held_ids" "
                (\$held | split(\",\") | map(select(length > 0))) as \$held
                | map(if .status == \"in_progress\"
                        and ((.id as \$bid | \$held | contains([\$bid])) | not)
                        and ($age_seconds_of_bead > (\$th * 3600))
                      then .status = \"open\" | .assignee = null
                      else . end)" "$STATE_FILE" > "$STATE_FILE.tmp"
            mv "$STATE_FILE.tmp" "$STATE_FILE"
        fi
        printf '%s\n' "$report"
        ;;

    update)
        bead_id="${1:-}"
        shift || true
        new_status=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --status) new_status="$2"; shift 2 ;;
                *) echo "bead-stub: unknown update flag: $1" >&2; exit 64 ;;
            esac
        done
        if [ -z "$bead_id" ] || [ -z "$new_status" ]; then
            echo "bead-stub: update requires <id> --status <status>" >&2
            exit 64
        fi
        # Resetting to open also clears the assignee — that is what "open"
        # means for a previously claimed bead and what the auto-fix path
        # relies on.
        jq -c --arg id "$bead_id" --arg s "$new_status" '
            map(if .id == $id
                then .status = $s | .assignee = null
                else . end)' "$STATE_FILE" > "$STATE_FILE.tmp"
        mv "$STATE_FILE.tmp" "$STATE_FILE"
        ;;

    create)
        title="" priority="2" issue_type="task" description="" unique_ref=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --title) title="$2"; shift 2 ;;
                --priority) priority="$2"; shift 2 ;;
                --issue-type) issue_type="$2"; shift 2 ;;
                --description) description="$2"; shift 2 ;;
                --unique-ref) unique_ref="$2"; shift 2 ;;
                *) echo "bead-stub: unknown create flag: $1" >&2; exit 64 ;;
            esac
        done
        # --unique-ref dedupe: a replay of a bound ref reports the existing
        # id instead of creating a second bead (matches bead-rs).
        if [ -n "$unique_ref" ]; then
            existing=$(jq -r --arg ref "$unique_ref" \
                '[.[] | select(.unique_ref == $ref) | .id][0] // empty' "$STATE_FILE")
            if [ -n "$existing" ]; then
                echo "EXISTING $existing"
                exit 0
            fi
        fi
        bead_id=$(next_bead_id)
        jq -c --arg id "$bead_id" --arg title "$title" --arg priority "$priority" \
            --arg type "$issue_type" --arg desc "$description" --arg ref "$unique_ref" \
            '. + [{id: $id, title: $title, status: "open", priority: ($priority | tonumber),
                   issue_type: $type, assignee: null, description: $desc,
                   unique_ref: (if $ref == "" then null else $ref end)}]' \
            "$STATE_FILE" > "$STATE_FILE.tmp"
        mv "$STATE_FILE.tmp" "$STATE_FILE"
        echo "$bead_id"
        ;;

    *)
        echo "bead-stub: unsupported subcommand: $cmd" >&2
        exit 64
        ;;
esac
