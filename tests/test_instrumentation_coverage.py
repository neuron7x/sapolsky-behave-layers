"""python -m pytest tests/test_instrumentation_coverage.py -v

Targeted branch/line coverage for guard clauses, error paths, writer helpers,
type helpers, and import-guarded fallbacks across the cwc/instrumentation
package that the behavioral test files do not otherwise reach. Together with
the property and NVML-mocked suites this drives the package to ~100%.
"""

import json
from pathlib import Path

import pytest

from cwc.instrumentation.audit import flop_model_comparison, run_torch_profiler
from cwc.instrumentation.clock import cpu_elapsed_ms, cpu_start_ns, open_window, resolve_windows
from cwc.instrumentation.config import InstrumentationMode, _cuda_available
from cwc.instrumentation.energy import ExternalWallMeterAdapter, _trapezoidal_joules
from cwc.instrumentation.event_buffer import EventPool
from cwc.instrumentation.flops import FlopLedger
from cwc.instrumentation.manifest import device_manifest, environment_manifest, git_provenance
from cwc.instrumentation.run_meter import RunMeter
from cwc.instrumentation.types import InstrumentationSummary, VRAMRecord
from cwc.instrumentation.writer import InstrumentationWriter


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def test_cuda_available_real_call_returns_bool():
    # Calls the real function (not the monkeypatched lambda used elsewhere),
    # covering the torch-import + is_available path.
    assert isinstance(_cuda_available(), bool)


# --------------------------------------------------------------------------- #
# clock
# --------------------------------------------------------------------------- #
def test_open_window_returns_none_when_pool_exhausted():
    pool = EventPool(size=1)
    pool._available = []  # simulate exhausted, warmed pool without CUDA
    pool._warmed_up = True
    assert open_window(pool, device_index=0) is None


def test_resolve_windows_empty_returns_empty():
    pool = EventPool(size=1)
    assert resolve_windows([], pool) == []


def test_cpu_clock_monotonic_nonnegative():
    start = cpu_start_ns()
    elapsed = cpu_elapsed_ms(start)
    assert elapsed >= 0.0


# --------------------------------------------------------------------------- #
# event_buffer
# --------------------------------------------------------------------------- #
def test_event_pool_rejects_nonpositive_size():
    with pytest.raises(ValueError, match="size must be > 0"):
        EventPool(size=0)


def test_event_pool_warm_up_is_idempotent_when_already_warmed():
    pool = EventPool(size=2)
    pool._warmed_up = True  # pretend already warmed (no CUDA needed)
    pool.warm_up()  # must return immediately without touching torch
    assert pool.available_count == 0


# --------------------------------------------------------------------------- #
# flops
# --------------------------------------------------------------------------- #
def test_flop_ledger_rejects_negative_executed_estimate():
    ledger = FlopLedger()
    with pytest.raises(ValueError, match="executed_estimate_flops cannot be negative"):
        ledger.add("x", "y", 100, executed_estimate_flops=-1)


def test_flop_ledger_noncausal_attention_branch():
    ledger = FlopLedger()
    rec = ledger.add_attention(
        "a", batch=1, seq_len=8, d_model=16, n_head=2, n_kv_head=2, head_dim=8, causal=False
    )
    # non-causal uses full T*T pairs, strictly more than causal
    causal = ledger.add_attention(
        "b", batch=1, seq_len=8, d_model=16, n_head=2, n_kv_head=2, head_dim=8, causal=True
    )
    assert rec.logical_flops > causal.logical_flops


def test_sliding_window_zero_raises_via_ledger():
    ledger = FlopLedger()
    with pytest.raises(ValueError, match="window must be positive"):
        ledger.add_attention(
            "w", batch=1, seq_len=8, d_model=16, n_head=2, n_kv_head=2, head_dim=8, window=0
        )


# --------------------------------------------------------------------------- #
# run_meter
# --------------------------------------------------------------------------- #
def test_run_meter_cpu_path_no_cuda_events():
    meter = RunMeter(enable_cuda_events=False)
    with meter.scope("s", step=0, tokens=10):
        pass
    records = meter.resolve()
    assert len(records) == 1
    assert records[0].gpu_kernel_ms == 0.0
    assert records[0].status == "ok"


def test_run_meter_resolve_with_nothing_pending_returns_empty():
    meter = RunMeter(enable_cuda_events=False)
    assert meter.resolve() == []


def test_run_meter_measure_step_returns_value():
    meter = RunMeter(enable_cuda_events=False)
    assert meter.measure_step(lambda: 42, step=0, tokens=8) == 42
    assert len(meter.resolve()) == 1


def test_run_meter_cuda_available_false_when_torch_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("no torch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert RunMeter(enable_cuda_events=False).cuda_available is False


def test_run_meter_skips_mark_start_when_pool_exhausted():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("needs CUDA for the event-pool path")
    from cwc.instrumentation.event_buffer import EventPool

    pool = EventPool(size=1)
    pool.warm_up()
    pool.acquire()  # exhaust the pool so scope()'s open_window returns None
    meter = RunMeter(event_pool=pool, enable_cuda_events=True)
    with meter.scope("s", step=0):  # open_window -> None -> mark_start skipped
        pass
    records = meter.resolve()
    assert len(records) == 1
    assert records[0].gpu_kernel_ms == 0.0  # no CUDA window was available


def test_run_meter_error_scope_records_and_reraises():
    meter = RunMeter(enable_cuda_events=False)
    with pytest.raises(ValueError, match="boom"), meter.scope("s", step=1):
        raise ValueError("boom")
    recs = meter.flush()
    assert recs and recs[-1].status == "error" and recs[-1].error_type == "ValueError"


# --------------------------------------------------------------------------- #
# types
# --------------------------------------------------------------------------- #
def test_vram_record_delta():
    rec = VRAMRecord(
        scope_name="s", device="cuda",
        start_allocated_bytes=100, start_reserved_bytes=200,
        peak_allocated_bytes=500, peak_reserved_bytes=600,
        end_allocated_bytes=300, end_reserved_bytes=400,
    )
    assert rec.delta_allocated_bytes == 200


def test_instrumentation_summary_to_dict_roundtrips_keys():
    summary = InstrumentationSummary(
        schema_version="1.0.0", run={}, environment={}, model={}, workload={},
        instrumentation={}, latency={}, throughput={}, vram={}, flops={},
        energy={}, routing={}, validity={},
    )
    d = summary.to_dict()
    assert set(d) == {
        "schema_version", "run", "environment", "model", "workload",
        "instrumentation", "latency", "throughput", "vram", "flops",
        "energy", "routing", "validity",
    }


# --------------------------------------------------------------------------- #
# energy misc
# --------------------------------------------------------------------------- #
def test_external_wall_meter_adapter_is_not_auto_wired():
    with pytest.raises(NotImplementedError, match="never an automatic fallback"):
        ExternalWallMeterAdapter().read_joules(0.0, 1.0)


def test_trapezoidal_single_sample_zero():
    assert _trapezoidal_joules([(0.0, 10.0)]) == 0.0


# --------------------------------------------------------------------------- #
# writer helpers
# --------------------------------------------------------------------------- #
def test_writer_overhead_report_and_energy_raw(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.write_overhead_report({"gate_passed": True})
    writer.write_manifest({"run_id": "x"})
    writer.write_resolved_config({"mode": "counters"})
    writer.write_energy_raw([{"t": 0.0, "w": 50.0}, {"t": 0.1, "w": 51.0}])
    writer.close()
    assert json.loads((tmp_path / "overhead_report.json").read_text())["gate_passed"] is True
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "config.resolved.json").exists()
    lines = (tmp_path / "energy.raw.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_writer_close_is_idempotent(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.write_metric({"a": 1})
    writer.close()
    writer.close()  # second close must be a no-op, not re-flush
    assert len((tmp_path / "metrics.jsonl").read_text().splitlines()) == 1


def test_writer_checksums_empty_dir_has_trailing_behavior(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.close()
    sums = writer.compute_checksums()
    # no files written besides (eventually) SHA256SUMS itself, which is excluded
    assert sums.read_text() == ""


# --------------------------------------------------------------------------- #
# manifest fallbacks
# --------------------------------------------------------------------------- #
def test_git_provenance_on_non_repo_returns_none(tmp_path: Path):
    prov = git_provenance(tmp_path)  # tmp_path is not a git repo
    assert prov["git_commit"] is None
    assert prov["git_dirty"] is False


def test_device_manifest_without_torch(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("no torch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    manifest = device_manifest()
    assert manifest["cuda_available"] is False
    assert manifest["total_vram_bytes"] == 0


def test_environment_manifest_without_torch(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("no torch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    manifest = environment_manifest(expected_torch_version="2.9.1")
    assert manifest["torch_version"] == "unavailable"
    assert manifest["environment_match"] is False


# --------------------------------------------------------------------------- #
# audit branches
# --------------------------------------------------------------------------- #
def test_audit_without_flops_flag_reports_none_profiler_flops(tmp_path: Path):
    pytest.importorskip("torch")
    import torch

    def workload():
        x = torch.randn(16, 16)
        return (x @ x).sum()

    result = run_torch_profiler(workload, steps=2, warmup_steps=1, with_flops=False)
    assert result["profiler_observed_flops"] is None
    comparison = flop_model_comparison(analytical_flops=1000, audit_result=result)
    assert comparison["comparable"] is False


def test_audit_mode_enum_values_are_stable():
    assert InstrumentationMode.OFF.value == "off"
    assert InstrumentationMode.COUNTERS.value == "counters"
    assert InstrumentationMode.TRACE.value == "trace"
    assert InstrumentationMode.AUDIT.value == "audit"


# --------------------------------------------------------------------------- #
# additional guard/error branches
# --------------------------------------------------------------------------- #
def test_cuda_available_false_when_torch_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("no torch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert _cuda_available() is False


def test_routing_histogram_rejects_nonpositive_bins():
    from cwc.instrumentation.routing import RoutingHistogram

    with pytest.raises(ValueError, match="num_bins must be > 0"):
        RoutingHistogram(num_bins=0)


def test_routing_histogram_zero_max_value_bins_at_zero():
    from cwc.instrumentation.routing import RoutingHistogram

    hist = RoutingHistogram(num_bins=4, max_value=0)
    hist.add(999)  # max_value<=0 branch -> bin 0
    assert hist.counts[0] == 1


def test_flops_rejects_negative_shared_expert_count():
    ledger = FlopLedger()
    with pytest.raises(ValueError, match="token counts cannot be negative"):
        ledger.record_expert_assignments(
            expert_token_counts={0: 1}, top_k=1,
            shared_expert_token_count=-1, dropped_token_count=0, padded_token_count=0,
        )


def test_event_pool_size_property():
    pool = EventPool(size=7)
    assert pool.size == 7


def test_writer_metric_flush_below_buffer_stays_buffered(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path, buffer_size=5)
    writer.write_metric({"a": 1})  # below buffer -> not yet written
    assert not (tmp_path / "metrics.jsonl").exists() or (tmp_path / "metrics.jsonl").read_text() == ""
    writer.flush()
    assert len((tmp_path / "metrics.jsonl").read_text().splitlines()) == 1


def test_writer_checksums_excludes_sha_file_itself(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.write_metric({"a": 1})
    writer.close()
    writer.compute_checksums()
    content = (tmp_path / "SHA256SUMS").read_text()
    assert "metrics.jsonl" in content
    assert "SHA256SUMS" not in content


def test_device_manifest_cuda_false_branch(monkeypatch):
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    manifest = device_manifest()
    assert manifest["cuda_available"] is False
    assert manifest["device_name"] is None


def test_device_manifest_driver_probe_failure(monkeypatch):
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("needs CUDA for the driver-probe branch")
    import cwc.instrumentation.manifest as manifest_mod

    def raising_run(*args, **kwargs):
        raise OSError("nvidia-smi not found")

    monkeypatch.setattr(manifest_mod.subprocess, "run", raising_run)
    manifest = device_manifest()
    assert manifest["driver_version"] is None
    assert manifest["cuda_available"] is True


def test_power_sampler_nvml_init_exception_is_unavailable(monkeypatch):
    import cwc.instrumentation.energy as energy_mod
    from cwc.instrumentation.energy import NVMLPowerSampler

    class _BrokenNVML:
        def nvmlInit(self):
            raise RuntimeError("NVML driver mismatch")

    monkeypatch.setattr(energy_mod, "pynvml", _BrokenNVML())
    monkeypatch.setattr(energy_mod, "_PYNVML_AVAILABLE", True)
    sampler = NVMLPowerSampler()
    assert sampler.available is False


def test_power_sampler_median_interval_with_few_samples():
    from cwc.instrumentation.energy import NVMLPowerSampler

    sampler = NVMLPowerSampler()
    sampler._samples = [(0.0, 50.0)]  # < 2 samples
    assert sampler.median_sampling_interval_sec == 0.0


def test_power_sampler_rejects_nonpositive_rate():
    from cwc.instrumentation.energy import NVMLPowerSampler

    with pytest.raises(ValueError, match="sample_rate_hz must be > 0"):
        NVMLPowerSampler(sample_rate_hz=0.0)


def test_routing_rejects_negative_dropped_tokens():
    from cwc.instrumentation.routing import RoutingCounters

    counters = RoutingCounters()
    with pytest.raises(ValueError, match="dropped/padded token counts cannot be negative"):
        counters.record(
            step=0, active_tokens=1, active_blocks=1, active_experts=1,
            active_parameters=1, dropped_tokens=-1,
        )


def test_roofline_zero_flops_is_unclassified_zero_bandwidth():
    from cwc.instrumentation.audit import roofline_report

    report = roofline_report(
        total_flops=0, total_bytes_moved=1000,
        peak_flops_per_s=1e12, peak_bandwidth_bytes_per_s=1e9,
        hardware_ceiling_provenance="test",
    )
    assert report["bound"] == "unclassified"
    assert report["achieved_bandwidth_bytes_per_s"] == 0.0


def test_writer_checksums_skips_subdirectories(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.write_metric({"a": 1})
    writer.close()
    (tmp_path / "audit").mkdir()  # a subdirectory must be skipped, not hashed
    (tmp_path / "audit" / "trace.json").write_text("{}")
    writer.compute_checksums()
    content = (tmp_path / "SHA256SUMS").read_text()
    # rglob descends into the subdir for files but never emits the dir entry itself
    assert "audit/trace.json" in content
    assert not any(line.endswith("  audit") for line in content.splitlines())
