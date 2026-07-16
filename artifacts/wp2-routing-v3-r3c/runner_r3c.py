"""R3-C — end-to-end routing WITHOUT oracle leakage (P0 #3). The decisive test
of whether the routing-causality result survives once the three leaks are
removed:
  - capacity is FIXED before evaluation (not (vkind==HARD).sum());
  - the controller trains ONLY on task loss under a hard top-K budget
    (straight-through), with NO (direct_loss - sem_loss) distillation target and
    NO ground-truth in its signal;
  - metrics use the corrected symmetric NMI / average-rank AUROC.

If R3-C still routes HARD->semantic and beats random/frozen at the fixed budget,
the routing claim strengthens back toward autonomous. If it collapses, the
earlier result was genuinely dependent on value distillation (claim stays
narrowed). Either outcome is reported honestly.

Run: PYTHONPATH=. python -m experiments.wp2_routing_v2.src.runner_r3c --seeds 0 1 2
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


def _train_controller_e2e(g, seed, cap_frac, device, steps):
    for p in list(g.direct.parameters()) + list(g.semantic.parameters()):
        p.requires_grad_(False)
    opt = torch.optim.AdamW(g.controller.parameters(), lr=LR, weight_decay=0.01)
    gen = torch.Generator().manual_seed(seed + 11)
    K = int(round(cap_frac * BATCH))
    for _ in range(steps):
        g.train()
        tokens, _gt, canon, _kind = generate_batch(BATCH, gen, "train", 0.5, device)
        need = g.controller.need_score(tokens)
        hard = topk_mask(need, K)
        gate = hard.float() + (torch.sigmoid(need) - torch.sigmoid(need).detach())   # straight-through
        with torch.no_grad():
            sem, _ = g.semantic(tokens)
            direct = g.direct(tokens)
        gm = gate.view(-1, 1, 1)
        out = gm * sem + (1 - gm) * direct
        loss = _canon_loss_per_sample(out, canon).mean()   # TASK LOSS ONLY — no distillation target
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
    # frozen controller: reinit, no training
    tpr = learned[hard].float().mean().item() if hard.any() else 0.0
    tnr = (~learned[~hard]).float().mean().item() if (~hard).any() else 0.0
    return {
        "fixed_capacity_K": K, "n_hard": int(hard.sum().item()),
        "learned_loss": routed_loss(learned), "random_loss": routed_loss(rand),
        "route_balanced_acc": 0.5 * (tpr + tnr),
        "route_symmetric_nmi": symmetric_nmi(learned.long(), hard.long()),
        "route_auroc": auroc(need, hard.long()),
        "semantic_used": int(learned.sum().item()),
    }


def run_seed(seed, device, path_steps, ctrl_steps):
    g, _ = _train_paths(seed, device, path_steps)
    g = _train_controller_e2e(g, seed, FIXED_CAP_FRAC, device, ctrl_steps)
    gv = torch.Generator().manual_seed(999_999)
    vx, _vgt, vcanon, vkind = generate_batch(VAL, gv, "test", 0.5, device)
    return {"seed": seed, "eval": _eval(g, vx, vcanon, vkind, FIXED_CAP_FRAC, seed, device)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--path-steps", type=int, default=2000)
    ap.add_argument("--ctrl-steps", type=int, default=CTRL_STEPS)
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-routing-v3-r3c/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, device, args.path_steps, args.ctrl_steps)
        (args.out / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        e = r["eval"]
        print(f"[s{seed}] learned_loss={e['learned_loss']:.3f} random_loss={e['random_loss']:.3f} "
              f"bal_acc={e['route_balanced_acc']:.3f} nmi={e['route_symmetric_nmi']:.3f} "
              f"auroc={e['route_auroc']:.3f} K={e['fixed_capacity_K']} hard={e['n_hard']}")


if __name__ == "__main__":
    main()
