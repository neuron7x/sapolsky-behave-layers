"""Execute frozen WP4 v4 with every successor probe inside the shared budget."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from experiments.wp4_adaptive_depth.src.runner import stable_distribution_seed
from experiments.wp4_adaptive_depth.src.runner_exact_compute_v3 import ALL_DISTRIBUTIONS
from experiments.wp4_adaptive_depth.src.runner_exact_compute_v31 import FROZEN_TOTAL_HOPS
from experiments.wp4_adaptive_depth.src.substrate import run_policy
from experiments.wp4_adaptive_depth.src.task_hops import generate_batch

MILLIHOPS_PER_LOOKUP = 1000
EXPECTED_SEEDS = list(range(300, 316))


def run_paid_probe(
    table: torch.Tensor,
    start: torch.Tensor,
    lookup_budget: int,
    gen: torch.Generator,
) -> dict[str, object]:
    """Run without difficulty access; each observed successor consumes one lookup."""
    if lookup_budget < 0:
        raise ValueError("lookup_budget must be non-negative")
    batch_size = start.shape[0]
    cur = start.clone()
    idx = torch.arange(batch_size, device=start.device)
    moves = torch.zeros(batch_size, dtype=torch.long, device=start.device)
    active = torch.ones(batch_size, dtype=torch.bool, device=start.device)
    remaining = lookup_budget
    terminal_probes = 0

    while remaining and active.any():
        candidates = torch.nonzero(active, as_tuple=False).flatten()
        if len(candidates) > remaining:
            order = torch.randperm(len(candidates), generator=gen).to(start.device)
            selected = candidates[order[:remaining]]
        else:
            selected = candidates
        nxt = table[selected, cur[selected]]
        moved = nxt != cur[selected]
        cur[selected] = nxt
        moves[selected] += moved.long()
        halted = selected[~moved]
        active[halted] = False
        terminal_probes += int((~moved).sum().item())
        remaining -= len(selected)

    paid_padding = remaining
    remaining = 0
    billed = lookup_budget
    return {
        "moves_per_item": moves.cpu().tolist(),
        "billed_lookups": billed,
        "billed_millihops": billed * MILLIHOPS_PER_LOOKUP,
        "terminal_probes": terminal_probes,
        "paid_padding_lookups": paid_padding,
        "unfinished_items": int(active.sum().item()),
    }


def run_seed(seed: int, allocation_replicates: int, batch_size: int, device: str) -> dict:
    if seed not in EXPECTED_SEEDS:
        raise ValueError("v4 seed must be in frozen set 300..315")
    if batch_size != 4096 or allocation_replicates != 32:
        raise ValueError("v4 requires batch_size=4096 and 32 allocation replicates")
    distributions = {}
    for name, weights in ALL_DISTRIBUTIONS.items():
        lookup_budget = FROZEN_TOTAL_HOPS[name]
        data_seed = stable_distribution_seed(seed, f"v4:{name}")
        table, values, start, target, m = generate_batch(
            batch_size,
            torch.Generator().manual_seed(data_seed),
            device,
            m_weights=weights,
        )
        adaptive = run_paid_probe(
            table,
            start,
            lookup_budget,
            torch.Generator().manual_seed(stable_distribution_seed(seed, f"v4:{name}:adaptive")),
        )
        moves = torch.tensor(adaptive.pop("moves_per_item"), device=m.device)
        adaptive["solved"] = float((moves >= m).float().mean().item())
        adaptive["total_moves"] = int(moves.sum().item())

        controls = []
        for replicate in range(allocation_replicates):
            controls.append(
                run_policy(
                    "random_exact", 0, table, values, start, target, m,
                    torch.Generator().manual_seed(
                        stable_distribution_seed(
                            seed * allocation_replicates + replicate,
                            f"v4:{name}:allocation",
                        )
                    ),
                    total_hops=lookup_budget,
                )
            )
        control_mean = sum(float(row["solved"]) for row in controls) / len(controls)
        distributions[name] = {
            "data_seed": data_seed,
            "frozen_lookup_budget": lookup_budget,
            "frozen_millihop_budget": lookup_budget * MILLIHOPS_PER_LOOKUP,
            "realized_sum_m_audit_only": int(m.sum().item()),
            "budget_was_derived_from_realized_m": False,
            "adaptive_paid_probe": adaptive,
            "input_blind_exact_solved_mean": control_mean,
            "paired_solved_difference": float(adaptive["solved"]) - control_mean,
        }
    return {
        "seed": seed,
        "protocol_commit": "b6bc531",
        "status": "INTERNAL_CONFIRMATORY_GIT_ORDERED",
        "allocation_replicates": allocation_replicates,
        "batch_size": batch_size,
        "distributions": distributions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=EXPECTED_SEEDS)
    parser.add_argument("--allocation-replicates", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--out", type=Path, default=Path("artifacts/wp4-end-to-end-v4/raw_runs"))
    args = parser.parse_args()
    if args.seeds != EXPECTED_SEEDS:
        parser.error("v4 seed set is frozen to 300..315")
    args.out.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    for seed in args.seeds:
        result = run_seed(seed, args.allocation_replicates, args.batch_size, device)
        (args.out / f"seed{seed}.json").write_text(json.dumps(result, indent=2))
        print(f"seed={seed} complete")


if __name__ == "__main__":
    main()
