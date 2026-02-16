#!/bin/bash
# Bead Health Check - Detects and recovers from stuck beads
#
# Detects:
# 1. Unclaimed in_progress beads (status=in_progress, claimed_by=null)
# 2. Expired claims (claim_timestamp > 1 hour old)
# 3. Low claim success rate (< 50%)
#
# Auto-recovery:
# - Reset invalid beads to "open" status
# - Create incident bead for monitoring
# - Log violations with bead details
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
LOW_SUCCESS_RATE_THRESHOLD=50  # Alert if < 50% success rate

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
    echo "Run: cd $WORKSPACE && br init"
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

# Calculate timestamp N hours ago
hours_ago_timestamp() {
    local hours=$1
    date -u -d "$hours hours ago" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || \
    date -u -v-${hours}H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || \
    echo ""
}

# Create incident bead
create_incident_bead() {
    local title="$1"
    local description="$2"
    local priority="${3:-1}"

    log_warning "Creating incident bead: $title"

    br create --type human \
        --priority "$priority" \
        --title "$title" \
        --description "$description"
}

# ============================================================================
# Health Check Functions
# ============================================================================

# Check #1: Unclaimed in_progress beads
check_unclaimed_in_progress() {
    log_info "Checking for unclaimed in_progress beads..."

    # Get all in_progress beads
    local in_progress_beads
    in_progress_beads=$(br list --status in_progress --all --json 2>/dev/null || echo "[]")

    # Filter for beads with claimed_by=null
    local unclaimed_beads
    unclaimed_beads=$(echo "$in_progress_beads" | jq -r '.[] | select(.claimed_by == null) | .id' 2>/dev/null || echo "")

    local unclaimed_count
    unclaimed_count=$(echo "$unclaimed_beads" | grep -c "^bd-" 2>/dev/null || echo "0")

    if [ "$unclaimed_count" -eq 0 ]; then
        log_success "No unclaimed in_progress beads found"
        return 0
    fi

    log_error "Found $unclaimed_count unclaimed in_progress beads (P0 severity)"

    # Log details
    echo "$in_progress_beads" | jq -r '.[] | select(.claimed_by == null) | "  - \(.id): \(.title)"' 2>/dev/null

    if [ "$AUTO_FIX" = true ] && [ "$CHECK_ONLY" = false ]; then
        log_warning "Auto-fixing unclaimed beads..."

        while IFS= read -r bead_id; do
            if [ -n "$bead_id" ] && [[ "$bead_id" =~ ^bd- ]]; then
                log_info "Resetting $bead_id to open status"
                br update "$bead_id" --status open
                log_success "Reset $bead_id"
            fi
        done <<< "$unclaimed_beads"

        # Create incident bead
        create_incident_bead \
            "ALERT: $unclaimed_count unclaimed in_progress beads detected" \
            "## Problem
Detected $unclaimed_count beads in invalid state:
- status: in_progress
- claimed_by: null (should have worker ID)
- claim_timestamp: null (should have timestamp)

## Auto-Recovery
All beads were automatically reset to 'open' status.

## Affected Beads
$(echo "$in_progress_beads" | jq -r '.[] | select(.claimed_by == null) | "- \(.id): \(.title)"' 2>/dev/null)

## Timestamp
$(now_timestamp)

## Workspace
$WORKSPACE

## Prevention
Consider:
1. Adding atomic claim acquisition
2. Adding state validation
3. Adding periodic integrity checks" \
            0

        return 1
    fi

    return 1
}

# Check #2: Expired claims
check_expired_claims() {
    log_info "Checking for expired claims (> $CLAIM_EXPIRY_HOURS hour)..."

    # Calculate cutoff timestamp
    local cutoff_timestamp
    cutoff_timestamp=$(hours_ago_timestamp "$CLAIM_EXPIRY_HOURS")

    if [ -z "$cutoff_timestamp" ]; then
        log_warning "Could not calculate cutoff timestamp (date utility issue)"
        return 0
    fi

    # Get all in_progress beads
    local in_progress_beads
    in_progress_beads=$(br list --status in_progress --all --json 2>/dev/null || echo "[]")

    # Filter for beads with claim_timestamp older than cutoff
    local expired_beads
    expired_beads=$(echo "$in_progress_beads" | jq -r --arg cutoff "$cutoff_timestamp" \
        '.[] | select(.claim_timestamp != null and .claim_timestamp < $cutoff) | .id' 2>/dev/null || echo "")

    local expired_count
    expired_count=$(echo "$expired_beads" | grep -c "^bd-" 2>/dev/null || echo "0")

    if [ "$expired_count" -eq 0 ]; then
        log_success "No expired claims found"
        return 0
    fi

    if [ "$expired_count" -le "$EXPIRED_CLAIM_THRESHOLD" ]; then
        log_info "Found $expired_count expired claims (within threshold of $EXPIRED_CLAIM_THRESHOLD)"
        return 0
    fi

    log_error "Found $expired_count expired claims (> $EXPIRED_CLAIM_THRESHOLD threshold, P1 severity)"

    # Log details
    echo "$in_progress_beads" | jq -r --arg cutoff "$cutoff_timestamp" \
        '.[] | select(.claim_timestamp != null and .claim_timestamp < $cutoff) | "  - \(.id): \(.title) (claimed by \(.claimed_by // "unknown"))"' 2>/dev/null

    if [ "$AUTO_FIX" = true ] && [ "$CHECK_ONLY" = false ]; then
        log_warning "Auto-fixing expired claims..."

        while IFS= read -r bead_id; do
            if [ -n "$bead_id" ] && [[ "$bead_id" =~ ^bd- ]]; then
                log_info "Resetting $bead_id to open status"
                br update "$bead_id" --status open
                log_success "Reset $bead_id"
            fi
        done <<< "$expired_beads"

        # Create incident bead
        create_incident_bead \
            "ALERT: $expired_count expired claims detected" \
            "## Problem
Detected $expired_count beads with claims older than $CLAIM_EXPIRY_HOURS hour(s).

## Auto-Recovery
All expired claims were automatically reset to 'open' status.

## Affected Beads
$(echo "$in_progress_beads" | jq -r --arg cutoff "$cutoff_timestamp" \
    '.[] | select(.claim_timestamp != null and .claim_timestamp < $cutoff) | "- \(.id): \(.title) (claimed by \(.claimed_by // "unknown"))"' 2>/dev/null)

## Timestamp
$(now_timestamp)

## Workspace
$WORKSPACE" \
            1

        return 1
    fi

    return 1
}

# Check #3: Low claim success rate
check_claim_success_rate() {
    log_info "Checking claim success rate..."

    # Get stats
    local stats
    stats=$(br stats --json 2>/dev/null || echo "{}")

    # Extract metrics
    local total_claims
    local successful_claims
    total_claims=$(echo "$stats" | jq -r '.total_claims // 0' 2>/dev/null || echo "0")
    successful_claims=$(echo "$stats" | jq -r '.successful_claims // 0' 2>/dev/null || echo "0")

    if [ "$total_claims" -eq 0 ]; then
        log_info "No claim attempts yet"
        return 0
    fi

    # Calculate success rate
    local success_rate
    success_rate=$(echo "scale=2; ($successful_claims * 100) / $total_claims" | bc -l 2>/dev/null || echo "0")

    log_info "Claim success rate: ${success_rate}% ($successful_claims/$total_claims)"

    # Compare with threshold
    if (( $(echo "$success_rate < $LOW_SUCCESS_RATE_THRESHOLD" | bc -l) )); then
        log_error "Claim success rate is below ${LOW_SUCCESS_RATE_THRESHOLD}% threshold (P1 severity)"

        if [ "$CHECK_ONLY" = false ]; then
            # Create incident bead (no auto-fix for this check)
            create_incident_bead \
                "ALERT: Low claim success rate (${success_rate}%)" \
                "## Problem
Claim success rate has dropped to ${success_rate}% (threshold: ${LOW_SUCCESS_RATE_THRESHOLD}%).

## Metrics
- Total claims: $total_claims
- Successful claims: $successful_claims
- Success rate: ${success_rate}%

## Possible Causes
1. Database corruption (unclaimed in_progress beads)
2. Worker contention issues
3. Race conditions in claim acquisition

## Recommended Actions
1. Run health check with --auto-fix to reset stuck beads
2. Review worker logs for errors
3. Check for unclaimed in_progress beads
4. Investigate claim acquisition logic

## Timestamp
$(now_timestamp)

## Workspace
$WORKSPACE" \
                1
        fi

        return 1
    fi

    log_success "Claim success rate is healthy (${success_rate}%)"
    return 0
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

    check_claim_success_rate || exit_code=1
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
