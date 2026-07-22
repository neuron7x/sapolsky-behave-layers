"""WP19: is the WP18 negative a property of the DATA or of the weight-tied mechanism?

Axis B = untied depth: L in {1,2,3} INDEPENDENT blocks, each depth a separately trained model, no
weight sharing and no multi-K training -- structurally unlike WP18's weight-tied block cycled over
K. Same corpora, same held-out eval shards, same difficulty terciles, same certificate.
See PREREGISTRATION.md; decision rule frozen before this file existed.
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.wp18_real_workload_pilot.src.analyze import C_ROUTE, _cert
from experiments.wp18_real_workload_pilot.src.runner import (
    BATCH,
    BUCKETS,
    EVAL_WINDOWS,
    LR,
    N_EVAL_SHARDS,
    TRAIN_STEPS,
    VOCAB,
    Block,
    _bigram_surprisal,
    _bytes,
)

ROOT = Path(__file__).resolve().parents[3]
WP18 = ROOT / "artifacts/wp18-real-workload-pilot"
OUT = ROOT / "artifacts/wp19-negative-robustness"
AC1_RAW = ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs"
DEPTHS = [1, 2, 3]
SEQ_LEN = 64
D_MODEL = 64


class UntiedDepthLM(nn.Module):
    """L INDEPENDENT blocks -- no weight tying. Depth is the compute axis."""

    def __init__(self, depth: int, d_model: int = D_MODEL, seq_len: int = SEQ_LEN) -> None:
        super().__init__()
        self.emb = nn.Embedding(VOCAB, d_model)
        self.pos = nn.Embedding(seq_len, d_model)
        self.blocks = nn.ModuleList([Block(d_model, 4) for _ in range(depth)])
        self.head = nn.Linear(d_model, VOCAB, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        t = x.shape[1]
        h = self.emb(x) + self.pos(torch.arange(t, device=x.device)).unsqueeze(0)
        for b in self.blocks:
            h = b(h)
        return self.head(h)


def run_cell(family: str, depth: int, seed: int, device: str) -> dict:
    train = _bytes(WP18 / f"corpus_{family}_train.txt")
    surp = _bigram_surprisal(train)
    torch.manual_seed(seed)
    m = UntiedDepthLM(depth).to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=LR)
    gen = torch.Generator().manual_seed(seed + 7)
    for _ in range(TRAIN_STEPS):                       # identical budget per model
        ix = torch.randint(0, len(train) - SEQ_LEN - 1, (BATCH,), generator=gen)
        x = torch.stack([train[i:i + SEQ_LEN] for i in ix]).to(device)
        y = torch.stack([train[i + 1:i + SEQ_LEN + 1] for i in ix]).to(device)
        loss = F.cross_entropy(m(x).reshape(-1, VOCAB), y.reshape(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

    shards = []
    for s in range(1, N_EVAL_SHARDS + 1):
        ev = _bytes(WP18 / f"corpus_{family}_eval{s}.txt")
        if len(ev) < SEQ_LEN * 4:
            continue
        eg = torch.Generator().manual_seed(seed * 1000 + s)
        ix = torch.randint(0, len(ev) - SEQ_LEN - 1, (EVAL_WINDOWS,), generator=eg)
        xb = torch.stack([ev[i:i + SEQ_LEN] for i in ix]).to(device)
        yb = torch.stack([ev[i + 1:i + SEQ_LEN + 1] for i in ix]).to(device)
        prev, tgt = xb.reshape(-1), yb.reshape(-1)
        sv = torch.tensor([surp(int(prev[j]), int(tgt[j])) for j in range(len(tgt))])
        q1, q2 = torch.quantile(sv, torch.tensor([1 / 3, 2 / 3]))
        masks = {"easy": sv <= q1, "med": (sv > q1) & (sv <= q2), "hard": sv > q2}
        with torch.no_grad():
            per = F.cross_entropy(m(xb).reshape(-1, VOCAB), yb.reshape(-1), reduction="none")
        shards.append({"shard": s,
                       "loss": {b: float(per[masks[b].to(device)].mean()) for b in BUCKETS}})
    return {"family": family, "depth": depth, "seed": seed, "buckets": BUCKETS, "shards": shards}


def analyze() -> dict[str, Any]:
    runs = [json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(OUT / "raw_runs/*.json")))]
    workloads: dict[str, Any] = {}
    for fam in ("prose", "code"):
        fr = [r for r in runs if r["family"] == fam]
        seeds = sorted({r["seed"] for r in fr})
        # one utility matrix per (seed, shard): rows = difficulty buckets, cols = depths
        mats, best_by_bucket = [], {b: [] for b in BUCKETS}
        for sd in seeds:
            by_depth = {r["depth"]: r for r in fr if r["seed"] == sd}
            if set(by_depth) != set(DEPTHS):
                continue
            for si in range(len(by_depth[DEPTHS[0]]["shards"])):
                m = [[-by_depth[d]["shards"][si]["loss"][b] for d in DEPTHS] for b in BUCKETS]
                mats.append(m)
                for bi, b in enumerate(BUCKETS):
                    best_by_bucket[b].append(DEPTHS[m[bi].index(max(m[bi]))])
        g_lo = {str(lam): _cert(mats, +1, DEPTHS, lam) for lam in (0.0, 0.3)}
        modal = {b: statistics.mode(v) for b, v in best_by_bucket.items()}
        best = max(g_lo.values())
        workloads[fam] = {
            "n_replicate_matrices": len(mats), "g_lo_by_lambda": g_lo, "best_g_lo": best,
            "c_route": C_ROUTE, "certifies": best > C_ROUTE,
            "modal_best_depth_per_bucket": modal,
            "single_best_depth_for_all_buckets": len(set(modal.values())) == 1,
        }

    ac1 = [json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(AC1_RAW / "seed*.json")))]
    dep = [str(d) for d in ac1[0]["depths"]]
    aks = [str(k) for k in ac1[0]["k_choices"]]
    pos = _cert([[[r["acc"][d][k] for k in aks] for d in dep] for r in ac1],
                +1, ac1[0]["k_choices"], 0.0)

    interaction = any(w["certifies"] or not w["single_best_depth_for_all_buckets"]
                      for w in workloads.values())
    if pos <= 0.0:
        verdict = "WP19_VOID"
    elif interaction:
        verdict = "NEGATIVE_IS_MECHANISM_SPECIFIC"
    else:
        verdict = "NEGATIVE_ROBUST_ACROSS_COMPUTE_AXES"
    return {
        "experiment": "wp19_negative_robustness",
        "verdict": verdict,
        "tier": "NEGATIVE-ROBUSTNESS -- untied-depth compute axis on the WP18 real workloads",
        "class_ceiling": "can only confirm or NARROW an existing negative; cannot create a positive",
        "compute_axis": "untied depth L in {1,2,3}, independent blocks, one model per depth",
        "workloads": workloads,
        "positive_control_synthetic_ac1_g_lo": pos,
        "implication": ("WP18's boundary is a property of the data, not of weight tying; the kill "
                        "rule stands as written." if verdict == "NEGATIVE_ROBUST_ACROSS_COMPUTE_AXES"
                        else "WP18's CWC-RD3 must be NARROWED to the weight-tied compute axis."),
        "prohibited_extrapolations": ["any architecture claim", "L7",
                                      "adaptive compute never helps real LMs",
                                      "the boundary at large pretrained scale"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.analyze_only:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        (OUT / "raw_runs").mkdir(exist_ok=True)
        for family in ("prose", "code"):
            for depth in DEPTHS:
                for seed in args.seeds:
                    r = run_cell(family, depth, seed, device)
                    (OUT / "raw_runs" / f"{family}_L{depth}_s{seed}.json").write_text(
                        json.dumps(r, indent=2))
                    lo = r["shards"][0]["loss"]
                    print(f"[{family} L{depth} s{seed}] easy={lo['easy']:.3f} "
                          f"med={lo['med']:.3f} hard={lo['hard']:.3f}")
    r = analyze()
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2) + "\n")
    print(f"WP19 VERDICT: {r['verdict']}")
    for fam, w in r["workloads"].items():
        print(f"  {fam:6s}: G_lo {w['g_lo_by_lambda']} best={w['best_g_lo']:+.4f} "
              f"certifies={w['certifies']} | modal best depth {w['modal_best_depth_per_bucket']} "
              f"single={w['single_best_depth_for_all_buckets']}")
    print(f"  positive control: {r['positive_control_synthetic_ac1_g_lo']:+.4f}")
    print(f"  => {r['implication']}")


if __name__ == "__main__":
    main()
