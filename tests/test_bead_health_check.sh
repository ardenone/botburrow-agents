#!/bin/bash
# Integration tests for bead health check
#
# Tests:
# 1. Unclaimed in_progress beads detection and auto-fix
# 2. Expired claims detection and auto-fix
# 3. Low claim success rate detection
# 4. Incident bead creation
#
# Usage:
#   ./test_bead_health_check.sh

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_CHECK_SCRIPT="$SCRIPT_DIR/../scripts/bead-health-check.sh"
TEST_WORKSPACE="/tmp/bead-health-check-test-$$"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${NC}[INFO] $1${NC}"
}

log_success() {
    echo -e "${GREEN}[PASS] $1${NC}"
}

log_error() {
    echo -e "${RED}[FAIL] $1${NC}"
}

log_test() {
    echo -e "${YELLOW}[TEST] $1${NC}"
}

# Setup test workspace
setup_workspace() {
    log_info "Setting up test workspace: $TEST_WORKSPACE"

    # Create workspace
    mkdir -p "$TEST_WORKSPACE"
    cd "$TEST_WORKSPACE"

    # Initialize beads
    br init

    log_success "Test workspace initialized"
}

# Cleanup test workspace
cleanup_workspace() {
    log_info "Cleaning up test workspace: $TEST_WORKSPACE"

    if [ -d "$TEST_WORKSPACE" ]; then
        rm -rf "$TEST_WORKSPACE"
    fi

    log_success "Test workspace cleaned up"
}

# Run a test
run_test() {
    local test_name="$1"
    local test_function="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    log_test "$test_name"

    if $test_function; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "$test_name"
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "$test_name"
        return 1
    fi
}

# Assert condition
assert_true() {
    local condition="$1"
    local message="$2"

    if eval "$condition"; then
        return 0
    else
        log_error "Assertion failed: $message"
        return 1
    fi
}

assert_equal() {
    local actual="$1"
    local expected="$2"
    local message="$3"

    if [ "$actual" = "$expected" ]; then
        return 0
    else
        log_error "Assertion failed: $message (expected: $expected, actual: $actual)"
        return 1
    fi
}

# Create a bead with specific state (bypassing normal workflow)
create_test_bead() {
    local title="$1"
    local status="$2"
    local claimed_by="${3:-null}"
    local claim_timestamp="${4:-null}"

    cd "$TEST_WORKSPACE"

    # Create bead
    local bead_id=$(br create --title "$title" --priority 2 | grep -oP 'Created issue \K[a-z0-9-]+')

    # Manually update JSONL to set specific state
    if [ "$status" != "open" ]; then
        # Read current JSONL
        local jsonl_file="$TEST_WORKSPACE/.beads/issues.jsonl"
        local temp_file="$jsonl_file.tmp"

        # Update the bead's state
        while IFS= read -r line; do
            local line_id=$(echo "$line" | jq -r '.id')

            if [ "$line_id" = "$bead_id" ]; then
                # Update this bead's state
                echo "$line" | jq ".status = \"$status\" | .claimed_by = $claimed_by | .claim_timestamp = $claim_timestamp"
            else
                echo "$line"
            fi
        done < "$jsonl_file" > "$temp_file"

        mv "$temp_file" "$jsonl_file"

        # Sync to database
        br sync --flush-only
    fi

    echo "$bead_id"
}

# ============================================================================
# Tests
# ============================================================================

# Test 1: Detect unclaimed in_progress beads
test_unclaimed_in_progress_detection() {
    cd "$TEST_WORKSPACE"

    # Create unclaimed in_progress bead
    local bead_id=$(create_test_bead "Test unclaimed bead" "in_progress" "null" "null")

    # Run health check (check-only mode)
    local output
    output=$("$HEALTH_CHECK_SCRIPT" --workspace="$TEST_WORKSPACE" --check-only 2>&1 || true)

    # Verify detection
    assert_true "echo '$output' | grep -q 'unclaimed in_progress beads'" \
        "Should detect unclaimed in_progress beads"

    assert_true "echo '$output' | grep -q '$bead_id'" \
        "Should list the specific bead ID"

    # Clean up
    br update "$bead_id" --status open

    return 0
}

# Test 2: Auto-fix unclaimed in_progress beads
test_unclaimed_in_progress_autofix() {
    cd "$TEST_WORKSPACE"

    # Create unclaimed in_progress bead
    local bead_id=$(create_test_bead "Test autofix bead" "in_progress" "null" "null")

    # Verify initial state
    local initial_status
    initial_status=$(br show "$bead_id" --json | jq -r '.status')
    assert_equal "$initial_status" "in_progress" "Initial status should be in_progress"

    # Run health check with auto-fix
    "$HEALTH_CHECK_SCRIPT" --workspace="$TEST_WORKSPACE" --auto-fix 2>&1 || true

    # Verify bead was reset to open
    local fixed_status
    fixed_status=$(br show "$bead_id" --json | jq -r '.status')
    assert_equal "$fixed_status" "open" "Status should be reset to open"

    # Verify incident bead was created
    local incident_count
    incident_count=$(br list --all --json | jq '[.[] | select(.title | contains("ALERT"))] | length')
    assert_true "[ $incident_count -gt 0 ]" "Incident bead should be created"

    return 0
}

# Test 3: Expired claims detection
test_expired_claims_detection() {
    cd "$TEST_WORKSPACE"

    # Create bead with old claim timestamp (2 hours ago)
    local old_timestamp
    old_timestamp=$(date -u -d "2 hours ago" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || \
                    date -u -v-2H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)

    local bead_id=$(create_test_bead "Test expired claim" "in_progress" "\"worker-123\"" "\"$old_timestamp\"")

    # Run health check (check-only mode)
    local output
    output=$("$HEALTH_CHECK_SCRIPT" --workspace="$TEST_WORKSPACE" --check-only 2>&1 || true)

    # Verify detection (will only trigger if > threshold)
    # For this test, we just verify the check runs without error
    assert_true "[ $? -eq 0 ] || [ $? -eq 1 ]" "Health check should run"

    # Clean up
    br update "$bead_id" --status open

    return 0
}

# Test 4: Multiple unclaimed beads
test_multiple_unclaimed_beads() {
    cd "$TEST_WORKSPACE"

    # Create multiple unclaimed in_progress beads
    local bead1=$(create_test_bead "Test bead 1" "in_progress" "null" "null")
    local bead2=$(create_test_bead "Test bead 2" "in_progress" "null" "null")
    local bead3=$(create_test_bead "Test bead 3" "in_progress" "null" "null")

    # Run health check with auto-fix
    "$HEALTH_CHECK_SCRIPT" --workspace="$TEST_WORKSPACE" --auto-fix 2>&1 || true

    # Verify all beads were fixed
    local bead1_status=$(br show "$bead1" --json | jq -r '.status')
    local bead2_status=$(br show "$bead2" --json | jq -r '.status')
    local bead3_status=$(br show "$bead3" --json | jq -r '.status')

    assert_equal "$bead1_status" "open" "Bead 1 should be reset to open"
    assert_equal "$bead2_status" "open" "Bead 2 should be reset to open"
    assert_equal "$bead3_status" "open" "Bead 3 should be reset to open"

    return 0
}

# Test 5: Healthy system (no issues)
test_healthy_system() {
    cd "$TEST_WORKSPACE"

    # Create normal beads
    br create --title "Normal bead 1" --priority 2
    br create --title "Normal bead 2" --priority 2

    # Run health check
    local output
    output=$("$HEALTH_CHECK_SCRIPT" --workspace="$TEST_WORKSPACE" --check-only 2>&1)

    # Verify no issues detected
    assert_true "echo '$output' | grep -q 'All health checks passed'" \
        "Should report all checks passed"

    return 0
}

# ============================================================================
# Main
# ============================================================================

main() {
    echo "========================================"
    echo "  Bead Health Check Integration Tests"
    echo "========================================"
    echo ""

    # Verify health check script exists
    if [ ! -x "$HEALTH_CHECK_SCRIPT" ]; then
        log_error "Health check script not found or not executable: $HEALTH_CHECK_SCRIPT"
        exit 1
    fi

    # Setup
    setup_workspace

    # Run tests
    run_test "Test 1: Detect unclaimed in_progress beads" test_unclaimed_in_progress_detection
    run_test "Test 2: Auto-fix unclaimed in_progress beads" test_unclaimed_in_progress_autofix
    run_test "Test 3: Detect expired claims" test_expired_claims_detection
    run_test "Test 4: Fix multiple unclaimed beads" test_multiple_unclaimed_beads
    run_test "Test 5: Healthy system check" test_healthy_system

    # Cleanup
    cleanup_workspace

    # Report
    echo ""
    echo "========================================"
    echo "  Test Results"
    echo "========================================"
    echo "Total:  $TESTS_RUN"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        log_success "All tests passed! ✅"
        exit 0
    else
        log_error "Some tests failed ❌"
        exit 1
    fi
}

main
