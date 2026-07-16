"""AUDIT-mode-only adapters (Act 4.13, 6.3, 6.4): torch.profiler, roofline
analysis, and MoE-CAP schema field reservations. Never invoked from the
COUNTERS hot path — these are for periodic, offline, separate-run diagnosis,
and their output always carries `claimable: false` / a `claim_run: false` tag
so a summary cannot accidentally mix profiler-run latency with production
latency (Act 4.13: "не змішувати profiler latency з production latency").
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

# Operators this module can compare analytically vs profiler-observed. Any
# operator the profiler reports that is NOT in this set is left out of the
# comparison entirely — it is never silently treated as zero cost (Act 4.13).
_COVERED_OPERATOR_PREFIXES = ("aten::linear", "aten::matmul", "aten::mm", "aten::bmm", "aten::addmm")


def run_torch_profiler(
    fn: Callable[[], Any],
    *,
    steps: int,
    warmup_steps: int = 3,
    record_shapes: bool = True,
    profile_memory: bool = True,
    with_flops: bool = False,
    trace_export_path: Path | None = None,
) -> dict[str, Any]:
    """AUDIT-only: a short, fixed-window torch.profiler run over `fn`, called
    `steps` times after `warmup_steps` untimed warmup calls. Returns a summary
    dict, never a bare profiler object (so callers cannot accidentally treat
    it as a COUNTERS-mode latency record).
    """
    import torch
    from torch.profiler import ProfilerActivity, profile

    for _ in range(warmup_steps):
        fn()

    activities = [ProfilerActivity.CPU]
    if torch.cuda.is_available():
        activities.append(ProfilerActivity.CUDA)

    with profile(
        activities=activities,
        record_shapes=record_shapes,
        profile_memory=profile_memory,
        with_flops=with_flops,
    ) as prof:
        for _ in range(steps):
            fn()
            if torch.cuda.is_available():
                torch.cuda.synchronize()

    if trace_export_path is not None:
        trace_export_path.parent.mkdir(parents=True, exist_ok=True)
        prof.export_chrome_trace(str(trace_export_path))

    key_averages = prof.key_averages()
    total_cuda_time_us = sum(getattr(event, "cuda_time_total", 0) or 0 for event in key_averages)
    total_cpu_time_us = sum(getattr(event, "cpu_time_total", 0) or 0 for event in key_averages)

    covered_flops = 0
    uncovered_operator_names: list[str] = []
    profiler_observed_flops: int | None = None
    if with_flops:
        profiler_observed_flops = 0
        for event in key_averages:
            event_flops = getattr(event, "flops", 0) or 0
            profiler_observed_flops += event_flops
            if any(event.key.startswith(prefix) for prefix in _COVERED_OPERATOR_PREFIXES):
                covered_flops += event_flops
            elif event_flops > 0:
                uncovered_operator_names.append(event.key)

    return {
        "steps": steps,
        "warmup_steps": warmup_steps,
        "total_cuda_time_us": total_cuda_time_us,
        "total_cpu_time_us": total_cpu_time_us,
        "profiler_observed_flops": profiler_observed_flops,
        "covered_flops": covered_flops if with_flops else None,
        "uncovered_operator_names": sorted(set(uncovered_operator_names)),
        "trace_export_path": str(trace_export_path) if trace_export_path else None,
        "claim_run": False,  # an AUDIT profiler run never contributes to a claim
    }


def flop_model_comparison(*, analytical_flops: int, audit_result: dict[str, Any]) -> dict[str, Any]:
    """Compares analytical (this package's FlopLedger) vs profiler-observed
    FLOPs, restricted to operators this module actually covers. Uncovered
    operators are reported separately, never folded into a 0-cost assumption.
    """
    profiler_flops = audit_result.get("covered_flops")
    if profiler_flops is None or profiler_flops == 0:
        return {
            "comparable": False,
            "reason": "profiler run did not use with_flops=True or reported no covered-operator FLOPs",
            "uncovered_operator_names": audit_result.get("uncovered_operator_names", []),
        }
    error_percent = 100.0 * (profiler_flops - analytical_flops) / analytical_flops if analytical_flops else None
    return {
        "comparable": True,
        "analytical_flops": analytical_flops,
        "profiler_covered_flops": profiler_flops,
        "flop_model_error_percent": error_percent,
        "uncovered_operator_names": audit_result.get("uncovered_operator_names", []),
    }


def roofline_report(
    *,
    total_flops: int,
    total_bytes_moved: int,
    peak_flops_per_s: float,
    peak_bandwidth_bytes_per_s: float,
    hardware_ceiling_provenance: str,
) -> dict[str, Any]:
    if peak_flops_per_s <= 0.0 or peak_bandwidth_bytes_per_s <= 0.0:
        raise ValueError("peak hardware rates must be positive")
    operational_intensity = total_flops / total_bytes_moved if total_bytes_moved > 0 else 0.0
    ridge_point = peak_flops_per_s / peak_bandwidth_bytes_per_s
    attainable_flops_per_s = min(peak_flops_per_s, operational_intensity * peak_bandwidth_bytes_per_s)
    if operational_intensity == 0.0:
        bound = "unclassified"
    elif operational_intensity < ridge_point:
        bound = "memory_bound"
    else:
        bound = "compute_bound"
    return {
        "operational_intensity_flops_per_byte": operational_intensity,
        "ridge_point_flops_per_byte": ridge_point,
        "attainable_flops_per_s": attainable_flops_per_s,
        "achieved_bandwidth_bytes_per_s": (
            total_bytes_moved / (total_flops / attainable_flops_per_s) if attainable_flops_per_s > 0 else 0.0
        ),
        "bound": bound,
        "hardware_ceiling_provenance": hardware_ceiling_provenance,
    }


def moe_cap_placeholder() -> dict[str, Any]:
    """WP-1 reserves these MoE-CAP schema fields; none are computed until
    WP-3 implements routing (Act 6.4).
    """
    return {
        "implemented": False,
        "s_mfu": None,
        "s_mbu": None,
        "active_experts": None,
        "expert_capacity": None,
        "load_imbalance": None,
        "communication_bytes": None,
    }
