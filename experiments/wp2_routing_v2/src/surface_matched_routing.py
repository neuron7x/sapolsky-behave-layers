"""Surface-matched end-to-end routing (Routing v3, fully clean, local). Closes the
surface caveat of runner_r3c_reinforce: the benchmark (surface_matched_task) has
identical length/first-token/histogram for NEAR and FAR (leakage_probe ~0.5), so a
controller that still routes correctly MUST use STRUCTURE, not surface.

Mechanisms are EXACT operators (WP4 methodology -> no module-learning rabbit hole),
isolating the ALLOCATION decision:
  - LocalPath(w): finds the duplicate ONLY if its two occurrences fall in one
    window of width w (NEAR-solvable); otherwise abstains (uniform) -> high loss on FAR.
  - GlobalPath: full scan; always finds the duplicate -> low loss on both, but is
    the "expensive" path that a budget rations.
Controller is trained end-to-end by REINFORCE with an explicit per-use cost
(L = L_task + lambda*C_use), NO task/mechanism label, NO privileged target, NO
label-derived capacity. Eval routes top-K at a fixed label-free budget.

Run: PYTHONPATH=. python -m experiments.wp2_routing_v2.src.surface_matched_routing --seeds 0 1 2 3 4 5 6 7
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.common.metrics import auroc, symmetric_nmi
from experiments.wp2_routing_v2.src.controller import topk_mask
from experiments.wp2_routing_v2.src.surface_matched_task import (
    LOCAL_W,
    SEQ_LEN,
    VOCAB,
    generate_batch,
)

BATCH = 64
VAL = 1024
CTRL_STEPS = 2000
LR = 1e-3
FIXED_CAP_FRAC = 0.5


def local_logits(tokens: torch.Tensor, w: int) -> torch.Tensor:
    """EXACT local mechanism: a value is 'found' iff it repeats within a window of
    width w. Returns [B, VOCAB] logits: sharp on a found duplicate, else uniform."""
    B, L = tokens.shape
    out = torch.full((B, VOCAB), 0.0, device=tokens.device)
    found = torch.zeros(B, dtype=torch.bool, device=tokens.device)
    val = torch.zeros(B, dtype=torch.long, device=tokens.device)
    for i in range(L):
        for j in range(i + 1, min(i + w + 1, L)):     # only within local window w
            same = (tokens[:, i] == tokens[:, j]) & ~found
            val = torch.where(same, tokens[:, i], val)
            found = found | same
    sharp = F.one_hot(val, VOCAB).float() * 10.0
    return torch.where(found.view(-1, 1), sharp, out)   # uniform (zeros) when not found


def global_logits(tokens: torch.Tensor) -> torch.Tensor:
    """EXACT global mechanism: full scan, always finds the unique duplicate."""
    B, L = tokens.shape
    val = torch.zeros(B, dtype=torch.long, device=tokens.device)
    found = torch.zeros(B, dtype=torch.bool, device=tokens.device)
    for i in range(L):
        for j in range(i + 1, L):
            same = (tokens[:, i] == tokens[:, j]) & ~found
            val = torch.where(same, tokens[:, i], val)
            found = found | same
    return F.one_hot(val, VOCAB).float() * 10.0


class NeedNet(nn.Module):
    """CHEAP controller: embedding + positional + mean-pool + MLP. Cost << global
    mechanism. Cannot represent pairwise duplicate-distance (pooling destroys it)."""

    def __init__(self, d: int = 32):
        super().__init__()
        self.emb = nn.Embedding(VOCAB, d)
        self.pos = nn.Parameter(torch.zeros(SEQ_LEN, d))
        self.net = nn.Sequential(nn.Linear(d, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        x = self.emb(tokens) + self.pos.unsqueeze(0)
        return self.net(x.mean(dim=1)).squeeze(-1)      # [B] need score


class NeedNetAttn(nn.Module):
    """POWERFUL controller: one self-attention layer (O(L^2), can in principle
    detect duplicate pairs and their distance). Pre-empts the 'controller too weak'
    rebuttal: if THIS also routes at chance, the structural property is genuinely
    inaccessible below the cost of the global mechanism itself."""

    def __init__(self, d: int = 32):
        super().__init__()
        self.emb = nn.Embedding(VOCAB, d)
        self.pos = nn.Parameter(torch.zeros(SEQ_LEN, d))
        self.attn = nn.MultiheadAttention(d, num_heads=4, batch_first=True)
        self.net = nn.Sequential(nn.Linear(d, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        x = self.emb(tokens) + self.pos.unsqueeze(0)
        a, _ = self.attn(x, x, x)
        return self.net(a.mean(dim=1)).squeeze(-1)


def _make_controller(kind: str, device):
    return (NeedNetAttn() if kind == "attn" else NeedNet()).to(device)


def _task_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return F.cross_entropy(logits, target, reduction="none")   # [B]


def train_controller(seed, device, steps, lam, w, kind="cheap"):
    torch.manual_seed(seed)
    ctrl = _make_controller(kind, device)
    opt = torch.optim.AdamW(ctrl.parameters(), lr=LR, weight_decay=0.01)
    gen = torch.Generator().manual_seed(seed + 7)
    pgen = torch.Generator(device="cpu").manual_seed(seed + 101)
    for _ in range(steps):
        tokens, target, _far = generate_batch(BATCH, gen, device)
        need = ctrl(tokens)
        p = torch.sigmoid(need)
        act = (torch.rand(p.shape, generator=pgen).to(device) < p).float()
        with torch.no_grad():
            loc = local_logits(tokens, w)
            glo = global_logits(tokens)
            am = act.view(-1, 1)
            routed = am * glo + (1 - am) * loc         # a=1 -> global (expensive)
            taskloss = _task_loss(routed, target)
            reward = -taskloss - lam * act             # explicit per-use cost
            adv = reward - reward.mean()
        logp = act * torch.log(p + 1e-8) + (1 - act) * torch.log(1 - p + 1e-8)
        loss = -(adv * logp).mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(ctrl.parameters(), 1.0)
        opt.step()
    return ctrl


@torch.no_grad()
def evaluate(ctrl, seed, device, cap_frac, w):
    gv = torch.Generator().manual_seed(999_983)
    tokens, target, far = generate_batch(VAL, gv, device)
    B = tokens.shape[0]
    K = int(round(cap_frac * B))
    need = ctrl(tokens)
    learned = topk_mask(need, K)                        # route K to global, label-free

    loc = local_logits(tokens, w)
    glo = global_logits(tokens)

    def routed_loss(mask):
        m = mask.view(-1, 1).float()
        routed = m * glo + (1 - m) * loc
        return _task_loss(routed, target).mean().item()

    gg = torch.Generator(device="cpu").manual_seed(seed * 17 + B)
    rand = torch.zeros(B, dtype=torch.bool)
    rand[torch.randperm(B, generator=gg)[:K]] = True
    rand = rand.to(device)

    tpr = learned[far].float().mean().item() if far.any() else 0.0
    tnr = (~learned[~far]).float().mean().item() if (~far).any() else 0.0
    return {
        "fixed_capacity_K": K, "n_far": int(far.sum().item()),
        "learned_loss": routed_loss(learned),
        "random_loss": routed_loss(rand),
        "all_global_loss": routed_loss(torch.ones(B, dtype=torch.bool, device=device)),
        "all_local_loss": routed_loss(torch.zeros(B, dtype=torch.bool, device=device)),
        "route_balanced_acc": 0.5 * (tpr + tnr),
        "route_symmetric_nmi": symmetric_nmi(learned.long(), far.long()),
        "route_auroc": auroc(need, far.long()),
        "induced_route_fraction": torch.sigmoid(need).mean().item(),
    }


def supervised_probe(seed, device, steps, w, kind):
    """Representational-ceiling control: train the controller DIRECTLY on the far
    label (cross-entropy). Separates 'structure is inaccessible to this controller'
    (probe AUROC ~= 0.5) from 'RL credit-assignment failed' (probe AUROC high)."""
    torch.manual_seed(seed)
    ctrl = _make_controller(kind, device)
    opt = torch.optim.AdamW(ctrl.parameters(), lr=LR, weight_decay=0.01)
    gen = torch.Generator().manual_seed(seed + 7)
    for _ in range(steps):
        tokens, _target, far = generate_batch(BATCH, gen, device)
        need = ctrl(tokens)
        loss = F.binary_cross_entropy_with_logits(need, far.float())
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(ctrl.parameters(), 1.0)
        opt.step()
    gv = torch.Generator().manual_seed(999_983)
    tokens, _t, far = generate_batch(VAL, gv, device)
    with torch.no_grad():
        need = ctrl(tokens)
    return {"seed": seed, "controller": kind, "mode": "supervised_probe",
            "probe_auroc": auroc(need, far.long()),
            "probe_acc": ((need > 0) == far).float().mean().item()}


def run_seed(seed, device, steps, lam, w, kind="cheap"):
    ctrl = train_controller(seed, device, steps, lam, w, kind)
    return {"seed": seed, "lambda_use": lam, "local_w": w, "controller": kind,
            "eval": evaluate(ctrl, seed, device, FIXED_CAP_FRAC, w)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--ctrl-steps", type=int, default=CTRL_STEPS)
    ap.add_argument("--lambda-use", type=float, default=1.0)
    ap.add_argument("--local-w", type=int, default=LOCAL_W)
    ap.add_argument("--controller", choices=["cheap", "attn"], default="cheap")
    ap.add_argument("--mode", choices=["reinforce", "supervised"], default="reinforce")
    ap.add_argument("--out", type=Path,
                    default=Path("artifacts/wp2-routing-v3-surface-matched/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        if args.mode == "supervised":
            r = supervised_probe(seed, device, args.ctrl_steps, args.local_w, args.controller)
            (args.out / f"seed{seed}_{args.controller}_probe.json").write_text(json.dumps(r, indent=2))
            print(f"[s{seed}] supervised probe ({args.controller}): "
                  f"auroc={r['probe_auroc']:.3f} acc={r['probe_acc']:.3f}")
            continue
        r = run_seed(seed, device, args.ctrl_steps, args.lambda_use, args.local_w,
                     args.controller)
        (args.out / f"seed{seed}_{args.controller}.json").write_text(json.dumps(r, indent=2))
        e = r["eval"]
        print(f"[s{seed}] learned={e['learned_loss']:.3f} random={e['random_loss']:.3f} "
              f"allG={e['all_global_loss']:.3f} allL={e['all_local_loss']:.3f} "
              f"bal={e['route_balanced_acc']:.3f} auroc={e['route_auroc']:.3f} "
              f"frac={e['induced_route_fraction']:.2f}")


if __name__ == "__main__":
    main()
