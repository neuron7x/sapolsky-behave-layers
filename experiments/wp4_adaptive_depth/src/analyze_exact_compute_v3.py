"""Analyze the Git-ordered internal WP4 exact-compute v3 run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci
from experiments.wp4_adaptive_depth.src.runner import DISTRIBUTIONS
from experiments.wp4_adaptive_depth.src.runner_exact_compute_v3 import HELD_OUT_DISTRIBUTIONS

EXPECTED_SEEDS = list(range(100, 116))
MINIMUM_MEANINGFUL_EFFECT = 0.05


def exact_positive_randomization_p(values: list[float]) -> float:
    """Exact one-sided paired sign-randomization p-value."""
    if not values:
        raise ValueError("values must not be empty")
    observed_sum = sum(values)
    extreme = 0
    total = 1 << len(values)
    for mask in range(total):
        permuted_sum = sum(
            value if mask & (1 << index) else -value
            for index, value in enumerate(values)
        )
        if permuted_sum >= observed_sum - 1e-15:
            extreme += 1
    return extreme / total


def holm_adjust(raw: dict[str, float]) -> dict[str, float]:
    ordered = sorted(raw, key=raw.get)
    adjusted: dict[str, float] = {}
    running = 0.0
    m = len(ordered)
    for rank, name in enumerate(ordered):
        candidate = min(1.0, (m - rank) * raw[name])
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


def analyze(runs_dir: Path) -> dict[str, object]:
    runs = [json.loads(path.read_text()) for path in sorted(runs_dir.glob("seed*.json"))]
    seeds = sorted(run["seed"] for run in runs)
    errors = []
    if seeds != EXPECTED_SEEDS:
        errors.append(f"seed set {seeds} != frozen {EXPECTED_SEEDS}")
    if any(run.get("protocol_commit") != "6245a6d" for run in runs):
        errors.append("protocol commit mismatch")

    distributions = [*DISTRIBUTIONS, *HELD_OUT_DISTRIBUTIONS]
    raw_p = {}
    per_distribution: dict[str, object] = {}
    for name in distributions:
        cells = [run["distributions"][name] for run in runs]
        differences = [float(cell["paired_solved_difference"]) for cell in cells]
        exact_compute = all(
            cell["exact_compute_contract"]
            and cell["total_hops_each_primary_arm"] == cell["adaptive"]["total_hops"]
            for cell in cells
        )
        if not exact_compute:
            errors.append(f"{name}: exact compute contract failed")
        lo, hi = _bootstrap_ci(differences, seed=20260719)
        raw_p[name] = exact_positive_randomization_p(differences)
        noisy = {
            rate: sum(
                float(cell["noisy_halt_secondary"][rate]["solved"]) for cell in cells
            ) / len(cells)
            for rate in ("0.01", "0.05", "0.1")
        }
        per_distribution[name] = {
            "n_data_seeds": len(differences),
            "mean_paired_solved_difference": sum(differences) / len(differences),
            "bootstrap_ci95": [lo, hi],
            "exact_randomization_p_raw": raw_p[name],
            "exact_total_compute_all_cells": exact_compute,
            "worst_seed_difference": min(differences),
            "noisy_halt_mean_solved": noisy,
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
        "analysis_version": "3.0.0",
        "protocol_commit": "6245a6d",
        "status": "INTERNAL_CONFIRMATORY_NOT_EXTERNALLY_PREREGISTERED",
        "errors": errors,
        "per_distribution": per_distribution,
        "gates": {
            "frozen_seed_set": seeds == EXPECTED_SEEDS,
            "all_development_distributions_pass": development_pass,
            "held_out_pass_count": held_out_pass_count,
            "held_out_required": 2,
        },
        "verdict": "SUPPORTED_NARROWED_INTERNAL" if supported else "NOT_SUPPORTED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("artifacts/wp4-exact-compute-v3/raw_runs"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/wp4-exact-compute-v3"))
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
