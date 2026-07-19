"""Execute prospective amendment v3.1 with frozen distribution-derived budgets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from experiments.wp4_adaptive_depth.src.runner import stable_distribution_seed
from experiments.wp4_adaptive_depth.src.runner_exact_compute_v3 import ALL_DISTRIBUTIONS
from experiments.wp4_adaptive_depth.src.substrate import run_policy
from experiments.wp4_adaptive_depth.src.task_hops import generate_batch

FROZEN_TOTAL_HOPS = {
    "uniform": 18432,
    "easy_skew": 12743,
    "hard_skew": 24121,
    "bimodal": 18432,
    "extreme_easy": 10103,
    "extreme_hard": 26761,
    "mid_peak": 18432,
}


def run_seed(
    seed: int, allocation_replicates: int, batch_size: int, device: str
) -> dict[str, object]:
    if batch_size != 4096:
        raise ValueError("v3.1 frozen budgets require batch_size=4096")
    distributions: dict[str, object] = {}
    for name, weights in ALL_DISTRIBUTIONS.items():
        budget = FROZEN_TOTAL_HOPS[name]
        data_seed = stable_distribution_seed(seed, f"v31:{name}")
        table, values, start, target, m = generate_batch(
            batch_size,
            torch.Generator().manual_seed(data_seed),
            device,
            m_weights=weights,
        )
        adaptive = run_policy(
            "adaptive_budgeted", 0, table, values, start, target, m,
            torch.Generator().manual_seed(stable_distribution_seed(seed, f"v31:{name}:adaptive")),
            total_hops=budget,
        )
        controls = []
        for replicate in range(allocation_replicates):
            controls.append(
                run_policy(
                    "random_exact", 0, table, values, start, target, m,
                    torch.Generator().manual_seed(
                        stable_distribution_seed(
                            seed * allocation_replicates + replicate, f"v31:{name}:allocation"
                        )
                    ),
                    total_hops=budget,
                )
            )
        if adaptive["total_hops"] != budget or any(
            control["total_hops"] != budget for control in controls
        ):
            raise RuntimeError("v3.1 frozen-budget equality failed")
        control_solved = sum(float(control["solved"]) for control in controls) / len(controls)
        distributions[name] = {
            "data_seed": data_seed,
            "frozen_total_hops": budget,
            "realized_sum_m_audit_only": int(m.sum().item()),
            "budget_was_derived_from_realized_m": False,
            "exact_compute_contract": True,
            "adaptive_budgeted": adaptive,
            "input_blind_exact_solved_mean": control_solved,
            "paired_solved_difference": float(adaptive["solved"]) - control_solved,
        }
    return {
        "seed": seed,
        "protocol_commit": "760ebcd",
        "status": "INTERNAL_CONFIRMATORY_GIT_ORDERED",
        "allocation_replicates": allocation_replicates,
        "batch_size": batch_size,
        "distributions": distributions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(200, 216)))
    parser.add_argument("--allocation-replicates", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--out", type=Path, default=Path("artifacts/wp4-exact-compute-v31/raw_runs"))
    args = parser.parse_args()
    if args.seeds != list(range(200, 216)):
        parser.error("v3.1 seed set is frozen to 200..215")
    if args.allocation_replicates != 32 or args.batch_size != 4096:
        parser.error("v3.1 requires 32 allocation replicates and batch size 4096")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        result = run_seed(seed, args.allocation_replicates, args.batch_size, device)
        (args.out / f"seed{seed}.json").write_text(json.dumps(result, indent=2))
        print(f"seed={seed} complete")


if __name__ == "__main__":
    main()
