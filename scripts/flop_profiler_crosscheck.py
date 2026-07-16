"""Act B2 — profiler FLOP cross-check (standalone metrology).

Independently validates the analytic FLOP formulas in
``experiments.wp2_routing_v2.src.compute`` against ``torch.profiler`` observed
FLOPs, on a *real* batch, for the two typed forward paths (DirectPath,
SemanticParser) plus SemanticRenderer as a matmul-only positive control.

Two honesty guarantees, both discharged empirically at runtime rather than
assumed:

1. **MAC-vs-FLOP convention.** The logical formulas count 2*MAC (one multiply +
   one add). ``torch.profiler(with_flops=True)`` may report either MACs or
   2*MAC depending on the torch build. We calibrate the convention with a
   single isolated ``nn.Linear`` of known shape and multiply the profiler
   number accordingly. The measured ratio is recorded in the JSON.

2. **Incomplete operator coverage.** ``F.scaled_dot_product_attention`` (the
   attention core) is frequently *not* counted by the profiler. Any compute-
   bearing op the profiler reports as 0 FLOPs is recorded by name and forces
   ``FLOPS_STATUS = "PARTIALLY_ESTIMATED"`` — the gap is disclosed, never
   folded silently into a 0-cost assumption.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import torch
from torch.profiler import ProfilerActivity, profile

from experiments.wp2_routing_v2.src.compute import (
    direct_path_flops,
    semantic_parser_flops,
    semantic_renderer_flops,
)
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch
from experiments.wp2_routing_v2.src.typed_modules import (
    DirectPath,
    SemanticParser,
    SemanticRenderer,
)

_ARTIFACT_PATH = Path("artifacts/wp2-routing-v2/metrology/flop_crosscheck.json")

# Compute-bearing operator name hints. A profiler event matching one of these
# with 0 reported FLOPs is treated as an *uncounted* op (coverage gap), not as
# a genuinely free operation.
_COMPUTE_OP_HINTS = (
    "matmul", "::mm", "::bmm", "baddbmm", "addmm", "linear",
    "scaled_dot_product", "attention", "einsum", "conv",
)

# Matmul-family ops the profiler's with_flops DOES support. Their FLOPs are
# real when reported.
_COUNTED_MATMUL_HINTS = ("::mm", "::bmm", "baddbmm", "addmm")

# Container/dispatch ops that decompose into matmul-family children. On CUDA
# these appear as separate 0-FLOP parent events while the child mm/addmm carries
# the FLOPs, so a 0-FLOP parent here is NOT a genuine coverage gap.
_CONTAINER_OPS = frozenset({"aten::linear", "aten::matmul"})

_E_F_THRESHOLD = 0.03


def _activities() -> list[ProfilerActivity]:
    acts = [ProfilerActivity.CPU]
    if torch.cuda.is_available():
        acts.append(ProfilerActivity.CUDA)
    return acts


def _profile_flops(fn: Callable[[], Any]) -> tuple[int, dict[str, int], list[str]]:
    """Run ``fn`` once under the profiler and sum ``evt.flops`` over events.

    Returns (total_raw_flops, per_op_flops, uncounted_compute_op_names).
    """
    with torch.no_grad(), profile(
        activities=_activities(), record_shapes=True, with_flops=True
    ) as prof:
        fn()
        if torch.cuda.is_available():
            torch.cuda.synchronize()

    total = 0
    per_op: dict[str, int] = {}
    zero_flop_compute: list[str] = []
    for evt in prof.key_averages():
        flops = int(getattr(evt, "flops", 0) or 0)
        total += flops
        if flops > 0:
            per_op[evt.key] = per_op.get(evt.key, 0) + flops
        else:
            key = evt.key.lower()
            if any(hint in key for hint in _COMPUTE_OP_HINTS):
                zero_flop_compute.append(evt.key)

    # A 0-FLOP container op (aten::linear / aten::matmul) is a genuine coverage
    # gap only if no matmul-family child was counted anywhere in this pass.
    counted_matmul = any(
        any(hint in key.lower() for hint in _COUNTED_MATMUL_HINTS) for key in per_op
    )
    uncounted = [
        op for op in zero_flop_compute
        if not (op in _CONTAINER_OPS and counted_matmul)
    ]
    return total, per_op, sorted(set(uncounted))


def calibrate_convention(device: str) -> dict[str, Any]:
    """Empirically decide whether the profiler reports MACs or 2*MAC.

    Runs one isolated ``nn.Linear(in, out)`` of known shape whose exact MAC
    count is ``rows * in * out``. If the profiler's raw FLOPs match that count
    it is reporting MACs (multiplier 2 to reach logical 2*MAC accounting); if
    it matches twice that, it already reports 2*MAC (multiplier 1).
    """
    rows, d_in, d_out = 8, 128, 256
    lin = torch.nn.Linear(d_in, d_out, bias=True).to(device).eval()
    x = torch.randn(rows, d_in, device=device)
    raw, _, _ = _profile_flops(lambda: lin(x))
    mac = rows * d_in * d_out
    ratio = raw / mac if mac else float("nan")
    if abs(ratio - 1.0) <= abs(ratio - 2.0):
        convention, multiplier = "MAC", 2
    else:
        convention, multiplier = "FLOP(2*MAC)", 1
    return {
        "convention": convention,
        "profiler_to_logical_multiplier": multiplier,
        "calibration_ratio_raw_over_mac": ratio,
        "calibration_raw_flops": raw,
        "calibration_expected_mac": mac,
        "note": (
            "ratio~1 => profiler reports MACs, multiply by 2 for logical 2*MAC; "
            "ratio~2 => profiler already reports 2*MAC, multiply by 1"
        ),
    }


def compute_crosscheck(
    batch_size: int = 64,
    device: str | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Core compute: profile each module on a real batch and compare to the
    analytic formulas. Returns the full result dict (also the JSON payload).
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    gen = torch.Generator().manual_seed(seed)
    tokens, state, _canonical, _kind = generate_batch(batch_size, gen, device=device)

    direct = DirectPath().to(device).eval()
    parser = SemanticParser().to(device).eval()
    renderer = SemanticRenderer().to(device).eval()

    convention = calibrate_convention(device)
    multiplier = convention["profiler_to_logical_multiplier"]

    # name -> (forward-thunk, per-sample logical formula, has_attention)
    plan: dict[str, tuple[Callable[[], Any], Callable[[], int], bool]] = {
        "DirectPath": (lambda: direct(tokens), direct_path_flops, True),
        "SemanticParser": (lambda: parser(tokens), semantic_parser_flops, True),
        "SemanticRenderer": (lambda: renderer(state), semantic_renderer_flops, False),
    }

    modules: dict[str, Any] = {}
    all_uncounted: set[str] = set()
    e_f_values: list[float] = []
    for name, (fwd, flop_fn, has_attn) in plan.items():
        raw, per_op, uncounted = _profile_flops(fwd)
        f_profiler_adjusted = raw * multiplier
        f_logical = int(flop_fn()) * batch_size
        denom = max(f_logical, f_profiler_adjusted)
        e_f = abs(f_logical - f_profiler_adjusted) / denom if denom > 0 else float("nan")
        e_f_values.append(e_f)
        all_uncounted.update(uncounted)
        modules[name] = {
            "F_logical": f_logical,
            "F_logical_per_sample": int(flop_fn()),
            "F_profiler_raw": raw,
            "F_profiler_adjusted": f_profiler_adjusted,
            "e_F": e_f,
            "e_F_within_threshold": bool(e_f <= _E_F_THRESHOLD),
            "has_attention_core": has_attn,
            "profiler_counted_ops": per_op,
            "profiler_uncounted_compute_ops": uncounted,
        }

    coverage_complete = len(all_uncounted) == 0
    all_within = all(e <= _E_F_THRESHOLD for e in e_f_values)
    status = "PASS" if (all_within and coverage_complete) else "PARTIALLY_ESTIMATED"

    return {
        "act": "B2 — profiler FLOP cross-check",
        "batch_size": batch_size,
        "device": device,
        "seed": seed,
        "e_F_threshold": _E_F_THRESHOLD,
        "profiler_convention": convention,
        "modules": modules,
        "profiler_uncounted_compute_ops": sorted(all_uncounted),
        "coverage_complete": coverage_complete,
        "FLOPS_STATUS": status,
    }


def main() -> None:
    result = compute_crosscheck()
    _ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ARTIFACT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    conv = result["profiler_convention"]
    print(
        f"[calibration] convention={conv['convention']} "
        f"ratio={conv['calibration_ratio_raw_over_mac']:.4f} "
        f"multiplier={conv['profiler_to_logical_multiplier']}"
    )
    for name, m in result["modules"].items():
        unc = m["profiler_uncounted_compute_ops"]
        tag = "OK" if m["e_F_within_threshold"] else "GAP"
        unc_str = f" uncounted={unc}" if unc else ""
        print(
            f"[{tag}] {name:16s} F_logical={m['F_logical']:>12d} "
            f"F_profiler_adj={m['F_profiler_adjusted']:>12d} e_F={m['e_F']:.4f}{unc_str}"
        )
    print(f"FLOPS_STATUS={result['FLOPS_STATUS']} -> {_ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
