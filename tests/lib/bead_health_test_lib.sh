#!/usr/bin/env bash
# Shared harness for the bead-health test suites
# (tests/test_bead_health_check.sh, tests/test_bead_health_monitor.sh).
#
# Provides:
#   - a stub `br` CLI (tests/fixtures/br_stub.sh) put at the front of PATH so
#     the scripts under test never touch a real bead store
#   - fixture workspace builders backed by a JSON state file
#   - assertion helpers and a run_test runner with a summary
#
# A suite sources this file, defines test_* functions, then calls
# bead_health_test_main "$@" with the list of test function names.

set -uo pipefail

_TEST_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$_TEST_LIB_DIR/../.." && pwd)"
HEALTH_CHECK_SCRIPT="$REPO_ROOT/scripts/bead-health-check.sh"
HEALTH_MONITOR_SCRIPT="$REPO_ROOT/scripts/bead-health-monitor.sh"
BR_STUB="$REPO_ROOT/tests/fixtures/br_stub.sh"

SUITE_ROOT="$(mktemp -d /tmp/bead-health-tests.XXXXXX)"
STUB_BIN="$SUITE_ROOT/bin"

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TEST_NAMES=()

# ---------------------------------------------------------------------------
# Fixture workspace
# ---------------------------------------------------------------------------

# Create a fresh fixture workspace with an empty bead store. Sets the global
# WS to its path and exports BR_STUB_STATE / BR_STUB_STATS / BR_STUB_LOG for
# it. (The path is returned via $WS rather than stdout on purpose: a test
# function itself runs inside a $( ) subshell, and exports from a nested
# command substitution would be lost.)
new_workspace() {
    local ws="$SUITE_ROOT/ws-$TESTS_RUN-$RANDOM"
    mkdir -p "$ws/.beads" "$STUB_BIN"
    echo '[]' > "$ws/beads-state.json"
    echo '{"total_claims": 0, "successful_claims": 0}' > "$ws/beads-stats.json"
    : > "$ws/br-calls.log"
    export BR_STUB_STATE="$ws/beads-state.json"
    export BR_STUB_STATS="$ws/beads-stats.json"
    export BR_STUB_LOG="$ws/br-calls.log"
    ln -sf "$BR_STUB" "$STUB_BIN/br"
    WS="$ws"
}

# Append a bead to the current fixture state.
#   add_bead <title> <status> [claimed_by] [claim_timestamp]
add_bead() {
    local title="$1" status="$2"
    local claimed_by="${3:-null}" claim_ts="${4:-null}"
    jq -c --arg t "$title" --arg s "$status" --arg cb "$claimed_by" --arg ct "$claim_ts" '
        . + [{id: ("bd-fixture" + (length + 1 | tostring)), title: $t, status: $s,
              priority: 2, issue_type: "task",
              claimed_by: (if $cb == "null" then null else $cb end),
              claim_timestamp: (if $ct == "null" then null else $ct end)}]' \
        "$BR_STUB_STATE" > "$BR_STUB_STATE.tmp"
    mv "$BR_STUB_STATE.tmp" "$BR_STUB_STATE"
}

# Echo the current fixture state as compact JSON (for assertions).
fixture_state() {
    jq -c '.' "$BR_STUB_STATE"
}

# Fetch one bead from the current fixture state as an object.
fixture_bead() {
    jq -c --arg id "$1" '.[] | select(.id == $id)' "$BR_STUB_STATE"
}

# Echo the IDs of incident beads (type=human, title starts with ALERT).
fixture_incidents() {
    jq -c '[.[] | select(.issue_type == "human" and (.title | startswith("ALERT")))]' "$BR_STUB_STATE"
}

# Set claim-success stats for the current fixture.
#   set_stats <total_claims> <successful_claims>
set_stats() {
    printf '{"total_claims": %s, "successful_claims": %s}' "$1" "$2" > "$BR_STUB_STATS"
}

now_ts() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

hours_ago_ts() {
    date -u -d "$1 hours ago" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null ||
        date -u -v-"$1"H +"%Y-%m-%dT%H:%M:%SZ"
}

# Run the health check script against a workspace and echo its output.
# The script's exit code is stored in $SUITE_ROOT/last-rc — read it with
# last_rc afterwards. (A global set inside the $( ) subshell would be lost,
# so the code travels through a file.)
run_health() {
    local ws="$1"
    shift
    local out
    out=$(PATH="$STUB_BIN:$PATH" bash "$HEALTH_CHECK_SCRIPT" --workspace="$ws" "$@" 2>&1)
    printf '%s' "$?" > "$SUITE_ROOT/last-rc"
    printf '%s\n' "$out"
}

# Run the health monitor with --once against colon-separated workspaces.
# Exit code stored like run_health.
run_monitor_once() {
    local workspaces="$1"
    local out
    out=$(PATH="$STUB_BIN:$PATH" BOTBURROW_HEALTH_WORKSPACES="$workspaces" \
        bash "$HEALTH_MONITOR_SCRIPT" --once 2>&1)
    printf '%s' "$?" > "$SUITE_ROOT/last-rc"
    printf '%s\n' "$out"
}

# Exit code of the most recent run_health / run_monitor_once call.
last_rc() {
    cat "$SUITE_ROOT/last-rc"
}

# ---------------------------------------------------------------------------
# Assertions (record failure via RETURN 1 so run_test catches it)
# ---------------------------------------------------------------------------

assert_contains() {
    local needle="$1" haystack="$2" message="${3:-}"
    if ! grep -qF -- "$needle" <<< "$haystack"; then
        echo "    assertion failed: output missing '$needle' ${message:+($message)}"
        return 1
    fi
}

assert_not_contains() {
    local needle="$1" haystack="$2" message="${3:-}"
    if grep -qF -- "$needle" <<< "$haystack"; then
        echo "    assertion failed: output should not contain '$needle' ${message:+($message)}"
        return 1
    fi
}

assert_equals() {
    local actual="$1" expected="$2" message="${3:-}"
    if [ "$actual" != "$expected" ]; then
        echo "    assertion failed: expected '$expected', got '$actual' ${message:+($message)}"
        return 1
    fi
}

assert_exit() {
    local expected="$1" actual="$2" message="${3:-}"
    if [ "$actual" != "$expected" ]; then
        echo "    assertion failed: expected exit $expected, got $actual ${message:+($message)}"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

bead_health_test_cleanup() {
    rm -rf "$SUITE_ROOT"
}
trap bead_health_test_cleanup EXIT

run_test() {
    local test_fn="$1"
    local name="${2:-$test_fn}"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo ""
    echo "[TEST] $name"

    local fn_output
    fn_output=$("$test_fn" 2>&1)
    local fn_rc=$?

    if [ $fn_rc -eq 0 ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo "[PASS] $name"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TEST_NAMES+=("$name")
        echo "[FAIL] $name (exit $fn_rc)"
        [ -n "$fn_output" ] && sed 's/^/    /' <<< "$fn_output"
    fi
    return 0
}

bead_health_test_main() {
    SUITE_NAME="${SUITE_NAME:-Bead Health Test Suite}"

    echo "========================================"
    echo "  $SUITE_NAME"
    echo "========================================"

    for artifact in "$HEALTH_CHECK_SCRIPT" "$HEALTH_MONITOR_SCRIPT" "$BR_STUB"; do
        if [ ! -f "$artifact" ]; then
            echo "[FAIL] required file missing: $artifact"
            exit 1
        fi
    done

    local fn
    for fn in "$@"; do
        run_test "$fn"
    done

    echo ""
    echo "========================================"
    echo "  Test Results"
    echo "========================================"
    echo "Total:  $TESTS_RUN"
    echo "Passed: $TESTS_PASSED"
    echo "Failed: $TESTS_FAILED"
    if [ $TESTS_FAILED -gt 0 ]; then
        printf 'Failed tests:\n'
        local n
        for n in "${FAILED_TEST_NAMES[@]}"; do
            printf '  - %s\n' "$n"
        done
        exit 1
    fi
    echo "All tests passed."
    exit 0
}
