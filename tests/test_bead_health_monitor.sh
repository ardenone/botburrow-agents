#!/usr/bin/env bash
# Integration tests for scripts/bead-health-monitor.sh.
#
# Uses the stub `bead` CLI (tests/fixtures/bead_stub.sh) and the
# BOTBURROW_HEALTH_WORKSPACES override so the monitor can be pointed at
# fixture workspaces instead of the hard-coded /home/coding defaults.
#
# Usage:
#   ./tests/test_bead_health_monitor.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/lib/bead_health_test_lib.sh
source "$SCRIPT_DIR/lib/bead_health_test_lib.sh"

SUITE_NAME="Bead Health Monitor Script Tests"

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# A run over healthy workspaces must exit 0 and actually check them.
test_monitor_healthy_workspaces_exit_zero() {
    new_workspace
    local ws="$WS"
    add_bead "Queued task" open

    local out
    out=$(run_monitor_once "$ws")

    assert_exit 0 "$(last_rc)" "all-healthy run must exit 0"
    assert_contains "Checking workspace: $ws" "$out" "valid workspace must be checked"
    assert_contains "All health checks passed" "$out"
}

# A directory that does not exist must be skipped without failing the run.
test_monitor_skips_missing_workspace() {
    new_workspace
    local ws="$WS"
    local missing="$SUITE_ROOT/does-not-exist"

    local out
    out=$(run_monitor_once "$missing:$ws")

    assert_exit 0 "$(last_rc)" "a missing workspace must not fail the run"
    assert_contains "does not exist" "$out"
    assert_contains "Checking workspace: $ws" "$out" "the real workspace must still be checked"
}

# A directory without .beads/ must be skipped without failing the run.
test_monitor_skips_workspace_without_beads() {
    new_workspace
    local ws="$WS"
    local bare="$SUITE_ROOT/no-beads"
    mkdir -p "$bare"

    local out
    out=$(run_monitor_once "$bare:$ws")

    assert_exit 0 "$(last_rc)" "a beads-less workspace must not fail the run"
    assert_contains "does not have beads" "$out"
    assert_contains "Checking workspace: $ws" "$out"
}

# The monitor runs checks with --auto-fix: a violating workspace is repaired
# and counted as failed (non-zero exit) so cron/systemd see the event.
test_monitor_autofixes_violations_and_exits_nonzero() {
    new_workspace
    local ws="$WS"
    add_bead "Stuck task" in_progress

    local out
    out=$(run_monitor_once "$ws")

    assert_exit 1 "$(last_rc)" "one failed workspace must exit 1"
    assert_contains "Health check failed for $ws" "$out"

    assert_equals "open" "$(fixture_bead bd-fixture1 | jq -r .status)" \
        "monitor must auto-fix the stuck bead"
    assert_equals 1 "$(fixture_incidents | jq 'length')" \
        "monitor must leave an incident bead behind"
}

# ---------------------------------------------------------------------------

bead_health_test_main \
    test_monitor_healthy_workspaces_exit_zero \
    test_monitor_skips_missing_workspace \
    test_monitor_skips_workspace_without_beads \
    test_monitor_autofixes_violations_and_exits_nonzero
