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

# The override must REPLACE the built-in defaults, not merely add a target:
# with it set, the hard-coded /home/coding workspaces must not be consulted
# at all. This is the proof that the override redirects the monitor — the
# other tests rely on it to reach their fixtures, so a regression to the
# defaults would otherwise only surface as confusing fixture-not-found noise.
test_env_override_replaces_builtin_defaults() {
    new_workspace
    local ws="$WS"
    add_bead "Queued task" open

    local out
    out=$(run_monitor_once "$ws")

    assert_exit 0 "$(last_rc)"
    assert_contains "Checking workspace: $ws" "$out" "the override target must be checked"
    assert_contains "Workspaces: 1" "$out" "the override must yield exactly the listed workspaces"
    assert_not_contains "Checking workspace: /home/coding/botburrow-agents" "$out" \
        "the first built-in default must not be checked while the override is set"
    assert_not_contains "Checking workspace: /home/coding/botburrow-hub" "$out" \
        "no built-in default may be checked while the override is set"
}

# The override's documented second form is space-separated. The split runs
# through `${var//:/ }` + `read -a`, so a change to colon-only splitting
# would silently drop the space form.
test_env_override_accepts_space_separated_workspaces() {
    new_workspace
    local ws_a="$WS"
    new_workspace
    local ws_b="$WS"
    add_bead "Queued task" open

    local out
    out=$(run_monitor_once "$ws_a $ws_b")

    assert_exit 0 "$(last_rc)"
    assert_contains "Workspaces: 2" "$out" "both space-separated workspaces must be configured"
    assert_contains "Checking workspace: $ws_a" "$out" "the first workspace must be checked"
    assert_contains "Checking workspace: $ws_b" "$out" "the second workspace must be checked"
}

# An override that yields no workspaces at all (a colon-only value splits to
# an empty array) must be a clean no-op run: exit 0, nothing checked, and no
# set -u "unbound variable" crash on the empty "${WORKSPACES[@]}".
test_monitor_with_no_workspaces_configured_exits_zero() {
    local out
    out=$(run_monitor_once ":")

    assert_exit 0 "$(last_rc)" "an empty workspace list must not fail the run"
    assert_contains "Workspaces: 0" "$out"
    assert_contains "All health checks passed" "$out"
    assert_not_contains "Checking workspace:" "$out" "nothing can be checked with no workspaces"
}

# A monitor whose sibling check script is missing must count the workspace
# as FAILED (exit 1) and say so — a silent skip here would report green to
# cron while checking nothing. SCRIPT_DIR comes from the monitor's own
# location, so a copy in a bare directory is what hides the check script.
test_monitor_fails_when_check_script_is_absent() {
    new_workspace
    local ws="$WS"

    local bare_dir="$SUITE_ROOT/monitor-without-check"
    mkdir -p "$bare_dir"
    cp "$HEALTH_MONITOR_SCRIPT" "$bare_dir/bead-health-monitor.sh"
    chmod +x "$bare_dir/bead-health-monitor.sh"

    local out
    out=$(PATH="$STUB_BIN:$PATH" BOTBURROW_HEALTH_WORKSPACES="$ws" \
        "$bare_dir/bead-health-monitor.sh" --once 2>&1)
    printf '%s' "$?" > "$SUITE_ROOT/last-rc"

    assert_exit 1 "$(last_rc)" "a missing check script must fail the run"
    assert_contains "Health check script not found" "$out"
    assert_contains "Health checks failed for 1 workspace(s)" "$out"
}

# failed_count must aggregate across the whole list: an early failure must
# not stop the loop, and the final exit code must be the NUMBER of failing
# workspaces (the documented `exit $failed_count` contract), not just 0/1.
#
# Both workspaces are failed through BEAD_STUB_FAIL_LIST because the stub's
# state file is process-global — BEAD_STUB_STATE is exported once for the
# whole monitor run, so per-workspace outcomes are not representable, and a
# first check's auto-fix would otherwise repair the shared state under the
# second workspace's feet.
test_monitor_aggregates_failures_across_workspaces() {
    new_workspace
    local ws_a="$WS"
    new_workspace
    local ws_b="$WS"
    export BEAD_STUB_FAIL_LIST=1

    local out
    out=$(run_monitor_once "$ws_a:$ws_b")
    unset BEAD_STUB_FAIL_LIST

    assert_exit 2 "$(last_rc)" "two failing workspaces must exit 2 (the failed count)"
    assert_contains "Health check failed for $ws_a" "$out" "the first failure must be reported"
    assert_contains "Health check failed for $ws_b" "$out" \
        "the loop must continue past the first failure and check the second workspace"
    assert_contains "Health checks failed for 2 workspace(s)" "$out" \
        "both failing workspaces must be counted"
}

# Direct execution end to end: run_monitor_once execs the monitor as a
# program, and the monitor executes the check script directly. The check's
# own log lines reaching this output is what proves the second hop — the
# sibling was invoked as a program and its shebang resolved bash.
test_monitor_and_check_run_via_direct_execution() {
    new_workspace
    local ws="$WS"
    add_bead "Queued task" open

    local out
    out=$(run_monitor_once "$ws")

    assert_exit 0 "$(last_rc)" "direct execution must work end to end"
    assert_contains "Starting bead health check..." "$out" \
        "the check script's own output must appear — it was executed directly"
    assert_contains "No unclaimed in_progress beads found" "$out" \
        "the check must actually have run against the workspace"
}

# ---------------------------------------------------------------------------

bead_health_test_main \
    test_monitor_healthy_workspaces_exit_zero \
    test_monitor_skips_missing_workspace \
    test_monitor_skips_workspace_without_beads \
    test_monitor_autofixes_violations_and_exits_nonzero \
    test_env_override_replaces_builtin_defaults \
    test_env_override_accepts_space_separated_workspaces \
    test_monitor_with_no_workspaces_configured_exits_zero \
    test_monitor_fails_when_check_script_is_absent \
    test_monitor_aggregates_failures_across_workspaces \
    test_monitor_and_check_run_via_direct_execution
