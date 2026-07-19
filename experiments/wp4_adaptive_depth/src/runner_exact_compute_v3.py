"""Execute the frozen internal WP4 exact-compute v3 protocol."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from experiments.wp4_adaptive_depth.src.runner import DISTRIBUTIONS, stable_distribution_seed
from experiments.wp4_adaptive_depth.src.substrate import run_policy
from experiments.wp4_adaptive_depth.src.task_hops import generate_batch

HELD_OUT_DISTRIBUTIONS = {
    "extreme_easy": torch.tensor([12.0, 8.0, 4.0, 2.0, 1.0, 1.0, 1.0, 1.0]),
    "extreme_hard": torch.tensor([1.0, 1.0, 1.0, 1.0, 2.0, 4.0, 8.0, 12.0]),
    "mid_peak": torch.tensor([1.0, 2.0, 6.0, 10.0, 10.0, 6.0, 2.0, 1.0]),
}
ALL_DISTRIBUTIONS = {**DISTRIBUTIONS, **HELD_OUT_DISTRIBUTIONS}
NOISE_RATES = (0.01, 0.05, 0.10)
CONTROLLER_COST_MILLIHOPS = (10, 50, 100, 250)


def run_seed(
    seed: int, allocation_replicates: int, batch_size: int, device: str
) -> dict[str, object]:
    distributions: dict[str, object] = {}
    for name, weights in ALL_DISTRIBUTIONS.items():
        data_seed = stable_distribution_seed(seed, f"v3:{name}")
        table, values, start, target, m = generate_batch(
            batch_size,
            torch.Generator().manual_seed(data_seed),
            device,
            m_weights=weights,
        )
        adaptive = run_policy(
            "adaptive", 0, table, values, start, target, m,
            torch.Generator().manual_seed(stable_distribution_seed(seed, f"v3:{name}:adaptive")),
        )
        total_hops = adaptive["total_hops"]
        controls = []
        for replicate in range(allocation_replicates):
            allocation_seed = stable_distribution_seed(
                seed * allocation_replicates + replicate, f"v3:{name}:allocation"
            )
            controls.append(
                run_policy(
                    "random_exact", 0, table, values, start, target, m,
                    torch.Generator().manual_seed(allocation_seed),
                    total_hops=total_hops,
                )
            )
        if any(control["total_hops"] != total_hops for control in controls):
            raise RuntimeError("exact-total-hop contract violated")
        control_solved = sum(float(control["solved"]) for control in controls) / len(controls)
        noisy = {}
        for rate in NOISE_RATES:
            noise_seed = stable_distribution_seed(seed, f"v3:{name}:noise:{rate}")
            noisy[str(rate)] = run_policy(
                "adaptive_noisy", 0, table, values, start, target, m,
                torch.Generator().manual_seed(noise_seed),
                halt_false_positive_rate=rate,
            )
        cost_accounting = {
            str(cost): {
                "operator_hops": total_hops,
                "halt_evaluations": adaptive["halt_evaluations"],
                "total_millihop_equivalents": (
                    1000 * total_hops + cost * adaptive["halt_evaluations"]
                ),
            }
            for cost in CONTROLLER_COST_MILLIHOPS
        }
        distributions[name] = {
            "data_seed": data_seed,
            "batch_size": batch_size,
            "total_hops_each_primary_arm": total_hops,
            "exact_compute_contract": True,
            "adaptive": adaptive,
            "input_blind_exact_solved_mean": control_solved,
            "paired_solved_difference": float(adaptive["solved"]) - control_solved,
            "noisy_halt_secondary": noisy,
            "controller_cost_secondary": cost_accounting,
        }
    return {
        "seed": seed,
        "protocol_commit": "6245a6d",
        "status": "INTERNAL_CONFIRMATORY_GIT_ORDERED",
        "allocation_replicates": allocation_replicates,
        "distributions": distributions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(100, 116)))
    parser.add_argument("--allocation-replicates", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--out", type=Path, default=Path("artifacts/wp4-exact-compute-v3/raw_runs"))
    args = parser.parse_args()
    if args.allocation_replicates <= 0 or args.batch_size <= 0:
        parser.error("allocation-replicates and batch-size must be positive")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        result = run_seed(seed, args.allocation_replicates, args.batch_size, device)
        (args.out / f"seed{seed}.json").write_text(json.dumps(result, indent=2))
        print(f"seed={seed} complete")


if __name__ == "__main__":
    main()
