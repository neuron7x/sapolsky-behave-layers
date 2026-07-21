"""WP6 real-LM runner: train the byte recurrent LM on the frozen real corpus and measure
per-difficulty-bucket loss at each compute budget K. Difficulty = target-byte unigram surprisal
tercile (an independent signal). Writes one JSON per seed. Run:
  PYTHONPATH=. python -m experiments.wp6_real_lm.src.runner --seeds 0 1 2 3 4
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

import torch
import torch.nn.functional as F

from experiments.wp6_real_lm.src.model import SEQ_LEN, VOCAB, ByteRecurrentLM

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "artifacts/wp6-real-lm/corpus.txt"
K_CHOICES = [1, 2, 3]
TRAIN_STEPS = 2500
BATCH = 64
LR = 3e-3
EVAL_TOKENS = 4096
BUCKETS = ["easy", "med", "hard"]


def _data() -> torch.Tensor:
    raw = CORPUS.read_text(encoding="utf-8").encode("utf-8", errors="ignore")
    return torch.tensor(list(raw), dtype=torch.long)


def _surprisal(data: torch.Tensor) -> torch.Tensor:
    cnt = collections.Counter(data.tolist())
    tot = len(data)
    return torch.tensor([-math.log((cnt.get(b, 0) + 1) / tot) for b in range(VOCAB)])


def _batch(data, n, split, device):
    lo, hi = (0, int(len(data) * 0.9)) if split == "tr" else (int(len(data) * 0.9), len(data) - SEQ_LEN - 1)
    gen = torch.Generator().manual_seed(1234 + (0 if split == "tr" else 1))
    ix = torch.randint(lo, hi - SEQ_LEN - 1, (n,), generator=gen)
    x = torch.stack([data[i:i + SEQ_LEN] for i in ix])
    y = torch.stack([data[i + 1:i + SEQ_LEN + 1] for i in ix])
    return x.to(device), y.to(device)


def run_seed(seed: int, device: str) -> dict:
    data = _data()
    surpr = _surprisal(data)
    torch.manual_seed(seed)
    m = ByteRecurrentLM().to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=LR)
    tgen = torch.Generator().manual_seed(seed + 7)
    lo, hi = 0, int(len(data) * 0.9)
    for step in range(TRAIN_STEPS):
        k = K_CHOICES[step % len(K_CHOICES)]                 # teach iterable refinement
        ix = torch.randint(lo, hi - SEQ_LEN - 1, (BATCH,), generator=tgen)
        x = torch.stack([data[i:i + SEQ_LEN] for i in ix]).to(device)
        y = torch.stack([data[i + 1:i + SEQ_LEN + 1] for i in ix]).to(device)
        loss = F.cross_entropy(m(x, k).reshape(-1, VOCAB), y.reshape(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    # eval loss[bucket][K]
    n_ev = EVAL_TOKENS // SEQ_LEN + 1
    xb, yb = _batch(data, n_ev, "te", device)
    ys = yb.reshape(-1)
    s_y = surpr[ys.cpu()]
    q1, q2 = torch.quantile(s_y, torch.tensor([1 / 3, 2 / 3]))
    masks = {"easy": s_y <= q1, "med": (s_y > q1) & (s_y <= q2), "hard": s_y > q2}
    loss_bk: dict[str, dict[str, float]] = {b: {} for b in BUCKETS}
    with torch.no_grad():
        for k in K_CHOICES:
            per = F.cross_entropy(m(xb, k).reshape(-1, VOCAB), yb.reshape(-1), reduction="none")
            for b in BUCKETS:
                loss_bk[b][str(k)] = per[masks[b].to(device)].mean().item()
    return {"seed": seed, "buckets": BUCKETS, "k_choices": K_CHOICES,
            "cost_iters": {str(k): k for k in K_CHOICES}, "loss": loss_bk}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp6-real-lm/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, device)
        (args.out / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        line = " ".join(f"{b}:K1={r['loss'][b]['1']:.2f},K3={r['loss'][b]['3']:.2f}" for b in BUCKETS)
        print(f"[s{seed}] {line}")


if __name__ == "__main__":
    main()
