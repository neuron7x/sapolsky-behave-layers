"""WP18 real-workload pilot runner (Act G3/G5/G7, PILOT ONLY -- no architecture claim).

Trains a byte-level weight-tied recurrent LM from scratch on each real workload and records, per
held-out eval shard, the per-difficulty-bucket loss at each compute budget K. That per-shard matrix
is the input to the identifiability certificate. Same mechanism as WP5/WP6 (K = shared-block
iterations), parameterised over model scale and sequence length. See PREREGISTRATION.md.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "artifacts/wp18-real-workload-pilot"
VOCAB = 256
K_CHOICES = [1, 2, 3]
BUCKETS = ["easy", "med", "hard"]
N_EVAL_SHARDS = 5
TRAIN_STEPS = 2000
BATCH = 64
LR = 3e-3
EVAL_WINDOWS = 64


class Block(nn.Module):
    def __init__(self, d: int, n_head: int) -> None:
        super().__init__()
        self.n_head = n_head
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.proj = nn.Linear(d, d, bias=False)
        self.fc = nn.Linear(d, 4 * d, bias=False)
        self.fout = nn.Linear(4 * d, d, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, c = x.shape
        q, k, v = self.qkv(x).split(c, dim=2)
        shape = (b, t, self.n_head, c // self.n_head)
        q, k, v = (z.view(*shape).transpose(1, 2) for z in (q, k, v))
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.proj(y.transpose(1, 2).contiguous().view(b, t, c))
        return x + self.fout(F.relu(self.fc(x)))


class ByteLM(nn.Module):
    """K shared-block iterations = K units of compute (the WP5/WP6 adaptive-compute mechanism)."""

    def __init__(self, d_model: int, seq_len: int, n_head: int = 4) -> None:
        super().__init__()
        self.emb = nn.Embedding(VOCAB, d_model)
        self.pos = nn.Embedding(seq_len, d_model)
        self.block = Block(d_model, n_head)
        self.head = nn.Linear(d_model, VOCAB, bias=False)

    def forward(self, x: torch.Tensor, k_iter: int) -> torch.Tensor:
        t = x.shape[1]
        h = self.emb(x) + self.pos(torch.arange(t, device=x.device)).unsqueeze(0)
        for _ in range(k_iter):
            h = self.block(h)
        return self.head(h)


def _bytes(path: Path) -> torch.Tensor:
    return torch.tensor(list(path.read_bytes()), dtype=torch.long)


def _bigram_surprisal(data: torch.Tensor):
    big: collections.Counter = collections.Counter()
    uni: collections.Counter = collections.Counter()
    d = data.tolist()
    for i in range(len(d) - 1):
        big[(d[i], d[i + 1])] += 1
        uni[d[i]] += 1
    return lambda prev, tgt: -math.log((big[(prev, tgt)] + 1) / (uni[prev] + VOCAB))


def run_cell(family: str, d_model: int, seq_len: int, seed: int, device: str) -> dict:
    train = _bytes(DATA / f"corpus_{family}_train.txt")
    surp = _bigram_surprisal(train)                     # difficulty model fit on TRAIN only
    torch.manual_seed(seed)
    m = ByteLM(d_model, seq_len).to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=LR)
    gen = torch.Generator().manual_seed(seed + 7)
    for step in range(TRAIN_STEPS):
        k = K_CHOICES[step % len(K_CHOICES)]             # train all budgets equally
        ix = torch.randint(0, len(train) - seq_len - 1, (BATCH,), generator=gen)
        x = torch.stack([train[i:i + seq_len] for i in ix]).to(device)
        y = torch.stack([train[i + 1:i + seq_len + 1] for i in ix]).to(device)
        loss = F.cross_entropy(m(x, k).reshape(-1, VOCAB), y.reshape(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

    shards = []
    for s in range(1, N_EVAL_SHARDS + 1):
        ev = _bytes(DATA / f"corpus_{family}_eval{s}.txt")
        if len(ev) < seq_len * 4:
            continue
        eg = torch.Generator().manual_seed(seed * 1000 + s)
        ix = torch.randint(0, len(ev) - seq_len - 1, (EVAL_WINDOWS,), generator=eg)
        xb = torch.stack([ev[i:i + seq_len] for i in ix]).to(device)
        yb = torch.stack([ev[i + 1:i + seq_len + 1] for i in ix]).to(device)
        prev, tgt = xb.reshape(-1), yb.reshape(-1)
        sv = torch.tensor([surp(int(prev[j]), int(tgt[j])) for j in range(len(tgt))])
        q1, q2 = torch.quantile(sv, torch.tensor([1 / 3, 2 / 3]))
        masks = {"easy": sv <= q1, "med": (sv > q1) & (sv <= q2), "hard": sv > q2}
        loss_bk: dict[str, dict[str, float]] = {b: {} for b in BUCKETS}
        with torch.no_grad():
            for k in K_CHOICES:
                per = F.cross_entropy(m(xb, k).reshape(-1, VOCAB), yb.reshape(-1), reduction="none")
                for b in BUCKETS:
                    loss_bk[b][str(k)] = float(per[masks[b].to(device)].mean())
        shards.append({"shard": s, "n_tokens": int(len(tgt)), "loss": loss_bk})
    return {"family": family, "d_model": d_model, "seq_len": seq_len, "seed": seed,
            "buckets": BUCKETS, "k_choices": K_CHOICES, "shards": shards}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--out", type=Path, default=DATA / "raw_runs")
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for family in ("prose", "code"):
        for d_model in (32, 64):
            for seq_len in (32, 64):
                for seed in args.seeds:
                    r = run_cell(family, d_model, seq_len, seed, device)
                    name = f"seed{seed}_{family}_d{d_model}_t{seq_len}.json"
                    (args.out / name).write_text(json.dumps(r, indent=2))
                    m = r["shards"][0]["loss"]
                    print(f"[{family} d{d_model} t{seq_len} s{seed}] "
                          f"easy K1={m['easy']['1']:.2f}/K3={m['easy']['3']:.2f} "
                          f"hard K1={m['hard']['1']:.2f}/K3={m['hard']['3']:.2f} "
                          f"({len(r['shards'])} shards)")


if __name__ == "__main__":
    main()
