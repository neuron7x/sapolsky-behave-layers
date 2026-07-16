"""A3 — adaptive-routing causality on the mechanism-separable benchmark.

Per (config, seed, stage): train, eval loss/acc/per-family, route↔label
agreement, MI(R;T). For learned: causal interventions (force-correct,
force-incorrect, permute-route, module-swap). Provenance manifest per run.

Usage: PYTHONPATH=. python experiments/wp2_mechanism_v2/src/runner_mech.py \
    --seeds 0 1 2 3 4 5 6 7 --out artifacts/wp2-mechanism-v2/raw_runs
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from experiments.wp2_mechanism_v2.src.model_mech import MechConfig, MechModel, Mode
from experiments.wp2_mechanism_v2.src.provenance import run_manifest
from experiments.wp2_mechanism_v2.src.task_mech import MechTaskConfig, answer_mask, generate_batch

TC = MechTaskConfig()
MC = MechConfig()
STEPS = 1500
BATCH = 64
LR = 1e-3
VAL = 1024
CONFIGS = [Mode.DENSE, Mode.RANDOM, Mode.FROZEN, Mode.FIXED, Mode.ORACLE, Mode.LEARNED]


def _mi_norm(route: torch.Tensor, label: torch.Tensor) -> dict:
    # both binary; MI(R;T)/H(T)
    r = route.cpu(); t = label.cpu()
    n = r.numel()
    mi = 0.0
    for rv in (0, 1):
        for tv in (0, 1):
            p_rt = ((r == rv) & (t == tv)).float().mean().item()
            p_r = (r == rv).float().mean().item()
            p_t = (t == tv).float().mean().item()
            if p_rt > 0 and p_r > 0 and p_t > 0:
                mi += p_rt * math.log(p_rt / (p_r * p_t))
    ht = 0.0
    for tv in (0, 1):
        p = (t == tv).float().mean().item()
        if p > 0:
            ht -= p * math.log(p)
    return {"mi_nats": mi, "h_t_nats": ht, "i_norm": (mi / ht) if ht > 0 else 0.0}


def _permutation_pvalue(route, label, observed_inorm, iters=1000, seed=0):
    g = torch.Generator().manual_seed(seed)
    ge = 0
    for _ in range(iters):
        perm = label[torch.randperm(label.numel(), generator=g)]
        if _mi_norm(route, perm)["i_norm"] >= observed_inorm:
            ge += 1
    return (ge + 1) / (iters + 1)


@torch.no_grad()
def _eval(model, vx, vy, vl, vm, device):
    model.eval()
    ll = model(vx, task_label=vl, seq_seed=None).view(-1, MC.vocab_size)
    sel = vm.view(-1)
    pred = ll[sel].argmax(-1); tgt = vy.view(-1)[sel]
    ok = pred == tgt
    ce = F.cross_entropy(ll[sel], tgt).item()
    out = {"answer_ce": ce, "acc": ok.float().mean().item(),
           "acc_local": ok[vl == 0].float().mean().item(),
           "acc_far": ok[vl == 1].float().mean().item()}
    route = model._last_route
    if route is not None and (route >= 0).all():
        out["route_label_agreement"] = (route == vl).float().mean().item()
        out.update({f"mi_{k}": v for k, v in _mi_norm(route, vl).items()})
    return out


@torch.no_grad()
def _interventions(model, vx, vy, vl, vm, device):
    model.eval()
    sel = vm.view(-1); tgt = vy.view(-1)[sel]

    def ce_for(forced=None, swap=False):
        ll = model(vx, task_label=vl, forced_route=forced, swap_modules=swap).view(-1, MC.vocab_size)
        return F.cross_entropy(ll[sel], tgt).item()

    base = ce_for()
    correct = ce_for(forced=vl)                      # route == true label
    incorrect = ce_for(forced=1 - vl)                # inverted
    g = torch.Generator().manual_seed(0)
    perm = vl[torch.randperm(vl.numel(), generator=g)]
    permuted = ce_for(forced=perm)
    swapped = ce_for(swap=True)                       # swap E_A<->E_B, keep routes
    return {"ce_natural": base, "ce_force_correct": correct, "ce_force_incorrect": incorrect,
            "ce_route_permuted": permuted, "ce_module_swapped": swapped,
            "incorrect_over_correct_ratio": (incorrect / correct) if correct > 0 else None}


def run_one(mode, seed, stage_marker, device):
    torch.manual_seed(seed)
    model = MechModel(MC, mode).to(device)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=0.01)
    gen = torch.Generator().manual_seed(seed)
    gv = torch.Generator().manual_seed(999_999)
    vx, vy, vl = generate_batch(TC, VAL, gv, "cpu", has_marker=stage_marker)
    vx, vy, vl = vx.to(device), vy.to(device), vl.to(device)
    vm = answer_mask(TC, VAL, device)
    t0 = time.perf_counter()
    for s in range(STEPS):
        model.train()
        xb, yb, lb = generate_batch(TC, BATCH, gen, "cpu", has_marker=stage_marker)
        xb, yb, lb = xb.to(device), yb.to(device), lb.to(device)
        nonpad = yb.view(-1) != TC.pad_token
        loss = F.cross_entropy(model(xb, task_label=lb, seq_seed=s).view(-1, MC.vocab_size)[nonpad], yb.view(-1)[nonpad])
        opt.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step()
    ev = _eval(model, vx, vy, vl, vm, device)
    res = {"mode": mode.value, "seed": seed, "stage": "A_marker" if stage_marker else "B_inferred",
           "train_seconds": round(time.perf_counter() - t0, 2), "eval": ev,
           "total_params": sum(p.numel() for p in model.parameters()),
           "controller_params": sum(p.numel() for p in model.ctrl.parameters()) if model.ctrl else 0}
    if mode == Mode.LEARNED:
        res["interventions"] = _interventions(model, vx, vy, vl, vm, device)
        if "mi_i_norm" in ev:
            res["permutation_p"] = _permutation_pvalue(model._last_route, vl, ev["mi_i_norm"], iters=1000, seed=seed)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(8)))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-mechanism-v2/raw_runs"))
    ap.add_argument("--steps", type=int, default=None)
    args = ap.parse_args()
    global STEPS
    if args.steps:
        STEPS = args.steps
    device = "cuda" if torch.cuda.is_available() else "cpu"
    man = run_manifest(extra={"experiment": "wp2_mechanism_v2_A3", "steps": STEPS, "seeds": args.seeds})
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out.parent / "manifest.json").write_text(json.dumps(man, indent=2))
    for stage_marker in (True, False):
        stage = "A_marker" if stage_marker else "B_inferred"
        for mode in CONFIGS:
            d = args.out / stage / mode.value
            d.mkdir(parents=True, exist_ok=True)
            for seed in args.seeds:
                res = run_one(mode, seed, stage_marker, device)
                (d / f"seed{seed}.json").write_text(json.dumps(res, indent=2))
                ev = res["eval"]
                ag = ev.get("route_label_agreement", float("nan"))
                print(f"[{stage} {mode.value:8s} s{seed}] ce={ev['answer_ce']:.3f} acc={ev['acc']:.3f} "
                      f"(L={ev['acc_local']:.2f} F={ev['acc_far']:.2f}) route~T={ag:.3f}")


if __name__ == "__main__":
    main()
