"""python -m pytest tests/test_instrumentation_overhead.py -v

Unit tests for the statistical helpers in scripts/instrumentation_overhead.py
(percentile, bootstrap CI). The actual paired GPU benchmark is not run on
every test invocation — it takes minutes and needs a GPU; it is a separate,
explicit, real measurement recorded in
artifacts/instrumentation/overhead_report_canonical_run.json and discussed in
docs/WP1_INSTRUMENTATION.md, not something this fast unit-test file
reproduces per CI run.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.instrumentation_overhead import _bootstrap_ci, _percentile


def test_percentile_median_of_odd_list():
    assert _percentile([1.0, 2.0, 3.0], 0.5) == 2.0


def test_percentile_p0_and_p100():
    values = [5.0, 1.0, 3.0]
    assert _percentile(values, 0.0) == 1.0
    assert _percentile(values, 1.0) == 5.0


def test_percentile_empty_list_is_zero():
    assert _percentile([], 0.5) == 0.0


def test_percentile_single_value():
    assert _percentile([7.0], 0.9) == 7.0


def test_bootstrap_ci_tight_for_constant_deltas():
    deltas = [0.01] * 50
    lower, upper = _bootstrap_ci(deltas, resamples=500, seed=1)
    assert lower == pytest.approx(0.01, abs=1e-9)
    assert upper == pytest.approx(0.01, abs=1e-9)


def test_bootstrap_ci_widens_with_variance():
    low_variance = [0.01, 0.0105, 0.0098, 0.0102] * 10
    high_variance = [0.0, 0.02, -0.01, 0.03] * 10
    lo1, hi1 = _bootstrap_ci(low_variance, resamples=1000, seed=1)
    lo2, hi2 = _bootstrap_ci(high_variance, resamples=1000, seed=1)
    assert (hi2 - lo2) > (hi1 - lo1)


def test_bootstrap_ci_is_reproducible_given_same_seed():
    deltas = [0.01, 0.02, -0.005, 0.015, 0.008]
    result_a = _bootstrap_ci(deltas, resamples=500, seed=42)
    result_b = _bootstrap_ci(deltas, resamples=500, seed=42)
    assert result_a == result_b
