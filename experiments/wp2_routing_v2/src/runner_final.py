"""§11-13 — learned controller, routing causality, lesions. Trains the two
paths, FREEZES them, then trains only the controller on routed task loss under
a hard capacity (straight-through top-K). Reports causality metrics and the
aphasia-analogue lesions.

Run: PYTHONPATH=. python -m experiments.wp2_routing_v2.src.runner_final \
    --seeds 0 1 2 3 4 5 6 7 --capacity 32 --out artifacts/wp2-routing-v2/final
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import torch
import torch.nn.functional as F

from experiments.wp2_routing_v2.src.contracts import TaskKind
from experiments.wp2_routing_v2.src.controller import topk_mask
from experiments.wp2_routing_v2.src.runner_oracle import BATCH, VAL, _train_paths
from experiments.wp2_routing_v2.src.task_semantic_route import (
    deterministic_output_parser,
    generate_batch,
)
from experiments.wp2_routing_v2.src.typed_graph import TypedCognitiveGraph

CTRL_STEPS = 1500
LR = 1e-3


def _canon_loss_per_sample(out, canon):
    B, L, V = out.shape
    ce = F.cross_entropy(out.reshape(-1, V), canon.reshape(-1), reduction="none").reshape(B, L)
    return ce.mean(dim=1)  # [B]


def _train_controller(g: TypedCognitiveGraph, seed, capacity, device, steps):
    """Unsupervised w.r.t. task labels: the controller learns a value function
    for routing — need_score regresses toward the per-sample loss reduction the
    semantic path buys, (direct_loss - sem_loss). Top-K by need then spends the
    scarce semantic budget on the highest-benefit samples, minimizing total
    task loss under the hard capacity. Uses only path losses, never task_kind.
    """
    for p in list(g.direct.parameters()) + list(g.semantic.parameters()):
        p.requires_grad_(False)
    opt = torch.optim.AdamW(g.controller.parameters(), lr=LR, weight_decay=0.01)
    gen = torch.Generator().manual_seed(seed + 7)
    for _ in range(steps):
        g.train()
        tokens, _gt, canon, _kind = generate_batch(BATCH, gen, "train", 0.5, device)
        with torch.no_grad():
            sem, _ = g.semantic(tokens)
            direct = g.direct(tokens)
            benefit = (_canon_loss_per_sample(direct, canon)
                       - _canon_loss_per_sample(sem, canon))   # high for HARD
        need = g.controller.need_score(tokens)
        loss = F.mse_loss(need, benefit)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(g.controller.parameters(), 1.0)
        opt.step()
    return g


def _nmi(r, t):
    r = r.long()
    t = t.long()
    mi = 0.0
    for rv in (0, 1):
        for tv in (0, 1):
            p_rt = ((r == rv) & (t == tv)).float().mean().item()
            p_r = (r == rv).float().mean().item()
            p_t = (t == tv).float().mean().item()
            if p_rt > 0 and p_r > 0 and p_t > 0:
                mi += p_rt * math.log(p_rt / (p_r * p_t))
    ht = -sum((t == tv).float().mean().item() * math.log(max((t == tv).float().mean().item(), 1e-12)) for tv in (0, 1))
    return (mi / ht) if ht > 0 else 0.0


def _auroc(score, label):
    s = score.cpu()
    y = label.cpu().long()
    pos = s[y == 1]
    neg = s[y == 0]
    if pos.numel() == 0 or neg.numel() == 0:
        return float("nan")
    # rank-based AUROC
    order = torch.argsort(s)
    ranks = torch.zeros_like(s)
    ranks[order] = torch.arange(1, s.numel() + 1, dtype=s.dtype)
    auc = (ranks[y == 1].sum() - pos.numel() * (pos.numel() + 1) / 2) / (pos.numel() * neg.numel())
    return float(auc)


def _balanced_acc(pred_sem, hard):
    tpr = pred_sem[hard].float().mean().item() if hard.any() else 0.0
    tnr = (~pred_sem[~hard]).float().mean().item() if (~hard).any() else 0.0
    return 0.5 * (tpr + tnr)


@torch.no_grad()
def _eval_routed(g, mask, vx, vcanon):
    out, _, _ = g(vx, capacity=int(mask.sum()), forced_mask=mask)
    return _canon_loss_per_sample(out, vcanon).mean().item(), out


@torch.no_grad()
def _causality(g, capacity, vx, vgt, vcanon, vkind, seed, device):
    g.eval()
    need = g.controller.need_score(vx)
    learned_mask = topk_mask(need, capacity)
    hard = vkind == int(TaskKind.HARD_SEMANTIC)
    learned_loss, _ = _eval_routed(g, learned_mask, vx, vcanon)
    # controls
    gg = torch.Generator(device="cpu").manual_seed(seed * 13 + vkind.shape[0])
    rand_mask = torch.zeros(vkind.shape[0], dtype=torch.bool)
    rand_mask[torch.randperm(vkind.shape[0], generator=gg)[:capacity]] = True
    rand_mask = rand_mask.to(device)
    random_loss, _ = _eval_routed(g, rand_mask, vx, vcanon)
    # shuffled learned: same count, permuted decisions
    perm = torch.randperm(vkind.shape[0], generator=gg).to(device)
    shuffled_mask = learned_mask[perm]
    shuffled_loss, _ = _eval_routed(g, shuffled_mask, vx, vcanon)
    # forced correct (oracle) / forced wrong
    correct_loss, _ = _eval_routed(g, hard, vx, vcanon)
    wrong_loss, _ = _eval_routed(g, ~hard, vx, vcanon)
    return {
        "learned_loss": learned_loss, "random_loss": random_loss, "shuffled_loss": shuffled_loss,
        "forced_correct_loss": correct_loss, "forced_wrong_loss": wrong_loss,
        "route_balanced_acc": _balanced_acc(learned_mask, hard),
        "route_nmi": _nmi(learned_mask, hard),
        "route_auroc": _auroc(need, hard.long()),
        "cre": (wrong_loss / correct_loss) if correct_loss > 0 else None,
        "shuffling_loss_ratio": (shuffled_loss / learned_loss) if learned_loss > 0 else None,
        "budget_violation": int((learned_mask.sum() > capacity).item()),
        "semantic_used": int(learned_mask.sum().item()),
    }


@torch.no_grad()
def _lesions(g, vx, vgt, vcanon, vkind, device):
    from experiments.wp2_routing_v2.src.typed_graph import LESIONS
    g.eval()
    all_sem = torch.ones(vkind.shape[0], dtype=torch.bool, device=device)
    out_intact, _, _ = g(vx, capacity=vkind.shape[0], forced_mask=all_sem, lesion="none")
    intact_exact = (out_intact.argmax(-1) == vcanon).all(1).float().mean().item()
    res = {}
    for les in LESIONS:
        out, _state, _ = g(vx, capacity=vkind.shape[0], forced_mask=all_sem, lesion=les)
        pred = out.argmax(-1)
        exact = (pred == vcanon).all(1).float().mean().item()
        # semantic feedback: parse output back, compare tuple
        rec = deterministic_output_parser(pred)
        tuple_ok = ((rec.subject == vgt.subject) & (rec.relation == vgt.relation)
                    & (rec.object == vgt.object) & (rec.polarity == vgt.polarity)).float().mean().item()
        sv = (pred[:, 0] >= 10) & (pred[:, 0] < 26) & (pred[:, 1] >= 30) & (pred[:, 1] < 38)
        syntax_valid = sv.float().mean().item()
        res[les] = {"canonical_exact": exact, "tuple_correct": tuple_ok, "syntax_valid": syntax_valid,
                    "fnr_syntax_valid_wrong_tuple": (syntax_valid - tuple_ok) if tuple_ok < 1 else 0.0}
    res["_intact_exact"] = intact_exact
    return res


def run_seed(seed, capacity, device, path_steps, ctrl_steps):
    g, _ = _train_paths(seed, device, path_steps)
    g = _train_controller(g, seed, capacity, device, ctrl_steps)
    gv = torch.Generator().manual_seed(999_999)
    vx, vgt, vcanon, vkind = generate_batch(VAL, gv, "test", 0.5, device)
    eval_cap = VAL * capacity // BATCH   # scale the 50% capacity to the eval set
    caus = _causality(g, eval_cap, vx, vgt, vcanon, vkind, seed, device)
    les = _lesions(g, vx, vgt, vcanon, vkind, device)
    return {"seed": seed, "capacity": capacity, "causality": caus, "lesions": les}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(8)))
    ap.add_argument("--capacity", type=int, default=32)
    ap.add_argument("--path-steps", type=int, default=2000)
    ap.add_argument("--ctrl-steps", type=int, default=CTRL_STEPS)
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-routing-v2/final"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    (args.out / "raw_runs").mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, args.capacity, device, args.path_steps, args.ctrl_steps)
        (args.out / "raw_runs" / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        c = r["causality"]
        print(f"[s{seed}] learned={c['learned_loss']:.3f} random={c['random_loss']:.3f} "
              f"shuffled={c['shuffled_loss']:.3f} bal_acc={c['route_balanced_acc']:.3f} "
              f"nmi={c['route_nmi']:.3f} auroc={c['route_auroc']:.3f} cre={c['cre']:.1f}")


if __name__ == "__main__":
    main()
