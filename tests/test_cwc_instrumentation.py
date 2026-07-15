"""
Test the CWC WP-1 instrumentation module: EnergySampler degrades cleanly
without NVML/GPU, ActivatedComputeCounter reports honest fractions pre- and
post-routing, RoutingTelemetry is a plain placeholder schema.

python -m pytest tests/test_cwc_instrumentation.py -v
"""

import time

import pytest

from nanochat.cwc_instrumentation import ActivatedComputeCounter, EnergySampler, RoutingTelemetry


def test_energy_sampler_degrades_without_nvml():
    sampler = EnergySampler(poll_interval_s=0.01)
    # available may be True or False depending on the host; either way start/stop
    # must not raise, and joules must be a finite, non-negative number.
    sampler.start()
    time.sleep(0.03)
    sampler.stop()
    joules = sampler.joules_since_start()
    assert joules >= 0.0
    assert joules == joules  # not NaN


def test_energy_sampler_reset():
    sampler = EnergySampler(poll_interval_s=0.01)
    sampler.start()
    time.sleep(0.03)
    sampler.stop()
    sampler.reset()
    assert sampler.joules_since_start() == 0.0


def test_activated_counter_dense_only_is_honest_fraction_one():
    counter = ActivatedComputeCounter()
    counter.record_dense_step(1000.0)
    counter.record_dense_step(1000.0)
    assert counter.activated_fraction == pytest.approx(1.0)
    assert counter.total_dense_flops == pytest.approx(2000.0)
    assert counter.steps_recorded == 2


def test_activated_counter_with_no_steps_reports_one_not_nan():
    counter = ActivatedComputeCounter()
    assert counter.activated_fraction == 1.0


def test_activated_counter_routed_step_reports_sparsity():
    counter = ActivatedComputeCounter()
    counter.record_routed_step(activated_flops_this_step=250.0, dense_equivalent_flops_this_step=1000.0)
    assert counter.activated_fraction == pytest.approx(0.25)


def test_activated_counter_rejects_impossible_overcounting():
    counter = ActivatedComputeCounter()
    with pytest.raises(ValueError, match="cannot exceed"):
        counter.record_routed_step(activated_flops_this_step=1200.0, dense_equivalent_flops_this_step=1000.0)


def test_routing_telemetry_is_an_inert_placeholder_until_wp3():
    telemetry = RoutingTelemetry()
    assert telemetry.route_entropy_mean is None
    assert telemetry.expert_utilization == []
    assert telemetry.overflow_count == 0
    assert telemetry.fallback_used is False
