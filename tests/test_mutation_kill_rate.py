"""python -m pytest tests/test_mutation_kill_rate.py -v -m mutation

Runs the curated mutation probe (scripts/mutation_probe.py) and asserts a 100%
kill rate — every semantically-real defect injected into the mathematical cores
must be caught by the test suite. Marked `mutation` and `slow` because it
re-runs the targeted test subset once per mutant (~30s total); deselect with
`-m "not mutation"` for the fast inner loop.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

pytestmark = [pytest.mark.mutation, pytest.mark.slow]


def test_all_curated_mutants_are_killed():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "mutation_probe.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert "ALL MUTANTS KILLED" in output, output
    assert result.returncode == 0, output
