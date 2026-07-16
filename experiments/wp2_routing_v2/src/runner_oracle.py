"""§9 oracle-gap gate + §10 isolation gates. Trains the two paths, then
evaluates non-learned modes and emits the identifiability verdict.

Run: PYTHONPATH=. python -m experiments.wp2_routing_v2.src.runner_oracle \
    --seeds 0 1 2 3 4 --capacity 32 --out artifacts/wp2-routing-v2/oracle-gap
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F

from experiments.wp2_routing_v2.src.contracts import TaskKind
from experiments.wp2_routing_v2.src.controller import topk_mask
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch
from experiments.wp2_routing_v2.src.typed_graph import TypedCognitiveGraph

BATCH = 64
STEPS = 2000
LR = 1e-3
VAL = 1024


def _train_paths(seed, device, steps):
    torch.manual_seed(seed)
    g = TypedCognitiveGraph().to(device)
    # train only path params (controller is not used by non-learned modes)
    params = list(g.direct.parameters()) + list(g.semantic.parameters())
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=0.01)
    gen = torch.Generator().manual_seed(seed)
    for _ in range(steps):
        g.train()
        tokens, gt, canon, _kind = generate_batch(BATCH, gen, "train", 0.5, device)
        ls, lr_, lo, lp, _ = g.semantic.parser.logits(tokens)
        parser_loss = (F.cross_entropy(ls, gt.subject) + F.cross_entropy(lr_, gt.relation)
                       + F.cross_entropy(lo, gt.object) + F.cross_entropy(lp, gt.polarity))
        rend = g.semantic.renderer(gt)                     # teacher-forced on gt state
        rend_loss = F.cross_entropy(rend.reshape(-1, rend.shape[-1]), canon.reshape(-1))
        direct = g.direct(tokens)
        direct_loss = F.cross_entropy(direct.reshape(-1, direct.shape[-1]), canon.reshape(-1))
        loss = parser_loss + rend_loss + direct_loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
    return g, gen


@torch.no_grad()
def _mode_mask(mode, need, kind, capacity, seed):
    B = kind.shape[0]
    if mode == "DENSE_SEMANTIC":
        return torch.ones(B, dtype=torch.bool, device=kind.device)
    if mode == "DIRECT_ONLY":
        return torch.zeros(B, dtype=torch.bool, device=kind.device)
    if mode == "ORACLE":
        return kind == int(TaskKind.HARD_SEMANTIC)
    if mode == "RANDOM":
        gg = torch.Generator(device="cpu").manual_seed(seed * 13 + B)
        idx = torch.randperm(B, generator=gg)[:capacity]
        m = torch.zeros(B, dtype=torch.bool)
        m[idx] = True
        return m.to(kind.device)
    if mode == "FROZEN":
        return topk_mask(need, capacity)
    raise ValueError(mode)


@torch.no_grad()
def _eval_mode(g, mode, vx, vgt, vcanon, vkind, capacity, seed, device):
    g.eval()
    need = g.controller.need_score(vx)
    mask = _mode_mask(mode, need, vkind, capacity, seed)
    out, _, _trace = g(vx, capacity=capacity, forced_mask=mask)
    pred = out.argmax(-1)                                   # [B,L_OUT]
    exact = (pred == vcanon).all(dim=1).float()
    ce = F.cross_entropy(out.reshape(-1, out.shape[-1]), vcanon.reshape(-1)).item()
    hard = vkind == int(TaskKind.HARD_SEMANTIC)
    easy = ~hard
    return {"canonical_ce": ce, "exact_match": exact.mean().item(),
            "hard_exact": exact[hard].mean().item() if hard.any() else None,
            "easy_exact": exact[easy].mean().item() if easy.any() else None,
            "budget_violations": int((mask.sum() > capacity).item()),
            "semantic_used": int(mask.sum().item())}


@torch.no_grad()
def _isolation(g, vx, vgt, vcanon, vkind, device):
    g.eval()
    ls, lr_, lo, lp, _ = g.semantic.parser.logits(vx)
    subj = (ls.argmax(-1) == vgt.subject).float().mean().item()
    rel = (lr_.argmax(-1) == vgt.relation).float().mean().item()
    obj = (lo.argmax(-1) == vgt.object).float().mean().item()
    pol = (lp.argmax(-1) == vgt.polarity).float().mean().item()
    tup = ((ls.argmax(-1) == vgt.subject) & (lr_.argmax(-1) == vgt.relation)
           & (lo.argmax(-1) == vgt.object) & (lp.argmax(-1) == vgt.polarity)).float().mean().item()
    rend = g.semantic.renderer(vgt)                        # gt state -> canonical
    rend_exact = (rend.argmax(-1) == vcanon).all(dim=1).float().mean().item()
    direct = g.direct(vx).argmax(-1)
    dexact = (direct == vcanon).all(dim=1).float()
    hard = vkind == int(TaskKind.HARD_SEMANTIC)
    return {"parser_subject": subj, "parser_relation": rel, "parser_object": obj,
            "parser_polarity": pol, "parser_tuple": tup, "renderer_exact": rend_exact,
            "direct_easy_exact": dexact[~hard].mean().item(),
            "direct_hard_exact": dexact[hard].mean().item()}


def run_seed(seed, capacity, device, steps):
    g, _ = _train_paths(seed, device, steps)
    gv = torch.Generator().manual_seed(999_999)
    vx, vgt, vcanon, vkind = generate_batch(VAL, gv, "test", 0.5, device)
    eval_cap = VAL * capacity // BATCH   # scale the 50% capacity to the eval set
    modes = ["DENSE_SEMANTIC", "DIRECT_ONLY", "ORACLE", "RANDOM", "FROZEN"]
    return {"seed": seed, "capacity": eval_cap,
           "modes": {m: _eval_mode(g, m, vx, vgt, vcanon, vkind, eval_cap, seed, device) for m in modes},
           "isolation": _isolation(g, vx, vgt, vcanon, vkind, device)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--capacity", type=int, default=32)
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-routing-v2/oracle-gap"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    (args.out / "raw_runs").mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, args.capacity, device, args.steps)
        (args.out / "raw_runs" / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        m = r["modes"]
        iso = r["isolation"]
        print(f"[s{seed}] ORACLE ce={m['ORACLE']['canonical_ce']:.3f} exact={m['ORACLE']['exact_match']:.3f} "
              f"(H={m['ORACLE']['hard_exact']:.2f} E={m['ORACLE']['easy_exact']:.2f}) | "
              f"DIRECT exact={m['DIRECT_ONLY']['exact_match']:.3f} | parser_tuple={iso['parser_tuple']:.3f} "
              f"direct_H={iso['direct_hard_exact']:.2f}")


if __name__ == "__main__":
    main()
