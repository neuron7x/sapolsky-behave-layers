"""Exploratory exact-total-compute pilot; never licenses a confirmatory claim."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci
from experiments.wp4_adaptive_depth.src.runner import DISTRIBUTIONS, stable_distribution_seed
from experiments.wp4_adaptive_depth.src.substrate import run_policy
from experiments.wp4_adaptive_depth.src.task_hops import generate_batch


def run_pilot(
    data_seeds: list[int], allocation_replicates: int, batch_size: int, device: str
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for distribution, weights in DISTRIBUTIONS.items():
        for seed in data_seeds:
            data_seed = stable_distribution_seed(seed, distribution)
            batch = generate_batch(
                batch_size,
                torch.Generator().manual_seed(data_seed),
                device,
                m_weights=weights,
            )
            table, values, start, target, m = batch
            adaptive = run_policy(
                "adaptive", 0, table, values, start, target, m,
                torch.Generator().manual_seed(0),
            )
            total_hops = adaptive["total_hops"]
            controls = []
            for replicate in range(allocation_replicates):
                allocation_seed = stable_distribution_seed(
                    seed * allocation_replicates + replicate, f"{distribution}:allocation"
                )
                controls.append(
                    run_policy(
                        "random_exact", 0, table, values, start, target, m,
                        torch.Generator().manual_seed(allocation_seed),
                        total_hops=total_hops,
                    )
                )
            control_solved = sum(float(c["solved"]) for c in controls) / len(controls)
            if any(c["total_hops"] != total_hops for c in controls):
                raise RuntimeError("exact-total-compute invariant violated")
            rows.append(
                {
                    "distribution": distribution,
                    "data_seed_index": seed,
                    "data_seed": data_seed,
                    "batch_size": batch_size,
                    "allocation_replicates": allocation_replicates,
                    "total_hops_each_policy": total_hops,
                    "adaptive_solved": adaptive["solved"],
                    "input_blind_exact_solved_mean": control_solved,
                    "paired_solved_difference": adaptive["solved"] - control_solved,
                }
            )

    summary: dict[str, object] = {}
    for distribution in DISTRIBUTIONS:
        differences = [
            float(row["paired_solved_difference"])
            for row in rows
            if row["distribution"] == distribution
        ]
        lo, hi = _bootstrap_ci(differences)
        summary[distribution] = {
            "n_data_seeds": len(differences),
            "mean_paired_solved_difference": sum(differences) / len(differences),
            "bootstrap_ci95": [lo, hi],
            "exact_total_compute": True,
        }
    return {
        "status": "EXPLORATORY_PILOT_NOT_PREREGISTERED",
        "design": "adaptive exact halt vs input-blind floor/ceiling allocation",
        "rows": rows,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-seeds", type=int, nargs="+", default=list(range(8)))
    parser.add_argument("--allocation-replicates", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.allocation_replicates <= 0 or args.batch_size <= 0:
        parser.error("allocation-replicates and batch-size must be positive")
    result = run_pilot(
        args.data_seeds,
        args.allocation_replicates,
        args.batch_size,
        "cuda" if torch.cuda.is_available() else "cpu",
    )
    payload = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload)
    print(payload)


if __name__ == "__main__":
    main()
