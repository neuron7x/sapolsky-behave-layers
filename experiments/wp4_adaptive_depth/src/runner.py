"""Decisive experiment: does adaptive depth allocation beat the best static
allocation at matched average compute by exactly the theoretically-predicted
Jensen gap G = P(m > K)? Swept over several difficulty distributions P(m) so the
gap is confirmed as a PREDICTED CURVE, not a single fitted point.

Run: PYTHONPATH=. python -m experiments.wp4_adaptive_depth.src.runner --seeds 0-7
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from experiments.wp4_adaptive_depth.src.substrate import run_policy
from experiments.wp4_adaptive_depth.src.task_hops import MAX_M, generate_batch

# difficulty distributions over m ∈ {1..MAX_M}; each is a preregistered regime
DISTRIBUTIONS = {
    "uniform": torch.ones(MAX_M),
    "easy_skew": torch.tensor([5.0, 4.0, 3.0, 2.0, 1.0, 1.0, 1.0, 1.0]),
    "hard_skew": torch.tensor([1.0, 1.0, 1.0, 1.0, 2.0, 3.0, 4.0, 5.0]),
    "bimodal": torch.tensor([4.0, 1.0, 0.5, 0.5, 0.5, 0.5, 1.0, 4.0]),
}
VAL = 4000


def stable_distribution_seed(seed: int, dist_name: str) -> int:
    """Derive a process-independent seed from the declared inputs."""
    digest = hashlib.sha256(f"wp4:{seed}:{dist_name}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


def run_seed(seed: int, device: str) -> dict:
    out = {}
    for dist_name, w in DISTRIBUTIONS.items():
        data_seed = stable_distribution_seed(seed, dist_name)
        gen = torch.Generator().manual_seed(data_seed)
        table, values, start, target, m = generate_batch(VAL, gen, device, m_weights=w)
        e_m = m.float().mean().item()
        # Integer static depth nearest E[m]; exact parity is tested separately.
        K = round(e_m)
        rgen = torch.Generator().manual_seed(seed + 1)
        pol = {p: run_policy(p, K, table, values, start, target, m, rgen)
               for p in ("static", "random", "adaptive", "oracle")}
        p_m_gt_K = (m > K).float().mean().item()          # THEORY prediction
        out[dist_name] = {
            "data_seed": data_seed,
            "K": K, "E_m": e_m, "theory_P_m_gt_K": p_m_gt_K,
            "policies": pol,
            "solved_gap_adaptive_minus_static": pol["adaptive"]["solved"] - pol["static"]["solved"],
            "acc_gap_adaptive_minus_static": pol["adaptive"]["acc"] - pol["static"]["acc"],
            "adaptive_avg_hops": pol["adaptive"]["avg_hops"],
            "static_avg_hops": float(K),
        }
    return {"seed": seed, "distributions": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(8)))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp4-adaptive-depth-v2/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, device)
        (args.out / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        line = f"[s{seed}] "
        for d, v in r["distributions"].items():
            line += (f"{d}(K={v['K']}): gap={v['solved_gap_adaptive_minus_static']:.3f} "
                     f"theory={v['theory_P_m_gt_K']:.3f} | ")
        print(line)


if __name__ == "__main__":
    main()
