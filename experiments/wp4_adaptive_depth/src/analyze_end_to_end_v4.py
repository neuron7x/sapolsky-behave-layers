"""Analyze frozen paid-halt WP4 v4."""
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
from experiments.wp4_adaptive_depth.src.runner_end_to_end_v4 import EXPECTED_SEEDS
from experiments.wp4_adaptive_depth.src.runner_exact_compute_v3 import HELD_OUT_DISTRIBUTIONS
from experiments.wp4_adaptive_depth.src.runner_exact_compute_v31 import FROZEN_TOTAL_HOPS


def analyze(runs_dir: Path) -> dict:
    runs = [json.loads(path.read_text()) for path in sorted(runs_dir.glob("seed*.json"))]
    seeds = sorted(run["seed"] for run in runs)
    errors = []
    if seeds != EXPECTED_SEEDS:
        errors.append(f"seed set {seeds} != frozen {EXPECTED_SEEDS}")
    if any(run.get("protocol_commit") != "b6bc531" for run in runs):
        errors.append("protocol commit mismatch")
    if any(run.get("allocation_replicates") != 32 or run.get("batch_size") != 4096 for run in runs):
        errors.append("frozen replicate-count or batch-size mismatch")

    names = [*DISTRIBUTIONS, *HELD_OUT_DISTRIBUTIONS]
    raw_p = {}
    per_distribution = {}
    for name in names:
        cells = [run["distributions"][name] for run in runs]
        differences = [float(cell["paired_solved_difference"]) for cell in cells]
        contract = all(
            cell["budget_was_derived_from_realized_m"] is False
            and cell["frozen_lookup_budget"] == FROZEN_TOTAL_HOPS[name]
            and cell["adaptive_paid_probe"]["billed_lookups"] == FROZEN_TOTAL_HOPS[name]
            for cell in cells
        )
        if not contract:
            errors.append(f"{name}: paid-budget contract failed")
        lo, hi = _bootstrap_ci(differences, seed=20260720)
        raw_p[name] = exact_positive_randomization_p(differences)
        per_distribution[name] = {
            "n_data_seeds": len(differences),
            "mean_paired_solved_difference": sum(differences) / len(differences),
            "bootstrap_ci95": [lo, hi],
            "exact_randomization_p_raw": raw_p[name],
            "worst_seed_difference": min(differences),
            "mean_adaptive_solved": sum(float(c["adaptive_paid_probe"]["solved"]) for c in cells) / len(cells),
            "mean_unfinished_items": sum(int(c["adaptive_paid_probe"]["unfinished_items"]) for c in cells) / len(cells),
            "paid_budget_contract_all_cells": contract,
        }
    adjusted = holm_adjust(raw_p)
    for name in names:
        row = per_distribution[name]
        row["holm_adjusted_p"] = adjusted[name]
        row["primary_pass"] = bool(
            row["paid_budget_contract_all_cells"]
            and row["bootstrap_ci95"][0] > MINIMUM_MEANINGFUL_EFFECT
            and row["holm_adjusted_p"] < 0.05
            and row["worst_seed_difference"] > 0
        )
    development_pass = all(per_distribution[name]["primary_pass"] for name in DISTRIBUTIONS)
    held_out_pass_count = sum(bool(per_distribution[name]["primary_pass"]) for name in HELD_OUT_DISTRIBUTIONS)
    supported = not errors and development_pass and held_out_pass_count >= 2
    return {
        "analysis_version": "4.0.0",
        "protocol_commit": "b6bc531",
        "status": "INTERNAL_CONFIRMATORY_NOT_EXTERNALLY_PREREGISTERED",
        "errors": errors,
        "per_distribution": per_distribution,
        "gates": {
            "frozen_seed_set": seeds == EXPECTED_SEEDS,
            "all_development_distributions_pass": development_pass,
            "held_out_pass_count": held_out_pass_count,
            "held_out_required": 2,
        },
        "verdict": "SUPPORTED_END_TO_END_INTERNAL" if supported else "END_TO_END_ADVANTAGE_NOT_SUPPORTED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("artifacts/wp4-end-to-end-v4/raw_runs"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/wp4-end-to-end-v4"))
    args = parser.parse_args()
    result = analyze(args.runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(result, indent=2))
    (args.out / "verdict.json").write_text(json.dumps({"verdict": result["verdict"], "status": result["status"]}, indent=2))
    print(json.dumps({"verdict": result["verdict"], "gates": result["gates"]}, indent=2))


if __name__ == "__main__":
    main()
