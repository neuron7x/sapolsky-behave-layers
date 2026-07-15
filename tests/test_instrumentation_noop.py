"""python -m pytest tests/test_instrumentation_noop.py -v

Verifies OFF-mode no-op objects never touch torch.cuda, files, or threads.
"""

from cwc.instrumentation.noop import (
    NullEnergySampler,
    NullFlopLedger,
    NullRoutingCounters,
    NullRunMeter,
    NullVRAMMeter,
    NullWriter,
)


def test_null_run_meter_scope_runs_wrapped_code_only():
    meter = NullRunMeter()
    calls = []
    with meter.scope("train_step", step=0, tokens=128):
        calls.append("inside")
    assert calls == ["inside"]


def test_null_run_meter_measure_step_returns_result():
    meter = NullRunMeter()
    result = meter.measure_step(lambda: 42, step=0)
    assert result == 42


def test_null_run_meter_lifecycle_is_idempotent_and_side_effect_free():
    meter = NullRunMeter()
    meter.resolve()
    meter.flush()
    meter.close()
    meter.close()  # idempotent


def test_null_vram_meter_returns_none_snapshot():
    meter = NullVRAMMeter()
    meter.reset_peak()
    assert meter.snapshot() is None


def test_null_energy_sampler_reports_unavailable():
    sampler = NullEnergySampler()
    sampler.start()
    record = sampler.stop()
    assert record.available is False
    assert record.confidence == "unavailable"
    assert record.joules == 0.0


def test_null_flop_ledger_reports_zero():
    ledger = NullFlopLedger()
    assert ledger.add("x", "y", 100) is None
    assert ledger.total_logical_flops == 0
    assert ledger.total_executed_estimate_flops == 0
    assert ledger.to_dict() == {"enabled": False}


def test_null_routing_counters_snapshot_is_empty():
    counters = NullRoutingCounters()
    counters.record(active_tokens=10, active_blocks=1, active_experts=2, active_parameters=1000)
    snapshot = counters.snapshot()
    assert snapshot.step_count == 0
    assert snapshot.active_tokens_sum == 0


def test_null_writer_never_creates_output():
    writer = NullWriter()
    writer.write_metric({"a": 1})
    writer.write_summary({"b": 2})
    writer.close()
    assert writer.output_dir is None
