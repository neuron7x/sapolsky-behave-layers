"""WP5 adaptive-compute oracle-gap runner.

Trains the weight-tied recurrent model (one Block iteration = shift-by-1) and measures
acc[d][K]: accuracy on shift-by-d inputs using K compute iterations. Writes one JSON per seed.
The compute budget K is the mechanism; difficulty d is the context. Run:
  PYTHONPATH=. python -m experiments.wp5_adaptive_compute.src.runner_oracle --seeds 0 1 2 3 4
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F

from experiments.wp5_adaptive_compute.src.benchmark import DEPTHS, K_CHOICES, shift_batch
from experiments.wp5_adaptive_compute.src.model import RecurrentModel, VOCAB

TRAIN_STEPS = 1500
BATCH = 256
LR = 3e-3
EVAL_N = 1024


def _train(seed: int, device: str) -> RecurrentModel:
    torch.manual_seed(seed)
    m = RecurrentModel().to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=LR)
    gen = torch.Generator().manual_seed(seed + 1)
    for step in range(TRAIN_STEPS):
        d = DEPTHS[step % len(DEPTHS)]            # teach each iteration to advance the shift by 1
        x, y = shift_batch(BATCH, d, gen, device)
        loss = F.cross_entropy(m(x, k_iter=d).reshape(-1, VOCAB), y.reshape(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    return m


def run_seed(seed: int, device: str) -> dict:
    m = _train(seed, device)
    ev = torch.Generator().manual_seed(seed + 777)
    acc: dict[str, dict[str, float]] = {}
    for d in DEPTHS:
        acc[str(d)] = {}
        for k in K_CHOICES:
            x, y = shift_batch(EVAL_N, d, ev, device)
            with torch.no_grad():
                acc[str(d)][str(k)] = (m(x, k).argmax(-1) == y).float().mean().item()
    return {"seed": seed, "depths": DEPTHS, "k_choices": K_CHOICES,
            "cost_iters": {str(k): k for k in K_CHOICES}, "acc": acc}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp5-adaptive-compute-identifiability/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, device)
        (args.out / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        diag = " ".join(f"d{d}:K{d}={r['acc'][str(d)][str(d)]:.2f}" for d in DEPTHS)
        print(f"[s{seed}] diagonal {diag}")


if __name__ == "__main__":
    main()
