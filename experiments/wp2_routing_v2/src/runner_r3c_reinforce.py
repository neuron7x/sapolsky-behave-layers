"""R3-C with REINFORCE credit-assignment (Routing v3 core, local). Tests H_opt vs
H_deep: does a policy-gradient controller recover the routing signal that the
straight-through R3-C could not, given the oracle gap is positive under budget?

Identical to runner_r3c.py EXCEPT the controller is trained by REINFORCE with a
mean-reward advantage baseline and an explicit per-use FLOP cost (the honest R-C
objective L = L_task + lambda*C_use). No privileged target, no label-derived
capacity, no distillation. Eval uses top-K at a fixed label-free budget, same as
the straight-through arm, for a fair paired comparison.

Run: PYTHONPATH=. python -m experiments.wp2_routing_v2.src.runner_r3c_reinforce --seeds 0 1 2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from experiments.common.metrics import auroc, symmetric_nmi
from experiments.wp2_routing_v2.src.contracts import TaskKind
from experiments.wp2_routing_v2.src.controller import topk_mask
from experiments.wp2_routing_v2.src.runner_final import _canon_loss_per_sample
from experiments.wp2_routing_v2.src.runner_oracle import BATCH, VAL, _train_paths
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch

CTRL_STEPS = 2000
LR = 1e-3
FIXED_CAP_FRAC = 0.5   # capacity chosen BEFORE evaluation, label-free
LAMBDA_USE = 0.0       # set per --lambda-use; tuned so induced fraction ~= 0.5


def _train_controller_reinforce(g, seed, device, steps, lam):
    for p in list(g.direct.parameters()) + list(g.semantic.parameters()):
        p.requires_grad_(False)
    opt = torch.optim.AdamW(g.controller.parameters(), lr=LR, weight_decay=0.01)
    gen = torch.Generator().manual_seed(seed + 11)
    pgen = torch.Generator(device="cpu").manual_seed(seed + 101)
    for _ in range(steps):
        g.train()
        tokens, _gt, canon, _kind = generate_batch(BATCH, gen, "train", 0.5, device)
        need = g.controller.need_score(tokens)
        p = torch.sigmoid(need)                                    # per-seq route prob
        act = (torch.rand(p.shape, generator=pgen).to(device) < p).float()  # a_i ~ Bern(p_i)
        with torch.no_grad():
            sem, _ = g.semantic(tokens)
            direct = g.direct(tokens)
            am = act.view(-1, 1, 1)
            out = am * sem + (1 - am) * direct
            taskloss = _canon_loss_per_sample(out, canon)          # per-sample [B]
            reward = -taskloss - lam * act                         # explicit FLOP cost
            adv = reward - reward.mean()                           # baseline
        logp = act * torch.log(p + 1e-8) + (1 - act) * torch.log(1 - p + 1e-8)
        loss = -(adv * logp).mean()                                # policy gradient
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(g.controller.parameters(), 1.0)
        opt.step()
    return g


@torch.no_grad()
def _eval(g, vx, vcanon, vkind, cap_frac, seed, device):
    g.eval()
    B = vx.shape[0]
    K = int(round(cap_frac * B))     # FIXED capacity, label-free
    need = g.controller.need_score(vx)
    learned = topk_mask(need, K)
    hard = vkind == int(TaskKind.HARD_SEMANTIC)

    def routed_loss(mask):
        out, _, _ = g(vx, capacity=int(mask.sum()), forced_mask=mask)
        return _canon_loss_per_sample(out, vcanon).mean().item()

    gg = torch.Generator(device="cpu").manual_seed(seed * 13 + B)
    rand = torch.zeros(B, dtype=torch.bool)
    rand[torch.randperm(B, generator=gg)[:K]] = True
    rand = rand.to(device)
    tpr = learned[hard].float().mean().item() if hard.any() else 0.0
    tnr = (~learned[~hard]).float().mean().item() if (~hard).any() else 0.0
    induced_frac = torch.sigmoid(need).mean().item()
    return {
        "fixed_capacity_K": K, "n_hard": int(hard.sum().item()),
        "learned_loss": routed_loss(learned), "random_loss": routed_loss(rand),
        "route_balanced_acc": 0.5 * (tpr + tnr),
        "route_symmetric_nmi": symmetric_nmi(learned.long(), hard.long()),
        "route_auroc": auroc(need, hard.long()),
        "semantic_used": int(learned.sum().item()),
        "induced_route_fraction": induced_frac,
    }


def run_seed(seed, device, path_steps, ctrl_steps, lam):
    g, _ = _train_paths(seed, device, path_steps)
    g = _train_controller_reinforce(g, seed, device, ctrl_steps, lam)
    gv = torch.Generator().manual_seed(999_999)
    vx, _vgt, vcanon, vkind = generate_batch(VAL, gv, "test", 0.5, device)
    return {"seed": seed, "lambda_use": lam,
            "eval": _eval(g, vx, vcanon, vkind, FIXED_CAP_FRAC, seed, device)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--path-steps", type=int, default=2000)
    ap.add_argument("--ctrl-steps", type=int, default=CTRL_STEPS)
    ap.add_argument("--lambda-use", type=float, default=0.05)
    ap.add_argument("--out", type=Path,
                    default=Path("artifacts/wp2-routing-v3-r3c-reinforce/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, device, args.path_steps, args.ctrl_steps, args.lambda_use)
        (args.out / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        e = r["eval"]
        print(f"[s{seed}] learned={e['learned_loss']:.3f} random={e['random_loss']:.3f} "
              f"bal_acc={e['route_balanced_acc']:.3f} nmi={e['route_symmetric_nmi']:.3f} "
              f"auroc={e['route_auroc']:.3f} frac={e['induced_route_fraction']:.2f} "
              f"lam={args.lambda_use}")


if __name__ == "__main__":
    main()
