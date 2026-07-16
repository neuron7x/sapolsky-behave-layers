"""Act F confirmatory — train each mode, evaluate, and run RCFR causal
interventions. Run:
PYTHONPATH=. python -m experiments.wp3_rcfr.src.runner --seeds 0 1 2 3 4 5 6 7
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F

from experiments.wp3_rcfr.src.rcfr_modules import Mode, OperatorModel
from experiments.wp3_rcfr.src.task_ops import N_ROLES, N_SYMBOLS, PERMS, generate_batch

STEPS = 2500
BATCH = 128
LR = 2e-3
VAL = 2048
MODES = [Mode.SHARED_NO_ROLE, Mode.STATIC_LORA, Mode.FIXED_ROLE, Mode.DISEL_GATED,
         Mode.SEPARATE_MODULES, Mode.RCFR]
CHANCE = 1.0 / N_SYMBOLS


def _acc(model, tokens, target, forced_role=None, swap=False):
    logits = model(tokens, forced_role=forced_role, swap_module=swap)
    return (logits.argmax(-1) == target).float().mean().item()


def _train(mode, seed, device, steps):
    torch.manual_seed(seed)
    m = OperatorModel(mode).to(device)
    opt = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad], lr=LR, weight_decay=0.01)
    gen = torch.Generator().manual_seed(seed)
    for _ in range(steps):
        m.train()
        tok, tgt, _ = generate_batch(BATCH, gen, "train", device)
        logits = m(tok)
        loss = F.cross_entropy(logits.reshape(-1, N_SYMBOLS), tgt.reshape(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    return m


def run_seed(seed, device, steps):
    perms = PERMS.to(device)
    gv = torch.Generator().manual_seed(999_999)
    vtok, vtgt, vroles = generate_batch(VAL, gv, "train", device)     # seen compositions
    gt = torch.Generator().manual_seed(888_888)
    ttok, ttgt, troles = generate_batch(VAL, gt, "test", device)       # unseen compositions
    res = {"seed": seed, "modes": {}}
    models = {}
    for mode in MODES:
        m = _train(mode, seed, device, steps)
        models[mode] = m
        res["modes"][mode.value] = {
            "acc_seen": _acc(m, vtok, vtgt),
            "acc_unseen": _acc(m, ttok, ttgt),
            "n_params": sum(p.numel() for p in m.parameters() if p.requires_grad),
        }
    # ---- RCFR causal interventions ----
    rcfr = models[Mode.RCFR]
    rcfr.eval()
    with torch.no_grad():
        acc_true = _acc(rcfr, vtok, vtgt)
        # role permutation: force a WRONG role (r+1 mod R)
        wrong = (vroles + 1) % N_ROLES
        acc_wrong = _acc(rcfr, vtok, vtgt, forced_role=wrong)
        # does output follow the WRONG role's function? (predictable functional change)
        logits_wrong = rcfr(vtok, forced_role=wrong)
        operands = vtok[:, 1:]
        # wrong_target[b,i] = perms[wrong[b]][operands[b,i]]
        wrong_target = torch.gather(perms[wrong], 1, operands)
        follows_wrong = (logits_wrong.argmax(-1) == wrong_target).float().mean().item()
        # module swap (corrupt delta)
        acc_swap = _acc(rcfr, vtok, vtgt, swap=True)
        # random role
        rand_role = torch.randint(0, N_ROLES, (VAL,), device=device)
        acc_random = _acc(rcfr, vtok, vtgt, forced_role=rand_role)
    # advantage removed by role permutation (vs chance floor)
    adv = acc_true - CHANCE
    removed_frac = (acc_true - acc_wrong) / adv if adv > 0 else 0.0
    res["rcfr_interventions"] = {
        "acc_true": acc_true, "acc_forced_wrong_role": acc_wrong,
        "follows_wrong_role_fn": follows_wrong, "acc_module_swapped": acc_swap,
        "acc_random_role": acc_random, "advantage_removed_by_role_permute": removed_frac,
        "chance": CHANCE,
    }
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(8)))
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp3-rcfr/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, device, args.steps)
        (args.out / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        m = r["modes"]
        iv = r["rcfr_interventions"]
        print(f"[s{seed}] rcfr={m['rcfr']['acc_seen']:.3f}/{m['rcfr']['acc_unseen']:.3f} "
              f"sep={m['separate_modules']['acc_seen']:.3f} disel={m['disel_gated']['acc_seen']:.3f} "
              f"noRole={m['shared_no_role']['acc_seen']:.3f} lora={m['static_lora']['acc_seen']:.3f} "
              f"| permute_removes={iv['advantage_removed_by_role_permute']:.2f} follows_wrong={iv['follows_wrong_role_fn']:.2f}")


if __name__ == "__main__":
    main()
