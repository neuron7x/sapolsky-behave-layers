"""python -m pytest tests/test_instrumentation_stats.py -v

Example-based coverage of the canonical stats helpers (property-based coverage
is in test_instrumentation_properties.py).
"""

import pytest

from cwc.instrumentation.stats import bootstrap_ci, percentile


def test_percentile_empty_is_zero():
    assert percentile([], 0.5) == 0.0


def test_percentile_single_element():
    assert percentile([3.0], 0.9) == 3.0


def test_percentile_interpolates():
    # midpoint between 0 and 10 at q=0.5 over [0, 10]
    assert percentile([0.0, 10.0], 0.5) == 5.0


def test_percentile_constant_is_exact():
    value = 0.9655213702332301
    for q in (0.0, 0.5, 0.95, 1.0):
        assert percentile([value] * 7, q) == value  # exact, not approx


def test_bootstrap_ci_empty_is_zero():
    assert bootstrap_ci([], seed=1) == (0.0, 0.0)


def test_bootstrap_ci_single_element():
    assert bootstrap_ci([0.5], seed=1) == (0.5, 0.5)


def test_bootstrap_ci_constant_is_exact():
    value = 0.9655213702332301
    lower, upper = bootstrap_ci([value] * 5, resamples=200, seed=3)
    assert lower == value
    assert upper == value


def test_bootstrap_ci_reproducible_given_seed():
    deltas = [0.01, 0.02, -0.005, 0.015, 0.008]
    assert bootstrap_ci(deltas, resamples=300, seed=42) == bootstrap_ci(deltas, resamples=300, seed=42)


def test_bootstrap_ci_lower_le_upper():
    deltas = [0.0, 0.02, -0.01, 0.03, 0.005, -0.002]
    lower, upper = bootstrap_ci(deltas, resamples=500, seed=9)
    assert lower <= upper


def test_bootstrap_ci_confidence_widens_interval():
    deltas = [0.0, 0.02, -0.01, 0.03, 0.005, -0.002, 0.011, -0.004]
    lo90, hi90 = bootstrap_ci(deltas, resamples=1000, seed=9, confidence=0.90)
    lo99, hi99 = bootstrap_ci(deltas, resamples=1000, seed=9, confidence=0.99)
    assert (hi99 - lo99) >= (hi90 - lo90)


@pytest.mark.parametrize("q", [0.0, 0.5, 1.0])
def test_percentile_endpoints(q):
    values = [4.0, 1.0, 9.0, 2.0]
    result = percentile(values, q)
    assert min(values) <= result <= max(values)
