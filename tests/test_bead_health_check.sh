#!/usr/bin/env bash
# Integration tests for scripts/bead-health-check.sh.
#
# Runs the script against fixture workspaces served by the stub `br` CLI
# (tests/fixtures/br_stub.sh) so the tests are hermetic: no real bead store
# is touched, and the corrupt states under test (in_progress with no
# claimant) can be built exactly.
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

# Check-only mode must flag an in_progress bead with no claimant, list its
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
# claim metadata with it.
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
    assert_equals "null" "$(jq -r .claimed_by <<< "$bead")" "claimant must be cleared"
    assert_equals "null" "$(jq -r .claim_timestamp <<< "$bead")" "claim timestamp must be cleared"
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

# --auto-fix must reset every expired claim and raise a P1 incident.
test_autofix_resets_expired_claims_and_creates_incident() {
    new_workspace
    local ws="$WS"
    add_bead "Expired 1" in_progress worker-a "$(hours_ago_json_quoted 2)"
    add_bead "Expired 2" in_progress worker-b "$(hours_ago_json_quoted 3)"
    add_bead "Expired 3" in_progress worker-c "$(hours_ago_json_quoted 5)"
    add_bead "Expired 4" in_progress worker-d "$(hours_ago_json_quoted 6)"

    run_health "$ws" --auto-fix >/dev/null

    assert_exit 1 "$(last_rc)"
    local status
    status=$(fixture_state | jq -r '[.[] | select(.id | startswith("bd-fixture")) | .status] | unique | join(",")')
    assert_equals "open" "$status" "all expired claims must be reset to open"

    assert_equals 1 "$(count_incidents)"
    local incident
    incident=$(fixture_incidents | jq '.[0]')
    assert_equals 1 "$(jq -r .priority <<< "$incident")" "expired-claims incident must be P1"
    assert_contains "ALERT: 4 expired claims detected" "$(jq -r .title <<< "$incident")"
}

# A success rate below LOW_SUCCESS_RATE_THRESHOLD must fail the check even
# in check-only mode (where no incident is raised).
test_detects_low_claim_success_rate() {
    new_workspace
    local ws="$WS"
    set_stats 10 2

    local out
    out=$(run_health "$ws" --check-only)

    assert_exit 1 "$(last_rc)" "low claim success rate must exit 1"
    assert_contains "below 50" "$out"
    assert_contains "20%" "$out" "output must report the computed rate"
    assert_equals 0 "$(count_incidents)" "check-only must not create incidents"
}

# Outside check-only mode a low success rate raises a P1 incident bead
# (this check has no auto-fix — it only alerts).
test_low_claim_success_rate_creates_incident() {
    new_workspace
    local ws="$WS"
    set_stats 10 2

    run_health "$ws" >/dev/null

    assert_exit 1 "$(last_rc)"
    assert_equals 1 "$(count_incidents)"
    local incident
    incident=$(fixture_incidents | jq '.[0]')
    assert_equals "human" "$(jq -r .issue_type <<< "$incident")"
    assert_equals 1 "$(jq -r .priority <<< "$incident")"
    assert_contains "ALERT: Low claim success rate" "$(jq -r .title <<< "$incident")"
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

# An in_progress bead with a live claimant and fresh timestamp is healthy —
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
    test_detects_expired_claims_above_threshold \
    test_expired_claims_within_threshold_are_healthy \
    test_autofix_resets_expired_claims_and_creates_incident \
    test_detects_low_claim_success_rate \
    test_low_claim_success_rate_creates_incident \
    test_healthy_workspace_exits_zero \
    test_claimed_in_progress_bead_is_healthy \
    test_unknown_workspace_exits_one \
    test_autofix_on_healthy_workspace_is_a_noop
