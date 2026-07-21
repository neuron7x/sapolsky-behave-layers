"""WP14 real-LM boundary robustness under a CONTEXTUAL difficulty signal.

WP6 found real-LM per-token compute allocation non-identifiable using UNIGRAM surprisal (a crude
difficulty proxy). This re-tests with BIGRAM surprisal -log P(target|prev) -- a stronger, contextual,
model-independent difficulty signal -- to check whether the WP6 negative is robust to the difficulty
definition. Same frozen corpus + byte recurrent LM as WP6.
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
    return torch.tensor(list(CORPUS.read_text(encoding="utf-8").encode("utf-8", "ignore")), dtype=torch.long)


def _bigram_surprisal(data: torch.Tensor):
    big: collections.Counter = collections.Counter()
    uni: collections.Counter = collections.Counter()
    d = data.tolist()
    for i in range(len(d) - 1):
        big[(d[i], d[i + 1])] += 1
        uni[d[i]] += 1
    return lambda prev, tgt: -math.log((big[(prev, tgt)] + 1) / (uni[prev] + VOCAB))


def run_seed(seed: int, device: str) -> dict:
    data = _data()
    bsurp = _bigram_surprisal(data)
    torch.manual_seed(seed)
    m = ByteRecurrentLM().to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=LR)
    gen = torch.Generator().manual_seed(seed + 7)
    lo, hi = 0, int(len(data) * 0.9)
    for step in range(TRAIN_STEPS):
        k = K_CHOICES[step % len(K_CHOICES)]
        ix = torch.randint(lo, hi - SEQ_LEN - 1, (BATCH,), generator=gen)
        x = torch.stack([data[i:i + SEQ_LEN] for i in ix]).to(device)
        y = torch.stack([data[i + 1:i + SEQ_LEN + 1] for i in ix]).to(device)
        loss = F.cross_entropy(m(x, k).reshape(-1, VOCAB), y.reshape(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    n_ev = EVAL_TOKENS // SEQ_LEN + 1
    eg = torch.Generator().manual_seed(seed + 777)
    ix = torch.randint(int(len(data) * 0.9), len(data) - SEQ_LEN - 1, (n_ev,), generator=eg)
    xb = torch.stack([data[i:i + SEQ_LEN] for i in ix]).to(device)
    yb = torch.stack([data[i + 1:i + SEQ_LEN + 1] for i in ix]).to(device)
    prev, tgt = xb.reshape(-1), yb.reshape(-1)
    sv = torch.tensor([bsurp(prev[j].item(), tgt[j].item()) for j in range(len(tgt))])
    q1, q2 = torch.quantile(sv, torch.tensor([1 / 3, 2 / 3]))
    masks = {"easy": sv <= q1, "med": (sv > q1) & (sv <= q2), "hard": sv > q2}
    loss_bk: dict[str, dict[str, float]] = {b: {} for b in BUCKETS}
    with torch.no_grad():
        for k in K_CHOICES:
            per = F.cross_entropy(m(xb, k).reshape(-1, VOCAB), yb.reshape(-1), reduction="none")
            for b in BUCKETS:
                loss_bk[b][str(k)] = per[masks[b].to(device)].mean().item()
    return {"seed": seed, "buckets": BUCKETS, "k_choices": K_CHOICES,
            "difficulty_signal": "bigram_surprisal", "loss": loss_bk}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp14-real-lm-contextual/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, device)
        (args.out / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        print(f"[s{seed}] " + " ".join(f"{b}:K1={r['loss'][b]['1']:.2f},K3={r['loss'][b]['3']:.2f}" for b in BUCKETS))


if __name__ == "__main__":
    main()
