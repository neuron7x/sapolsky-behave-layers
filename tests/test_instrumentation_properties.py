"""Property-based tests (Hypothesis) for the mathematical cores of the CWC WP-1
instrumentation. These assert invariants that must hold for ALL valid inputs,
not hand-picked examples — the strongest correctness statement available short
of a proof.

    python -m pytest tests/test_instrumentation_properties.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
pytest.importorskip("hypothesis", reason="optional property-testing dependency unavailable")

from hypothesis import assume, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cwc.instrumentation.config import InstrumentationMode
from cwc.instrumentation.energy import _trapezoidal_joules
from cwc.instrumentation.event_buffer import EventPool
from cwc.instrumentation.flops import (
    FlopLedger,
    attention_core_flops,
    dense_linear_flops,
    full_causal_pairs,
    full_noncausal_pairs,
    mlp_flops,
    sliding_causal_pairs,
)
from cwc.instrumentation.routing import RoutingCounters, RoutingHistogram
from cwc.instrumentation.stats import bootstrap_ci as _bootstrap_ci
from cwc.instrumentation.stats import percentile as _percentile

# Bounded so the analytical integer products stay quick and readable; the
# invariants they prove are scale-free.
_DIM = st.integers(min_value=0, max_value=4096)
_POS_DIM = st.integers(min_value=1, max_value=4096)
_SEQ = st.integers(min_value=1, max_value=512)


# --------------------------------------------------------------------------- #
# FLOP formulas
# --------------------------------------------------------------------------- #
@given(tokens=_DIM, d_in=_DIM, d_out=_DIM)
def test_dense_linear_flops_is_2mac_and_even(tokens: int, d_in: int, d_out: int) -> None:
    result = dense_linear_flops(tokens=tokens, d_in=d_in, d_out=d_out)
    assert result == 2 * tokens * d_in * d_out
    assert result % 2 == 0
    assert result >= 0


@given(tokens=_POS_DIM, d_in=_POS_DIM, d_out=_POS_DIM, extra=st.integers(min_value=1, max_value=100))
def test_dense_linear_flops_monotonic_in_tokens(tokens: int, d_in: int, d_out: int, extra: int) -> None:
    base = dense_linear_flops(tokens=tokens, d_in=d_in, d_out=d_out)
    more = dense_linear_flops(tokens=tokens + extra, d_in=d_in, d_out=d_out)
    assert more > base


@given(n=_SEQ)
def test_causal_pairs_never_exceed_noncausal(n: int) -> None:
    assert full_causal_pairs(n) <= full_noncausal_pairs(n)


@given(n=_SEQ)
def test_full_causal_pairs_equals_triangular_number(n: int) -> None:
    assert full_causal_pairs(n) == sum(range(1, n + 1))


@given(n=_SEQ, window=st.integers(min_value=1, max_value=512))
def test_sliding_window_never_exceeds_full_causal(n: int, window: int) -> None:
    assert sliding_causal_pairs(n, window) <= full_causal_pairs(n)


@given(n=_SEQ, window=st.integers(min_value=1, max_value=1024))
def test_sliding_window_covering_all_equals_full_causal(n: int, window: int) -> None:
    assume(window >= n)
    assert sliding_causal_pairs(n, window) == full_causal_pairs(n)


@given(n=_SEQ)
def test_sliding_window_of_one_is_diagonal(n: int) -> None:
    assert sliding_causal_pairs(n, 1) == n


@given(n=st.integers(min_value=2, max_value=256), w=st.integers(min_value=1, max_value=128))
def test_sliding_window_monotonic_nondecreasing_in_window(n: int, w: int) -> None:
    assert sliding_causal_pairs(n, w) <= sliding_causal_pairs(n, w + 1)


@given(batch=_POS_DIM, d_model=_DIM, pairs=_DIM)
def test_attention_core_flops_monotonic_in_pairs(batch: int, d_model: int, pairs: int) -> None:
    lo = attention_core_flops(batch=batch, d_model=d_model, valid_attention_pairs=pairs)
    hi = attention_core_flops(batch=batch, d_model=d_model, valid_attention_pairs=pairs + 1)
    assert hi >= lo


@given(tokens=_DIM, d_model=_DIM, d_ff=_DIM)
def test_mlp_flops_symmetric_formula(tokens: int, d_model: int, d_ff: int) -> None:
    # up-proj + down-proj, each 2*tokens*d_model*d_ff
    assert mlp_flops(tokens=tokens, d_model=d_model, d_ff=d_ff) == 4 * tokens * d_model * d_ff


@given(
    entries=st.lists(
        st.tuples(st.text(min_size=1, max_size=8), st.integers(min_value=0, max_value=10**9)),
        min_size=0,
        max_size=20,
    )
)
def test_flop_ledger_total_equals_sum_of_entries(entries: list[tuple[str, int]]) -> None:
    ledger = FlopLedger()
    for name, flops in entries:
        ledger.add(name, "test", flops)
    assert ledger.total_logical_flops == sum(f for _, f in entries)


@given(flops=st.integers(max_value=-1))
def test_flop_ledger_rejects_negative(flops: int) -> None:
    ledger = FlopLedger()
    try:
        ledger.add("x", "y", flops)
        raise AssertionError("expected ValueError for negative flops")
    except ValueError:
        pass


# --------------------------------------------------------------------------- #
# Percentile
# --------------------------------------------------------------------------- #
@given(values=st.lists(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False), min_size=1, max_size=50))
def test_percentile_within_min_max(values: list[float]) -> None:
    for q in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = _percentile(values, q)
        assert min(values) - 1e-9 <= result <= max(values) + 1e-9


@given(values=st.lists(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False), min_size=1, max_size=50))
def test_percentile_endpoints_are_min_and_max(values: list[float]) -> None:
    assert _percentile(values, 0.0) == min(values)
    assert _percentile(values, 1.0) == max(values)


@given(values=st.lists(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False), min_size=2, max_size=50))
def test_percentile_monotonic_in_q(values: list[float]) -> None:
    assert _percentile(values, 0.25) <= _percentile(values, 0.75) + 1e-9


@given(constant=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False), n=st.integers(min_value=1, max_value=30))
def test_percentile_of_constant_list_is_constant(constant: float, n: int) -> None:
    values = [constant] * n
    for q in (0.0, 0.5, 0.95, 1.0):
        assert _percentile(values, q) == constant


# --------------------------------------------------------------------------- #
# Bootstrap CI
# --------------------------------------------------------------------------- #
@given(deltas=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), min_size=2, max_size=40))
@settings(max_examples=50)
def test_bootstrap_ci_lower_le_upper(deltas: list[float]) -> None:
    lower, upper = _bootstrap_ci(deltas, resamples=200, seed=7)
    assert lower <= upper


@given(deltas=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), min_size=2, max_size=40))
@settings(max_examples=50)
def test_bootstrap_ci_within_data_range(deltas: list[float]) -> None:
    lower, upper = _bootstrap_ci(deltas, resamples=200, seed=7)
    assert min(deltas) - 1e-9 <= lower
    assert upper <= max(deltas) + 1e-9


@given(constant=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), n=st.integers(min_value=2, max_value=30))
@settings(max_examples=30)
def test_bootstrap_ci_of_constant_is_that_constant(constant: float, n: int) -> None:
    lower, upper = _bootstrap_ci([constant] * n, resamples=200, seed=3)
    assert lower == constant
    assert upper == constant


# --------------------------------------------------------------------------- #
# Trapezoidal energy integration
# --------------------------------------------------------------------------- #
@given(
    power=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
    duration=st.floats(min_value=0.01, max_value=100.0, allow_nan=False),
)
def test_constant_power_integrates_to_power_times_time(power: float, duration: float) -> None:
    # two samples at t=0 and t=duration, both at `power` watts
    joules = _trapezoidal_joules([(0.0, power), (duration, power)])
    assert joules == power * duration


_TS = st.floats(min_value=0.0, max_value=1e4, allow_nan=False)
_WATTS = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False)


@given(
    samples=st.lists(
        st.tuples(_TS, _WATTS),
        min_size=2,
        max_size=30,
    )
)
def test_trapezoidal_nonnegative_for_nonnegative_watts_and_sorted_time(samples: list[tuple[float, float]]) -> None:
    # sort by timestamp so intervals are non-negative (the sampler guarantees this)
    ordered = sorted(samples, key=lambda s: s[0])
    assert _trapezoidal_joules(ordered) >= 0.0


@given(power=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False))
def test_trapezoidal_needs_two_samples(power: float) -> None:
    assert _trapezoidal_joules([]) == 0.0
    assert _trapezoidal_joules([(0.0, power)]) == 0.0


# --------------------------------------------------------------------------- #
# Routing aggregation
# --------------------------------------------------------------------------- #
@given(
    tokens_seq=st.lists(st.integers(min_value=0, max_value=10**6), min_size=1, max_size=40),
)
def test_routing_sum_min_max_invariants(tokens_seq: list[int]) -> None:
    counters = RoutingCounters(mode=InstrumentationMode.COUNTERS)
    for step, tokens in enumerate(tokens_seq):
        counters.record(step=step, active_tokens=tokens, active_blocks=1, active_experts=1, active_parameters=1)
    snap = counters.snapshot()
    assert snap.step_count == len(tokens_seq)
    assert snap.active_tokens_sum == sum(tokens_seq)
    assert snap.active_tokens_min == min(tokens_seq)
    assert snap.active_tokens_max == max(tokens_seq)
    assert snap.active_tokens_min <= snap.active_tokens_max


@given(
    values=st.lists(st.integers(min_value=0, max_value=1000), min_size=0, max_size=60),
    num_bins=st.integers(min_value=1, max_value=50),
    max_value=st.integers(min_value=1, max_value=1000),
)
def test_histogram_total_count_and_bounded_bins(values: list[int], num_bins: int, max_value: int) -> None:
    hist = RoutingHistogram(num_bins=num_bins, max_value=max_value)
    for v in values:
        hist.add(v)
    counts = hist.counts
    assert len(counts) == num_bins  # never grows unbounded
    assert sum(counts) == len(values)  # every add lands in exactly one bin
    assert all(c >= 0 for c in counts)


# --------------------------------------------------------------------------- #
# Event pool conservation
# --------------------------------------------------------------------------- #
@given(size=st.integers(min_value=1, max_value=32), acquires=st.integers(min_value=0, max_value=64))
def test_event_pool_dropped_count_matches_overflow(size: int, acquires: int) -> None:
    # CPU-only structural test: warm_up allocates torch events, which needs
    # CUDA — so exercise only the counting logic by pre-seeding a fake pool.
    pool = EventPool(size=size)
    # Simulate the availability list without real CUDA events.
    pool._available = [("start", "end")] * size  # type: ignore[list-item]
    pool._warmed_up = True
    acquired = 0
    for _ in range(acquires):
        got = pool.acquire()
        if got is not None:
            acquired += 1
    assert acquired == min(acquires, size)
    assert pool.dropped_event_pairs == max(0, acquires - size)
