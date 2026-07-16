"""CWC WP-1 AUDIT-mode diagnostic: torch.profiler + roofline report over a
synthetic workload (or, with --checkpoint-source, a real nanochat model's
decode step once a trained checkpoint is available).

This script's own output always carries claim_run=false / claimable=false —
it exists for periodic offline diagnosis, never as evidence for a production
latency/FLOPs claim (Act 4.13, 6.3).

    python scripts/instrumentation_audit.py --steps 10
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from cwc.instrumentation.audit import flop_model_comparison, roofline_report, run_torch_profiler
from cwc.instrumentation.flops import dense_linear_flops


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--warmup-steps", type=int, default=3)
    parser.add_argument("--tokens", type=int, default=256)
    parser.add_argument("--d-model", type=int, default=256)
    parser.add_argument("--output", type=Path, default=Path("artifacts/instrumentation/audit"))
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    weight = torch.randn(args.d_model, args.d_model, device=device)

    def workload() -> torch.Tensor:
        x = torch.randn(args.tokens, args.d_model, device=device)
        y = x @ weight
        return y.relu().sum()

    args.output.mkdir(parents=True, exist_ok=True)
    trace_path = args.output / "profiler.chrome_trace.json"
    audit_result = run_torch_profiler(
        workload, steps=args.steps, warmup_steps=args.warmup_steps,
        with_flops=True, trace_export_path=trace_path,
    )

    # audit_result's covered_flops sums over every timed step, so the
    # analytical comparison must cover the same `steps` calls, not just one.
    analytical_flops_per_step = dense_linear_flops(tokens=args.tokens, d_in=args.d_model, d_out=args.d_model)
    analytical_flops = analytical_flops_per_step * args.steps
    comparison = flop_model_comparison(analytical_flops=analytical_flops, audit_result=audit_result)

    roofline = None
    if device == "cuda":
        # Conservative placeholder rates when the exact hardware ceiling isn't
        # in nanochat's own lookup table (e.g. this laptop GPU) — provenance
        # says so explicitly rather than silently using a wrong number.
        roofline = roofline_report(
            total_flops=analytical_flops,
            total_bytes_moved=args.tokens * args.d_model * 4 * 2,
            peak_flops_per_s=1e12,
            peak_bandwidth_bytes_per_s=1e11,
            hardware_ceiling_provenance="placeholder rates (exact device not in nanochat's peak-flops table)",
        )

    report = {
        "audit_result": audit_result,
        "flop_comparison": comparison,
        "roofline": roofline,
        "claimable": False,
    }
    report_path = args.output / "audit_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
