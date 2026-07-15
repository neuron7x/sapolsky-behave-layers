"""python -m pytest tests/test_instrumentation_routing.py -v

WP-1 implements no router (Act scope, section 0). These tests exercise the
measurement-ready RoutingCounters API with synthetic values only, proving the
aggregation/trace/histogram logic before any real routing decision exists.
"""

import pytest

from cwc.instrumentation.config import InstrumentationMode
from cwc.instrumentation.routing import RoutingCounters


def test_counters_mode_aggregates_only_no_per_step_records():
    counters = RoutingCounters(mode=InstrumentationMode.COUNTERS)
    for step in range(5):
        counters.record(step=step, active_tokens=10 + step, active_blocks=1, active_experts=2, active_parameters=1000)
    snapshot = counters.snapshot()
    assert snapshot.step_count == 5
    assert snapshot.active_tokens_sum == sum(10 + s for s in range(5))
    assert snapshot.active_tokens_min == 10
    assert snapshot.active_tokens_max == 14
    assert counters.flush_trace() == []  # COUNTERS mode never buffers per-step trace


def test_trace_mode_samples_every_n_steps():
    counters = RoutingCounters(mode=InstrumentationMode.TRACE, trace_every_n_steps=2, trace_buffer_records=100)
    for step in range(6):
        counters.record(step=step, active_tokens=step, active_blocks=1, active_experts=1, active_parameters=1)
    trace = counters.flush_trace()
    assert [record["step"] for record in trace] == [0, 2, 4]


def test_trace_buffer_is_bounded_and_counts_dropped():
    counters = RoutingCounters(mode=InstrumentationMode.TRACE, trace_every_n_steps=1, trace_buffer_records=2)
    for step in range(5):
        counters.record(step=step, active_tokens=step, active_blocks=1, active_experts=1, active_parameters=1)
    trace = counters.flush_trace()
    assert len(trace) == 2  # bounded, not 5
    assert counters.dropped_trace_count > 0


def test_entropy_mean_none_when_never_supplied():
    counters = RoutingCounters()
    counters.record(step=0, active_tokens=1, active_blocks=1, active_experts=1, active_parameters=1)
    assert counters.snapshot().entropy_mean is None


def test_entropy_mean_computed_when_supplied():
    counters = RoutingCounters()
    counters.record(step=0, active_tokens=1, active_blocks=1, active_experts=1, active_parameters=1, entropy=0.5)
    counters.record(step=1, active_tokens=1, active_blocks=1, active_experts=1, active_parameters=1, entropy=1.5)
    assert counters.snapshot().entropy_mean == pytest.approx(1.0)


def test_negative_counts_rejected():
    counters = RoutingCounters()
    with pytest.raises(ValueError):
        counters.record(step=0, active_tokens=-1, active_blocks=1, active_experts=1, active_parameters=1)


def test_histogram_has_bounded_bins():
    counters = RoutingCounters(histogram_max_value=100)
    for i, value in enumerate((0, 10, 50, 99, 100, 1000)):
        counters.record(step=i, active_tokens=value, active_blocks=1, active_experts=1, active_parameters=1)
    assert len(counters.histogram_counts) == 20  # default num_bins, never grows unbounded
