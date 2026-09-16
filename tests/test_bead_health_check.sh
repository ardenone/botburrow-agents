#!/usr/bin/env bash
# Integration tests for scripts/bead-health-check.sh.
#
# Runs the script against fixture workspaces served by the stub `bead` CLI
# (tests/fixtures/bead_stub.sh) so the tests are hermetic: no real bead
# store is touched, and the corrupt states under test (in_progress with no
# assignee) can be built exactly.
#
# Usage:
#   ./tests/test_bead_health_check.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/lib/bead_health_test_lib.sh
source "$SCRIPT_DIR/lib/bead_health_test_lib.sh"

SUITE_NAME="Bead Health Check Script Tests"

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

hours_ago_json_quoted() {
    printf '"%s"' "$(hours_ago_ts "$1")"
}

count_incidents() {
    fixture_incidents | jq 'length'
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# Check-only mode must flag an in_progress bead with no assignee, list its
# id, and not mutate anything.
test_check_only_detects_unclaimed_in_progress() {
    new_workspace
    local ws="$WS"
    local bead_id="bd-fixture1"
    add_bead "Stuck task" in_progress

    local out
    out=$(run_health "$ws" --check-only)

    assert_exit 1 "$(last_rc)" "violations must exit 1"
    assert_contains "unclaimed in_progress beads" "$out"
    assert_contains "$bead_id" "$out" "output must name the stuck bead"

    # check-only must not repair or create incidents
    assert_equals "in_progress" "$(fixture_bead "$bead_id" | jq -r .status)" \
        "check-only must leave the bead untouched"
    assert_equals 0 "$(count_incidents)" "check-only must not create incidents"
}

# --auto-fix must reset an unclaimed in_progress bead to open, clearing the
# assignee with it.
test_autofix_resets_unclaimed_in_progress() {
    new_workspace
    local ws="$WS"
    local bead_id="bd-fixture1"
    add_bead "Stuck task" in_progress

    run_health "$ws" --auto-fix >/dev/null

    assert_exit 1 "$(last_rc)" "auto-fixed violations still exit 1"
    local bead
    bead=$(fixture_bead "$bead_id")
    assert_equals "open" "$(jq -r .status <<< "$bead")" "bead must be reset to open"
    assert_equals "null" "$(jq -r .assignee <<< "$bead")" "assignee must be cleared"
}

# --auto-fix must create a P0 incident bead describing the violation.
test_autofix_creates_incident_bead_for_unclaimed() {
    new_workspace
    local ws="$WS"
    local bead_id="bd-fixture1"
    add_bead "Stuck task" in_progress

    run_health "$ws" --auto-fix >/dev/null

    assert_equals 1 "$(count_incidents)" "exactly one incident bead expected"
    local incident
    incident=$(fixture_incidents | jq '.[0]')
    assert_equals "human" "$(jq -r .issue_type <<< "$incident")" "incident type must be human"
    assert_equals 0 "$(jq -r .priority <<< "$incident")" "unclaimed-bead incident must be P0"
    assert_contains "ALERT: 1 unclaimed in_progress beads detected" \
        "$(jq -r .title <<< "$incident")"
    assert_contains "$bead_id" "$(jq -r .description <<< "$incident")" \
        "incident must list the affected bead"
    assert_contains "$ws" "$(jq -r .description <<< "$incident")" \
        "incident must name the workspace"
}

# --auto-fix must dedupe incident beads through --unique-ref: while a
# violation persists (here: stale claims held by live leases, so nothing is
# ever repaired), a second run the same day must bind to the existing
# incident, not raise a new one.
test_autofix_incident_is_unique_ref_deduped() {
    new_workspace
    local ws="$WS"
    add_bead "Expired 1" in_progress worker-a "$(hours_ago_json_quoted 6)"
    add_bead "Expired 2" in_progress worker-b "$(hours_ago_json_quoted 6)"
    add_bead "Expired 3" in_progress worker-c "$(hours_ago_json_quoted 6)"
    add_bead "Expired 4" in_progress worker-d "$(hours_ago_json_quoted 6)"
    export BEAD_STUB_HELD_IDS="bd-fixture1,bd-fixture2,bd-fixture3,bd-fixture4"

    run_health "$ws" --auto-fix >/dev/null
    run_health "$ws" --auto-fix >/dev/null
    unset BEAD_STUB_HELD_IDS

    assert_equals 1 "$(count_incidents)" \
        "a same-day replay must reuse the existing incident bead"
    local calls
    calls=$(cat "$BEAD_STUB_LOG")
    assert_contains "--unique-ref" "$calls" "incident creates must carry a unique-ref binding"
}

# More expired claims than EXPIRED_CLAIM_THRESHOLD must fail the check.
test_detects_expired_claims_above_threshold() {
    new_workspace
    local ws="$WS"
    add_bead "Expired 1" in_progress worker-a "$(hours_ago_json_quoted 2)"
    add_bead "Expired 2" in_progress worker-b "$(hours_ago_json_quoted 3)"
    add_bead "Expired 3" in_progress worker-c "$(hours_ago_json_quoted 5)"
    add_bead "Expired 4" in_progress worker-d "$(hours_ago_json_quoted 6)"

    local out
    out=$(run_health "$ws" --check-only)

    assert_exit 1 "$(last_rc)" "expired claims above threshold must exit 1"
    assert_contains "expired claims" "$out"
    assert_contains "bd-fixture4" "$out" "output must name an expired bead"
}

# A couple of expired claims is within threshold and must stay green —
# this is the normal "worker died mid-task" case, not starvation.
test_expired_claims_within_threshold_are_healthy() {
    new_workspace
    local ws="$WS"
    add_bead "Expired 1" in_progress worker-a "$(hours_ago_json_quoted 2)"
    add_bead "Expired 2" in_progress worker-b "$(hours_ago_json_quoted 3)"

    local out
    out=$(run_health "$ws" --check-only)

    assert_exit 0 "$(last_rc)" "expired claims within threshold must not fail"
    assert_contains "within threshold" "$out"
}

# --auto-fix releases expired claims through `bead watchdog` (age-based
# detection, release delegated to the CLI) and raises a P1 incident.
test_autofix_releases_expired_claims_via_watchdog() {
    new_workspace
    local ws="$WS"
    add_bead "Expired 1" in_progress worker-a "$(hours_ago_json_quoted 2)"
    add_bead "Expired 2" in_progress worker-b "$(hours_ago_json_quoted 3)"
    add_bead "Expired 3" in_progress worker-c "$(hours_ago_json_quoted 5)"
    add_bead "Expired 4" in_progress worker-d "$(hours_ago_json_quoted 6)"

    local out
    out=$(run_health "$ws" --auto-fix)

    assert_exit 1 "$(last_rc)"
    assert_contains "released" "$out" "output must credit the watchdog release"
    local status
    status=$(fixture_state | jq -r '[.[] | select(.id | startswith("bd-fixture")) | .status] | unique | join(",")')
    assert_equals "open" "$status" "all expired claims must be released to open"

    assert_equals 1 "$(count_incidents)"
    local incident
    incident=$(fixture_incidents | jq '.[0]')
    assert_equals 1 "$(jq -r .priority <<< "$incident")" "expired-claims incident must be P1"
    assert_contains "ALERT: 4 expired claims detected" "$(jq -r .title <<< "$incident")"
}

# Watchdog liveness gating: stale beads whose assignee still holds a valid
# lease are reported but never released — the guard must not drop work a
# live worker is doing just because it has been quiet past the threshold.
test_watchdog_held_claims_are_reported_but_not_released() {
    new_workspace
    local ws="$WS"
    add_bead "Expired 1" in_progress worker-a "$(hours_ago_json_quoted 2)"
    add_bead "Expired 2" in_progress worker-b "$(hours_ago_json_quoted 3)"
    add_bead "Expired 3" in_progress worker-c "$(hours_ago_json_quoted 5)"
    add_bead "Live lease" in_progress worker-live "$(hours_ago_json_quoted 6)"
    export BEAD_STUB_HELD_IDS="bd-fixture4"

    local out
    out=$(run_health "$ws" --auto-fix)
    unset BEAD_STUB_HELD_IDS

    assert_exit 1 "$(last_rc)"
    assert_contains "valid lease" "$out" "output must report the held claim"
    assert_equals "in_progress" "$(fixture_bead bd-fixture4 | jq -r .status)" \
        "a liveness-gated claim must not be released"
    assert_equals 1 "$(count_incidents)" "stale count above threshold still alerts"
}

# Check-only must not release anything: the watchdog runs with --dry-run,
# so detection cannot mutate the store it is only observing.
test_check_only_watchdog_is_dry_run() {
    new_workspace
    local ws="$WS"
    add_bead "Expired 1" in_progress worker-a "$(hours_ago_json_quoted 6)"

    run_health "$ws" --check-only >/dev/null

    assert_equals "in_progress" "$(fixture_bead bd-fixture1 | jq -r .status)" \
        "check-only must leave a stale claim in place"
    local calls
    calls=$(cat "$BEAD_STUB_LOG")
    assert_contains "--dry-run" "$calls" "watchdog must run dry in check-only mode"
}

# A `bead list` failure must fail the check, not read as an empty healthy
# store — the silent-healthy failure mode is the worst one a monitor can
# have.
test_bead_list_failure_fails_the_check() {
    new_workspace
    local ws="$WS"
    add_bead "Queued task" open
    export BEAD_STUB_FAIL_LIST=1

    local out
    out=$(run_health "$ws" --check-only)
    unset BEAD_STUB_FAIL_LIST

    assert_exit 1 "$(last_rc)" "a broken CLI must fail the check"
    assert_contains "bead list failed" "$out"
    assert_not_contains "All health checks passed" "$out" "CLI failure must not read as healthy"
}

# A `bead watchdog` failure must fail the check too — claim freshness is
# half the guard, and losing it silently halves the detection window.
test_bead_watchdog_failure_fails_the_check() {
    new_workspace
    local ws="$WS"
    add_bead "Queued task" open
    export BEAD_STUB_FAIL_WATCHDOG=1

    local out
    out=$(run_health "$ws" --check-only)
    unset BEAD_STUB_FAIL_WATCHDOG

    assert_exit 1 "$(last_rc)" "a broken watchdog must fail the check"
    assert_contains "bead watchdog failed" "$out"
}

# A clean workspace must exit 0 — the guard's green path. This regressed
# once: a miscount made every healthy run report a P0 violation.
test_healthy_workspace_exits_zero() {
    new_workspace
    local ws="$WS"
    add_bead "Queued task" open

    local out
    out=$(run_health "$ws" --check-only)

    assert_exit 0 "$(last_rc)" "healthy workspace must exit 0"
    assert_contains "All health checks passed" "$out"
    assert_not_contains "[ERROR]" "$out" "no errors on a healthy workspace"
}

# An in_progress bead with a live assignee and fresh activity is healthy —
# regression guard for the bd-8q53 false-positive class.
test_claimed_in_progress_bead_is_healthy() {
    new_workspace
    local ws="$WS"
    add_bead "Active task" in_progress worker-9 "$(printf '"%s"' "$(now_ts)")"

    local out
    out=$(run_health "$ws" --check-only)

    assert_exit 0 "$(last_rc)" "a live claim must not be flagged"
    assert_contains "All health checks passed" "$out"
}

# Usage contract: a bad workspace path exits 1 without touching any store.
test_unknown_workspace_exits_one() {
    new_workspace
    local ws="$WS"

    run_health "/nonexistent/workspace-$$" --check-only >/dev/null

    assert_exit 1 "$(last_rc)" "missing workspace must exit 1"
}

# --auto-fix on a healthy workspace must be a no-op: exit 0, no resets, no
# incidents. The monitor runs every workspace with --auto-fix on a timer, so
# a fix path that damages live claims would be worse than the starvation it
# guards against.
test_autofix_on_healthy_workspace_is_a_noop() {
    new_workspace
    local ws="$WS"
    add_bead "Queued task" open
    add_bead "Active task" in_progress worker-9 "$(printf '"%s"' "$(now_ts)")"

    local out
    out=$(run_health "$ws" --auto-fix)

    assert_exit 0 "$(last_rc)" "healthy workspace must exit 0 even under --auto-fix"
    assert_contains "All health checks passed" "$out"
    assert_equals 0 "$(count_incidents)" "no incidents on a healthy workspace"
    assert_equals "in_progress" "$(fixture_bead bd-fixture2 | jq -r .status)" \
        "a live claim must survive an auto-fix run"
}

# ---------------------------------------------------------------------------

bead_health_test_main \
    test_check_only_detects_unclaimed_in_progress \
    test_autofix_resets_unclaimed_in_progress \
    test_autofix_creates_incident_bead_for_unclaimed \
    test_autofix_incident_is_unique_ref_deduped \
    test_detects_expired_claims_above_threshold \
    test_expired_claims_within_threshold_are_healthy \
    test_autofix_releases_expired_claims_via_watchdog \
    test_watchdog_held_claims_are_reported_but_not_released \
    test_check_only_watchdog_is_dry_run \
    test_bead_list_failure_fails_the_check \
    test_bead_watchdog_failure_fails_the_check \
    test_healthy_workspace_exits_zero \
    test_claimed_in_progress_bead_is_healthy \
    test_unknown_workspace_exits_one \
    test_autofix_on_healthy_workspace_is_a_noop
