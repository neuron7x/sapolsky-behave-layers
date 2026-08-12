"""python -m pytest tests/test_instrumentation_audit.py -v

Act 8.4: profiler trace export; analytic vs profiler supported-op comparison;
explicit list of unsupported operators; no claim from profiler-only FLOPs;
audit run has claimable=false.
"""

from pathlib import Path

import pytest

from cwc.instrumentation.audit import flop_model_comparison, moe_cap_placeholder, roofline_report

torch = pytest.importorskip("torch")


def test_audit_run_is_never_claimable(tmp_path: Path):
    from cwc.instrumentation.audit import run_torch_profiler

    def workload():
        x = torch.randn(64, 64)
        return x @ x

    result = run_torch_profiler(workload, steps=3, warmup_steps=1, trace_export_path=tmp_path / "trace.json")
    assert result["claim_run"] is False


def test_audit_exports_chrome_trace(tmp_path: Path):
    from cwc.instrumentation.audit import run_torch_profiler

    trace_path = tmp_path / "trace.json"

    def workload():
        x = torch.randn(64, 64)
        return x @ x

    run_torch_profiler(workload, steps=3, warmup_steps=1, trace_export_path=trace_path)
    assert trace_path.exists()
    assert trace_path.stat().st_size > 0


@pytest.mark.cuda
def test_flop_comparison_covers_matmul_and_lists_uncovered_ops():
    from cwc.instrumentation.audit import run_torch_profiler

    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this host")

    def workload():
        x = torch.randn(256, 256, device="cuda")
        y = x @ x
        return y.relu().sum()  # relu+sum are not in _COVERED_OPERATOR_PREFIXES

    audit_result = run_torch_profiler(workload, steps=5, warmup_steps=2, with_flops=True)
    analytical_flops = 2 * 256 * 256 * 256  # matches dense_linear_flops(tokens=256, d_in=256, d_out=256)
    comparison = flop_model_comparison(analytical_flops=analytical_flops, audit_result=audit_result)
    assert comparison["comparable"] is True
    assert comparison["profiler_covered_flops"] > 0
    assert "flop_model_error_percent" in comparison


def test_flop_comparison_reports_not_comparable_without_flops_flag():
    audit_result = {"covered_flops": None, "uncovered_operator_names": []}
    comparison = flop_model_comparison(analytical_flops=1000, audit_result=audit_result)
    assert comparison["comparable"] is False


def test_roofline_report_classifies_memory_bound():
    # low operational intensity (few flops per byte moved) -> memory bound
    report = roofline_report(
        total_flops=1_000,
        total_bytes_moved=1_000_000,
        peak_flops_per_s=1e12,
        peak_bandwidth_bytes_per_s=1e9,
        hardware_ceiling_provenance="test-fixture",
    )
    assert report["bound"] == "memory_bound"


def test_roofline_report_classifies_compute_bound():
    report = roofline_report(
        total_flops=1_000_000_000,
        total_bytes_moved=1_000,
        peak_flops_per_s=1e12,
        peak_bandwidth_bytes_per_s=1e9,
        hardware_ceiling_provenance="test-fixture",
    )
    assert report["bound"] == "compute_bound"


def test_roofline_report_rejects_nonpositive_hardware_rates():
    with pytest.raises(ValueError):
        roofline_report(
            total_flops=1,
            total_bytes_moved=1,
            peak_flops_per_s=0.0,
            peak_bandwidth_bytes_per_s=1e9,
            hardware_ceiling_provenance="x",
        )


def test_moe_cap_placeholder_is_unimplemented():
    placeholder = moe_cap_placeholder()
    assert placeholder["implemented"] is False
    assert placeholder["s_mfu"] is None
    assert placeholder["active_experts"] is None
