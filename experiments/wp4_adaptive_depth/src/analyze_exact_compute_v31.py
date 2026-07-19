"""Analyze prospective amendment v3.1 without reading invalid v3 outcomes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci
from experiments.wp4_adaptive_depth.src.analyze_exact_compute_v3 import (
    MINIMUM_MEANINGFUL_EFFECT,
    exact_positive_randomization_p,
    holm_adjust,
)
from experiments.wp4_adaptive_depth.src.runner import DISTRIBUTIONS
from experiments.wp4_adaptive_depth.src.runner_exact_compute_v3 import HELD_OUT_DISTRIBUTIONS
from experiments.wp4_adaptive_depth.src.runner_exact_compute_v31 import FROZEN_TOTAL_HOPS

EXPECTED_SEEDS = list(range(200, 216))


def analyze(runs_dir: Path) -> dict[str, object]:
    runs = [json.loads(path.read_text()) for path in sorted(runs_dir.glob("seed*.json"))]
    seeds = sorted(run["seed"] for run in runs)
    errors = []
    if seeds != EXPECTED_SEEDS:
        errors.append(f"seed set {seeds} != frozen {EXPECTED_SEEDS}")
    if any(run.get("protocol_commit") != "760ebcd" for run in runs):
        errors.append("protocol amendment commit mismatch")
    if any(run.get("allocation_replicates") != 32 or run.get("batch_size") != 4096 for run in runs):
        errors.append("frozen replicate-count or batch-size mismatch")

    distributions = [*DISTRIBUTIONS, *HELD_OUT_DISTRIBUTIONS]
    raw_p: dict[str, float] = {}
    per_distribution: dict[str, object] = {}
    for name in distributions:
        cells = [run["distributions"][name] for run in runs]
        differences = [float(cell["paired_solved_difference"]) for cell in cells]
        exact_compute = all(
            cell["exact_compute_contract"]
            and cell["frozen_total_hops"] == FROZEN_TOTAL_HOPS[name]
            and cell["adaptive_budgeted"]["total_hops"] == FROZEN_TOTAL_HOPS[name]
            and cell["budget_was_derived_from_realized_m"] is False
            for cell in cells
        )
        if not exact_compute:
            errors.append(f"{name}: frozen exact-budget contract failed")
        lo, hi = _bootstrap_ci(differences, seed=20260720)
        raw_p[name] = exact_positive_randomization_p(differences)
        per_distribution[name] = {
            "n_data_seeds": len(differences),
            "frozen_total_hops": FROZEN_TOTAL_HOPS[name],
            "mean_paired_solved_difference": sum(differences) / len(differences),
            "bootstrap_ci95": [lo, hi],
            "exact_randomization_p_raw": raw_p[name],
            "exact_total_compute_all_cells": exact_compute,
            "worst_seed_difference": min(differences),
            "mean_adaptive_budgeted_solved": sum(
                float(cell["adaptive_budgeted"]["solved"]) for cell in cells
            ) / len(cells),
            "mean_realized_budget_delta_vs_sum_m": sum(
                cell["frozen_total_hops"] - cell["realized_sum_m_audit_only"] for cell in cells
            ) / len(cells),
        }

    adjusted = holm_adjust(raw_p)
    for name in distributions:
        item = per_distribution[name]
        item["holm_adjusted_p"] = adjusted[name]
        item["primary_pass"] = (
            item["exact_total_compute_all_cells"]
            and item["bootstrap_ci95"][0] > MINIMUM_MEANINGFUL_EFFECT
            and item["holm_adjusted_p"] < 0.05
        )
    development_pass = all(per_distribution[name]["primary_pass"] for name in DISTRIBUTIONS)
    held_out_pass_count = sum(
        bool(per_distribution[name]["primary_pass"]) for name in HELD_OUT_DISTRIBUTIONS
    )
    supported = not errors and development_pass and held_out_pass_count >= 2
    return {
        "analysis_version": "3.1.0",
        "protocol_amendment_commit": "760ebcd",
        "status": "INTERNAL_CONFIRMATORY_NOT_EXTERNALLY_PREREGISTERED",
        "errors": errors,
        "per_distribution": per_distribution,
        "gates": {
            "frozen_seed_set": seeds == EXPECTED_SEEDS,
            "all_development_distributions_pass": development_pass,
            "held_out_pass_count": held_out_pass_count,
            "held_out_required": 2,
            "invalid_v3_seeds_excluded": not any(seed in range(100, 116) for seed in seeds),
        },
        "verdict": "SUPPORTED_NARROWED_INTERNAL" if supported else "NOT_SUPPORTED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("artifacts/wp4-exact-compute-v31/raw_runs"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/wp4-exact-compute-v31"))
    args = parser.parse_args()
    result = analyze(args.runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(result, indent=2))
    (args.out / "verdict.json").write_text(
        json.dumps({"verdict": result["verdict"], "status": result["status"]}, indent=2)
    )
    print(json.dumps({"verdict": result["verdict"], "gates": result["gates"]}, indent=2))


if __name__ == "__main__":
    main()
