"""WP-2 v1.1 runner — heterogeneous task, BINDING budget K=2 of 8.

Reports overall + per-type (recall/copy) accuracy and, crucially, per-type
routing utilization: does the learned controller pick DIFFERENT blocks for
copy vs recall? That is the direct adaptivity signal. Same 5 configs.

Usage: PYTHONPATH=. python experiments/wp2_routing_v1/src/runner_mixed.py \
    --seeds 0 1 2 3 4 --out artifacts/wp2-routing-v1_1/raw_runs
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from experiments.wp2_routing_v1.src.compute import active_inference_flops
from experiments.wp2_routing_v1.src.model import ModelConfig, RoutedTransformer, RoutingMode
from experiments.wp2_routing_v1.src.task_mixed import MixedTaskConfig, answer_mask, generate_batch

TASK = MixedTaskConfig()
MCFG = ModelConfig(seq_len=64, n_layer=8, d_model=128, n_head=4, d_ff=512, budget_k=2)  # BINDING K=2
TRAIN_STEPS = 2500
BATCH = 64
LR = 1e-3
WD = 0.01
WARMUP = 100
EVAL_EVERY = 500
VAL_SEQ = 2000
GRAD_CLIP = 1.0
MODES = [RoutingMode.DENSE, RoutingMode.RANDOM, RoutingMode.FROZEN, RoutingMode.LEARNED, RoutingMode.FIXED_DEPTH]


def _make_val(device):
    g = torch.Generator().manual_seed(999_999)
    xs, ys, rs = [], [], []
    rem = VAL_SEQ
    while rem > 0:
        b = min(256, rem)
        x, y, r = generate_batch(TASK, b, g, "cpu")
        xs.append(x); ys.append(y); rs.append(r); rem -= b
    x = torch.cat(xs)[:VAL_SEQ].to(device)
    y = torch.cat(ys)[:VAL_SEQ].to(device)
    r = torch.cat(rs)[:VAL_SEQ].to(device)
    m = answer_mask(TASK, VAL_SEQ, device)
    return x, y, r, m


@torch.no_grad()
def _evaluate(model, x, y, is_recall, amask, device):
    model.eval()
    ce_sum = 0.0; n = 0
    correct = 0; correct_r = 0; correct_c = 0; nr = 0; nc = 0
    util_r = torch.zeros(MCFG.n_layer, device=device); util_c = torch.zeros(MCFG.n_layer, device=device)
    cnt_r = 0; cnt_c = 0; viol = 0
    for i in range(0, x.shape[0], 256):
        xb, yb, rb, mb = x[i:i+256], y[i:i+256], is_recall[i:i+256], amask[i:i+256]
        logits = model(xb, seq_seed=None)
        sel = mb.view(-1)
        ll = logits.view(-1, MCFG.vocab_size)[sel]
        tt = yb.view(-1)[sel]
        ce_sum += float(F.cross_entropy(ll, tt, reduction="sum")); n += int(sel.sum())
        pred = ll.argmax(-1)
        ok = pred == tt
        correct += int(ok.sum())
        rr = rb
        correct_r += int(ok[rr].sum()); nr += int(rr.sum())
        correct_c += int(ok[~rr].sum()); nc += int((~rr).sum())
        mask = model._last_mask
        util_r += mask[rr].sum(0); cnt_r += int(rr.sum())
        util_c += mask[~rr].sum(0); cnt_c += int((~rr).sum())
        viol += int((model.last_active_counts() > MCFG.budget_k).sum())
    ur = (util_r / max(cnt_r, 1)).tolist()
    uc = (util_c / max(cnt_c, 1)).tolist()
    # routing divergence between the two types: L1 distance of utilization
    route_div = sum(abs(a - b) for a, b in zip(ur, uc))
    return {
        "answer_ce": ce_sum / max(n, 1),
        "acc_overall": correct / max(n, 1),
        "acc_recall": correct_r / max(nr, 1),
        "acc_copy": correct_c / max(nc, 1),
        "util_recall": ur,
        "util_copy": uc,
        "routing_divergence_copy_vs_recall": route_div,
        "budget_violations": viol,
    }


def run_one(mode, seed, device):
    torch.manual_seed(seed)
    model = RoutedTransformer(MCFG, mode).to(device)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=WD, betas=(0.9, 0.95))
    gen = torch.Generator().manual_seed(seed)
    vx, vy, vr, vm = _make_val(device)
    best_ce = float("inf"); best = None
    t0 = time.perf_counter()
    for step in range(TRAIN_STEPS):
        model.train()
        for pg in opt.param_groups:
            pg["lr"] = LR * min(1.0, (step + 1) / WARMUP)
        xb, yb, _ = generate_batch(TASK, BATCH, gen, "cpu")
        xb, yb = xb.to(device), yb.to(device)
        nonpad = yb.view(-1) != TASK.pad_token
        logits = model(xb, seq_seed=seed * 100000 + step)
        loss = F.cross_entropy(logits.view(-1, MCFG.vocab_size)[nonpad], yb.view(-1)[nonpad])
        opt.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(params, GRAD_CLIP); opt.step()
        if (step + 1) % EVAL_EVERY == 0 or step == TRAIN_STEPS - 1:
            ev = _evaluate(model, vx, vy, vr, vm, device)
            if ev["answer_ce"] < best_ce:
                best_ce = ev["answer_ce"]; best = ev
    train_s = time.perf_counter() - t0
    active = MCFG.n_layer if mode == RoutingMode.DENSE else MCFG.budget_k
    has_ctrl = mode in (RoutingMode.LEARNED, RoutingMode.FROZEN)
    return {
        "mode": mode.value, "seed": seed, "device": device,
        "train_steps": TRAIN_STEPS, "train_seconds": round(train_s, 2),
        "best_answer_ce": best_ce, "final_eval": best,
        "active_blocks": active,
        "active_inference_flops": active_inference_flops(MCFG, TASK.seq_len, active, has_ctrl),
        "controller_flops": (MCFG.n_layer * 2 * ((MCFG.d_model + 1) * 64 + 64)) if has_ctrl else 0,
        "budget_k": MCFG.budget_k,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-routing-v1_1/raw_runs"))
    ap.add_argument("--steps", type=int, default=None)
    args = ap.parse_args()
    global TRAIN_STEPS
    if args.steps:
        TRAIN_STEPS = args.steps
    device = "cuda" if torch.cuda.is_available() else "cpu"
    for mode in MODES:
        d = args.out / mode.value
        d.mkdir(parents=True, exist_ok=True)
        for seed in args.seeds:
            res = run_one(mode, seed, device)
            (d / f"seed{seed}.json").write_text(json.dumps(res, indent=2))
            fe = res["final_eval"]
            print(f"[{mode.value:12s} s{seed}] ce={res['best_answer_ce']:.4f} "
                  f"acc={fe['acc_overall']:.3f} (R={fe['acc_recall']:.3f} C={fe['acc_copy']:.3f}) "
                  f"route_div={fe['routing_divergence_copy_vs_recall']:.2f} t={res['train_seconds']}s")


if __name__ == "__main__":
    main()
