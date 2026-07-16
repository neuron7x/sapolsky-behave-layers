"""WP-2 multi-seed causal experiment runner. Trains all 5 configs at a fixed
budget and identical data order per seed, evaluates on a fixed val set, and
writes one JSON per (config, seed) with quality/compute/systems/routing.

Usage: PYTHONPATH=. python experiments/wp2_routing_v1/src/runner.py \
    --seeds 0 1 2 --out artifacts/wp2-routing-v1/raw_runs
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
from experiments.wp2_routing_v1.src.task import TaskConfig, generate_batch, query_position_mask

# Calibrated pre-run (recorded deviation, before any claim run): n_pairs=6 sits
# between n_pairs=4 (solved even at K=4, no headroom) and n_pairs=8 (unsolved
# even dense); lr=1e-3 learns decisively where 3e-4 plateaued.
TASK = TaskConfig(n_pairs=6)
MCFG = ModelConfig()
TRAIN_STEPS = 2500
BATCH = 64
LR = 1e-3
WD = 0.01
WARMUP = 100
EVAL_EVERY = 500
VAL_SEQ = 2000
GRAD_CLIP = 1.0
MODES = [RoutingMode.DENSE, RoutingMode.RANDOM, RoutingMode.FROZEN, RoutingMode.LEARNED, RoutingMode.FIXED_DEPTH]


def _lr_at(step: int) -> float:
    if step < WARMUP:
        return LR * step / WARMUP
    return LR


def _make_val(device: str) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    g = torch.Generator().manual_seed(999_999)  # fixed val, same for all configs/seeds
    xs, ys = [], []
    remaining = VAL_SEQ
    while remaining > 0:
        b = min(256, remaining)
        x, y = generate_batch(TASK, b, g, device="cpu")
        xs.append(x); ys.append(y); remaining -= b
    x = torch.cat(xs)[:VAL_SEQ].to(device)
    y = torch.cat(ys)[:VAL_SEQ].to(device)
    qmask = query_position_mask(TASK, VAL_SEQ, device=device)
    return x, y, qmask


@torch.no_grad()
def _evaluate(model, x, y, qmask, device) -> dict:
    model.eval()
    full_ce_sum = 0.0; full_n = 0
    q_ce_sum = 0.0; q_n = 0
    active_total = 0.0; active_count = 0
    util = torch.zeros(MCFG.n_layer, device=device)
    budget_viol = 0
    for i in range(0, x.shape[0], 256):
        xb, yb, qb = x[i:i+256], y[i:i+256], qmask[i:i+256]
        logits = model(xb, seq_seed=None)
        logl = logits.view(-1, MCFG.vocab_size)
        # query-position CE (primary discriminator)
        qsel = qb.view(-1)
        q_ce = F.cross_entropy(logl[qsel], yb.view(-1)[qsel], reduction="sum")
        q_ce_sum += float(q_ce); q_n += int(qsel.sum())
        # full-seq CE over non-pad targets
        nonpad = yb.view(-1) != TASK.pad_token
        f_ce = F.cross_entropy(logl[nonpad], yb.view(-1)[nonpad], reduction="sum")
        full_ce_sum += float(f_ce); full_n += int(nonpad.sum())
        counts = model.last_active_counts()
        active_total += float(counts.sum()); active_count += counts.numel()
        util += (model._last_mask.sum(dim=0))
        budget_viol += int((counts > MCFG.budget_k).sum())
    util = (util / active_count).tolist()
    mean_active = active_total / active_count
    # routing entropy/gini over per-layer utilization
    u = torch.tensor(util) + 1e-9
    p = u / u.sum()
    ent = float(-(p * p.log()).sum() / torch.log(torch.tensor(float(MCFG.n_layer))))
    su = sorted(util)
    n = len(su); cum = sum((i + 1) * su[i] for i in range(n))
    gini = float((2 * cum) / (n * sum(su) + 1e-9) - (n + 1) / n) if sum(su) > 0 else 0.0
    dead = float(sum(1 for v in util if v < 1e-6) / MCFG.n_layer)
    return {
        "query_ce": q_ce_sum / max(q_n, 1),
        "full_ce": full_ce_sum / max(full_n, 1),
        "mean_active_blocks": mean_active,
        "per_layer_utilization": util,
        "normalized_entropy": ent,
        "gini": gini,
        "dead_layer_fraction": dead,
        "budget_violations": budget_viol,
    }


def run_one(mode: RoutingMode, seed: int, device: str) -> dict:
    torch.manual_seed(seed)
    model = RoutedTransformer(MCFG, mode).to(device)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=WD, betas=(0.9, 0.95))
    gen = torch.Generator().manual_seed(seed)  # data order fixed per seed
    valx, valy, valq = _make_val(device)

    best_q = float("inf"); best_eval = None; curve = []
    t0 = time.perf_counter()
    for step in range(TRAIN_STEPS):
        model.train()
        for pg in opt.param_groups:
            pg["lr"] = _lr_at(step)
        xb, yb = generate_batch(TASK, BATCH, gen, device="cpu")
        xb, yb = xb.to(device), yb.to(device)
        logits = model(xb, seq_seed=seed * 100000 + step)
        nonpad = yb.view(-1) != TASK.pad_token
        loss = F.cross_entropy(logits.view(-1, MCFG.vocab_size)[nonpad], yb.view(-1)[nonpad])
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, GRAD_CLIP)
        opt.step()
        if (step + 1) % EVAL_EVERY == 0 or step == TRAIN_STEPS - 1:
            ev = _evaluate(model, valx, valy, valq, device)
            curve.append({"step": step + 1, "query_ce": ev["query_ce"], "full_ce": ev["full_ce"]})
            if ev["query_ce"] < best_q:
                best_q = ev["query_ce"]; best_eval = ev
    train_s = time.perf_counter() - t0

    # systems metrics: eval-time latency + VRAM on one fixed batch
    model.eval()
    xb = valx[:256]
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize()
    lat0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(10):
            model(xb, seq_seed=None)
        if device == "cuda":
            torch.cuda.synchronize()
    e2e_ms = (time.perf_counter() - lat0) * 1000.0 / 10
    peak_vram = int(torch.cuda.max_memory_allocated()) if device == "cuda" else None

    active_blocks = MCFG.n_layer if mode == RoutingMode.DENSE else MCFG.budget_k
    has_ctrl = mode in (RoutingMode.LEARNED, RoutingMode.FROZEN)
    flops = active_inference_flops(MCFG, TASK.seq_len, active_blocks, has_ctrl)
    ctrl_flops = MCFG.n_layer * 2 * ((MCFG.d_model + 1) * 64 + 64) if has_ctrl else 0

    total_params = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in params)
    ctrl_params = sum(p.numel() for p in model.controller.parameters()) if model.controller else 0

    return {
        "mode": mode.value,
        "seed": seed,
        "device": device,
        "train_steps": TRAIN_STEPS,
        "train_seconds": round(train_s, 2),
        "best_query_ce": best_q,
        "final_eval": best_eval,
        "val_curve": curve,
        "active_inference_flops": flops,
        "controller_flops": ctrl_flops,
        "active_blocks": active_blocks,
        "e2e_latency_ms_per_256batch": round(e2e_ms, 4),
        "peak_vram_allocated_bytes": peak_vram,
        "total_params": total_params,
        "trainable_params": trainable,
        "controller_params": ctrl_params,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-routing-v1/raw_runs"))
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
            print(f"[{mode.value:12s} seed{seed}] best_query_ce={res['best_query_ce']:.4f} "
                  f"active={res['active_blocks']} flops={res['active_inference_flops']:.3e} "
                  f"t={res['train_seconds']}s")


if __name__ == "__main__":
    main()
