"""CI entry point for the bead-health shell suites.

The starvation guard lives in bash (scripts/bead-health-check.sh,
scripts/bead-health-monitor.sh), so its tests are bash too
(test_bead_health_check.sh, test_bead_health_monitor.sh, hermetic via the
stub `bead` CLI in tests/fixtures/). This wrapper runs them under pytest so
`pytest tests/` — the repo's standard test invocation — covers the shell
scripts as well and a regression fails the build instead of the fleet.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent

SUITES = [
    "test_bead_health_check.sh",
    "test_bead_health_monitor.sh",
]


@pytest.mark.parametrize("suite", SUITES)
def test_bead_health_suite(suite: str) -> None:
    """Run one bash suite; its own pass/fail summary decides the verdict."""
    result = subprocess.run(
        ["bash", str(TESTS_DIR / suite)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"{suite} failed (exit {result.returncode})\n"
        f"--- stdout ---\n{result.stdout}"
        f"--- stderr ---\n{result.stderr}"
    )
