# bd-da08b7c8 — detection & exit-code coverage verification

Child of botburro-6b01bc9d (detection half). Verifies that the in-tree
`bead-health-check.sh` suite actually matches the parent acceptance list, by
mutation testing rather than by reading the tests.

**Date:** 2026-09-16 · **Suite:** `bash tests/test_bead_health_check.sh` — 15/15.

## Acceptance criteria vs. outcome

| Criterion | Outcome |
|---|---|
| Named test per detection, proven by breaking the detection | ✅ for both live detections — but only after fixing the harness (below) |
| Exit codes 0 (clean) / 1 (detection) asserted | ✅ `assert_exit` in both directions, now fatal |
| Suite green via `bash tests/test_bead_health_check.sh` | ✅ 15/15 (monitor suite 4/4) |
| Built on `tests/fixtures/bead_stub.sh` + `tests/lib/` | ✅ lib extended in place; stub and fixture model untouched |

## Gap found and closed: assertions were non-fatal

The harness ran each test as `fn_output=$("$test_fn")` and took the
function's exit status — the last assertion's return code. A failing
assertion mid-test echoed its reason and was overwritten by any later
passing assertion. Mutation proof: replacing every
`select(.assignee == null)` with a never-matching filter (detection fully
blind) left `test_check_only_detects_unclaimed_in_progress` and
`test_autofix_resets_unclaimed_in_progress` **green**. Two weak message
assertions compounded it — `"unclaimed in_progress beads"` and
`"expired claims"` are substrings of the *healthy* messages ("No unclaimed
in_progress beads found", "within threshold").

Fix (`tests/lib/bead_health_test_lib.sh`): failing assertions set
`_TEST_FAILED`; `_invoke_test` runs the test body and returns the flag, so
any failed assertion fails the test while still reporting all of them.
Detection tests now pin the violation lines ("Found 1 unclaimed in_progress
beads", "Found 4 expired claims").

## Script bug the enforcing harness caught immediately

`list_in_progress` logged `bead list failed …` on **stdout**, inside the
caller's `$( )` — the message was captured and discarded, so a CLI failure
exited 1 with no reason shown (the watchdog path already logged outside its
substitution). Now logged to stderr. This is exactly the failure class the
port commit claimed ("CLI failures fail the check instead of reading
healthy") — the exit code held, the diagnostic didn't.

## Mutation matrix (post-fix)

| Mutation | RED tests |
|---|---|
| `select(.assignee == null)` → never matches | `test_check_only_detects_unclaimed_in_progress`, `test_autofix_resets_unclaimed_in_progress`, `test_autofix_creates_incident_bead_for_unclaimed` |
| `[ "$stale_count" -le "$EXPIRED_CLAIM_THRESHOLD" ]` → `true` | `test_detects_expired_claims_above_threshold`, `test_autofix_releases_expired_claims_via_watchdog`, `test_watchdog_held_claims_are_reported_but_not_released`, `test_autofix_incident_is_unique_ref_deduped` |

Both mutations leave the other tests green — the kills are targeted, which
is what makes them meaningful.

## Deviation: the third detection no longer exists

The parent (and this bead's scope) list three detections; HEAD has two. The
claim success rate check (alert below 50%) was retired in 5811a9a's bead-rs
port: its only data source was `br stats --json`
(`.total_claims`/`.successful_claims`), and live `bead --help` confirms
bead-rs has no `stats`. `bead list` JSONL carries no attempt counters and
`bead query`'s whitelisted fields are issue fields only. There is nothing
left to detect, so no test can exist for it; the stub exits 64 on `stats`,
so any accidental resurrection fails loudly. If the metric is wanted again,
re-derive it (e.g. from `bead resolve` attempt outcomes) as its own piece
of work with its own named test. Documented in `docs/BEAD_HEALTH_CHECK.md`.

## Verification environment

Mutations ran in a throwaway `mktemp -d` copy of `scripts/` + `tests/`
(removed afterwards); the repo tree was never mutated. The stub's
`bead-rs` output shapes (`list` JSONL, `watchdog` JSON) are unchanged.
