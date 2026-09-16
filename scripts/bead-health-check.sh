#!/usr/bin/env bash
# Bead Health Check - Detects and recovers from stuck beads
#
# Detects:
# 1. Unclaimed in_progress beads (status=in_progress, assignee=null)
# 2. Expired claims (in_progress beads untouched for more than
#    CLAIM_EXPIRY_HOURS), recovered through `bead watchdog`
#
# Auto-recovery:
# - Reset invalid beads to "open" status
# - Create incident bead for monitoring
# - Log violations with bead details
#
# Ported to the bead-rs CLI (2026-09-16): `list` is JSONL with an `assignee`
# field (the old `claimed_by`/`claim_timestamp` fields no longer exist), an
# assigned in_progress bead is fenced and cannot be reset casually, and the
# retired `stats` subcommand took the claim-success-rate check with it (see
# docs/BEAD_HEALTH_CHECK.md). CLI failures now fail the check instead of
# reading as an empty, healthy store.
#
# Usage:
#   ./bead-health-check.sh --workspace=/path/to/project [--auto-fix]
#   ./bead-health-check.sh --workspace=/path/to/project --check-only

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE=""
AUTO_FIX=false
CHECK_ONLY=false
CLAIM_EXPIRY_HOURS=1
EXPIRED_CLAIM_THRESHOLD=3  # Alert if > 3 expired claims

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
for arg in "$@"; do
    case $arg in
        --workspace=*)
            WORKSPACE="${arg#*=}"
            shift
            ;;
        --auto-fix)
            AUTO_FIX=true
            shift
            ;;
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 --workspace=/path/to/project [--auto-fix] [--check-only]"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$WORKSPACE" ]; then
    echo "Error: --workspace is required"
    exit 1
fi

if [ ! -d "$WORKSPACE" ]; then
    echo "Error: Workspace directory does not exist: $WORKSPACE"
    exit 1
fi

if [ ! -d "$WORKSPACE/.beads" ]; then
    echo "Error: Workspace does not have beads initialized: $WORKSPACE"
    echo "Run: cd $WORKSPACE && bead init"
    exit 1
fi

# Change to workspace
cd "$WORKSPACE"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get current timestamp in ISO8601 format
now_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# List in_progress beads as bead-rs JSONL. Fails the caller on a CLI error —
# a broken `bead` invocation must never read as an empty, healthy store.
list_in_progress() {
    local out rc=0
    out=$(bead list --status in_progress --json --limit 999999 2>/dev/null) || rc=$?
    if [ "$rc" -ne 0 ]; then
        # stderr, not stdout: the caller captures stdout in $( ), so a
        # failure message printed there is swallowed with the empty capture
        # and the check exits 1 with no reason shown to the operator.
        log_error "bead list failed in $WORKSPACE (exit $rc) — cannot check bead state" >&2
        return 1
    fi
    printf '%s' "$out"
}

# Create incident bead, deduplicated per (workspace, violation, day) through
# a --unique-ref binding: a recurring violation re-alerts once per day at
# most instead of once per run.
create_incident_bead() {
    local title="$1"
    local description="$2"
    local priority="${3:-1}"
    local dedupe_key="$4"

    log_warning "Creating incident bead: $title"

    local unique_ref
    unique_ref="bead-health:$(date -u +%Y-%m-%d)-$(basename "$WORKSPACE")-$dedupe_key"

    # Fresh create prints the bare id; a same-day replay prints
    # "EXISTING <id>". Either outcome is fine — print it for the log.
    bead create --issue-type human \
        --priority "$priority" \
        --title "$title" \
        --description "$description" \
        --unique-ref "$unique_ref"
}

# ============================================================================
# Health Check Functions
# ============================================================================

# Check #1: Unclaimed in_progress beads
check_unclaimed_in_progress() {
    log_info "Checking for unclaimed in_progress beads..."

    local in_progress_beads
    in_progress_beads=$(list_in_progress) || return 1

    # JSONL in, JSONL out: select applies per line.
    local unclaimed_beads
    unclaimed_beads=$(printf '%s\n' "$in_progress_beads" \
        | jq -r 'select(.assignee == null) | .id' 2>/dev/null) || unclaimed_beads=""

    local unclaimed_count
    unclaimed_count=$(printf '%s\n' "$in_progress_beads" \
        | jq -s '[.[] | select(.assignee == null)] | length' 2>/dev/null) || unclaimed_count=0

    if [ "$unclaimed_count" -eq 0 ]; then
        log_success "No unclaimed in_progress beads found"
        return 0
    fi

    log_error "Found $unclaimed_count unclaimed in_progress beads (P0 severity)"

    # Log details
    printf '%s\n' "$in_progress_beads" \
        | jq -r 'select(.assignee == null) | "  - \(.id): \(.title)"' 2>/dev/null || true

    if [ "$AUTO_FIX" = true ] && [ "$CHECK_ONLY" = false ]; then
        log_warning "Auto-fixing unclaimed beads..."

        while IFS= read -r bead_id; do
            if [ -n "$bead_id" ]; then
                log_info "Resetting $bead_id to open status"
                # bead-rs fences assigned in_progress beads (lease conflict),
                # so this reset can only ever touch beads no worker holds.
                if bead update "$bead_id" --status open; then
                    log_success "Reset $bead_id"
                else
                    log_error "Could not reset $bead_id (fenced or gone)"
                fi
            fi
        done <<< "$unclaimed_beads"

        # Create incident bead
        create_incident_bead \
            "ALERT: $unclaimed_count unclaimed in_progress beads detected" \
            "## Problem
Detected $unclaimed_count beads in invalid state:
- status: in_progress
- assignee: null (should have a worker)

## Auto-Recovery
All beads were automatically reset to 'open' status.

## Affected Beads
$(printf '%s\n' "$in_progress_beads" | jq -r 'select(.assignee == null) | "- \(.id): \(.title)"' 2>/dev/null)

## Timestamp
$(now_timestamp)

## Workspace
$WORKSPACE

## Prevention
Consider:
1. Adding atomic claim acquisition
2. Adding state validation
3. Adding periodic integrity checks" \
            0 \
            "unclaimed-in-progress"

        return 1
    fi

    return 1
}

# Check #2: Expired claims, detected and recovered via `bead watchdog`.
# Watchdog is age-based on detection (stale_beads) but liveness-gated on
# release: it only releases beads whose assignee process is gone, and
# refuses (lease_valid_but_stale) when it cannot prove the worker is dead.
check_expired_claims() {
    log_info "Checking for expired claims (> $CLAIM_EXPIRY_HOURS hour, via bead watchdog)..."

    local watchdog_args=(--json --threshold "${CLAIM_EXPIRY_HOURS}h")
    if [ "$CHECK_ONLY" = true ]; then
        watchdog_args+=(--dry-run)
    fi

    local watchdog_json rc=0
    watchdog_json=$(bead watchdog "${watchdog_args[@]}" 2>/dev/null) || rc=$?
    if [ "$rc" -ne 0 ] || ! printf '%s' "$watchdog_json" | jq -e . >/dev/null 2>&1; then
        log_error "bead watchdog failed in $WORKSPACE (exit $rc) — cannot check claim freshness"
        return 1
    fi

    local stale_count released_count held_count
    stale_count=$(printf '%s' "$watchdog_json" | jq '.stale_beads | length')
    released_count=$(printf '%s' "$watchdog_json" | jq '.released_beads | length')
    held_count=$(printf '%s' "$watchdog_json" | jq '.lease_valid_but_stale | length')

    if [ "$stale_count" -eq 0 ]; then
        log_success "No expired claims found"
        return 0
    fi

    if [ "$released_count" -gt 0 ]; then
        log_info "bead watchdog released $released_count expired claim(s) (assignee process gone)"
    fi
    if [ "$held_count" -gt 0 ]; then
        log_info "$held_count expired claim(s) held under a valid lease (watchdog could not prove the worker is dead; no release)"
    fi

    # Log details
    printf '%s' "$watchdog_json" \
        | jq -r '.stale_beads[] | "  - \(.id): \(.hours_since_update | floor)h idle (assignee \(.assignee))"' 2>/dev/null || true

    if [ "$stale_count" -le "$EXPIRED_CLAIM_THRESHOLD" ]; then
        log_info "Found $stale_count expired claims (within threshold of $EXPIRED_CLAIM_THRESHOLD)"
        return 0
    fi

    log_error "Found $stale_count expired claims (> $EXPIRED_CLAIM_THRESHOLD threshold, P1 severity)"

    if [ "$AUTO_FIX" = true ] && [ "$CHECK_ONLY" = false ]; then
        # Create incident bead (the watchdog release above was the fix)
        create_incident_bead \
            "ALERT: $stale_count expired claims detected" \
            "## Problem
Detected $stale_count beads with no activity for more than $CLAIM_EXPIRY_HOURS hour(s).

## Auto-Recovery
bead watchdog released $released_count claim(s) whose assignee process is gone;
$held_count remained held under a valid lease (liveness could not be disproven).

## Affected Beads
$(printf '%s' "$watchdog_json" | jq -r '.stale_beads[] | "- \(.id): \(.hours_since_update | floor)h idle (assignee \(.assignee))"' 2>/dev/null)

## Timestamp
$(now_timestamp)

## Workspace
$WORKSPACE" \
            1 \
            "expired-claims"

        return 1
    fi

    return 1
}

# ============================================================================
# Main
# ============================================================================

main() {
    log_info "Starting bead health check..."
    log_info "Workspace: $WORKSPACE"
    log_info "Auto-fix: $AUTO_FIX"
    log_info "Check-only: $CHECK_ONLY"
    echo ""

    local exit_code=0

    # Run all checks
    check_unclaimed_in_progress || exit_code=1
    echo ""

    check_expired_claims || exit_code=1
    echo ""

    if [ $exit_code -eq 0 ]; then
        log_success "All health checks passed ✅"
    else
        log_error "Health check failed ❌"

        if [ "$AUTO_FIX" = false ] && [ "$CHECK_ONLY" = false ]; then
            log_info "Run with --auto-fix to automatically repair issues"
        fi
    fi

    return $exit_code
}

main
