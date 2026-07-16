"""Plasticity oracle-gap gate (spec §11.4, Phase H) — THE decisive gate.

Pretrain on BASE (identity); then for each task family and each single-group
allocation, reset to the pretrained state, adapt ONLY that group under the
plasticity optimizer, and measure new-task accuracy + retained BASE accuracy.
The oracle picks the best group per task; if it beats every fixed allocation
the benchmark is identifiable and a learned governor may be trained. Else:
PLASTICITY_BENCHMARK_NOT_IDENTIFIABLE.

Run: PYTHONPATH=. python -m experiments.wp3_plasticity_v1.src.runner_oracle \
    --seeds 0 1 2 3 4
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import torch
import torch.nn.functional as F

from cwc.plasticity.contracts import AdaptationMode, PlasticityDecision
from cwc.plasticity.optimizer import PlasticityOptimizer
from cwc.plasticity.registry import ParameterGroupRegistry
from experiments.wp3_plasticity_v1.src.benchmark import TASKS, base_batch
from experiments.wp3_plasticity_v1.src.model import VOCAB, GroupedModel

PRETRAIN_STEPS = 1500
ADAPT_STEPS = 300
BATCH = 128
LR = 3e-3
RETENTION_ALPHA = 1.0

# allocations by group_type (spec §5.1); each is a candidate plasticity locus
ALLOCATIONS: dict[str, tuple[str, ...]] = {
    "attn": ("attention.qkv", "attention.output"),
    "mlp": ("mlp.up", "mlp.down"),
    "head": ("language_head",),
    "embed": ("token_embedding",),
}


def _acc(model, batch_fn, gen, device, n=1024):
    model.eval()
    with torch.no_grad():
        x, y = batch_fn(n, gen, device)
        return (model(x).argmax(-1) == y).float().mean().item()


def _decision_for(reg: ParameterGroupRegistry, open_types: tuple[str, ...]) -> PlasticityDecision:
    G = reg.n_groups()
    mask = torch.zeros(G, dtype=torch.bool)
    for i, s in enumerate(reg.specs):
        if s.group_type in open_types:
            mask[i] = True
    return PlasticityDecision(
        group_mask=mask, lr_multiplier=torch.ones(G), consolidation=torch.zeros(G),
        max_update_norm=torch.zeros(G), replay_fraction=0.0,
        mode=AdaptationMode.UPDATE_EXISTING, selected_cost=int(mask.sum()), budget=G)


def _pretrain(seed, device):
    torch.manual_seed(seed)
    m = GroupedModel().to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=LR, weight_decay=0.0)
    gen = torch.Generator().manual_seed(seed)
    for _ in range(PRETRAIN_STEPS):
        m.train()
        x, y = base_batch(BATCH, gen, device)
        loss = F.cross_entropy(m(x).reshape(-1, VOCAB), y.reshape(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    return m


def _adapt_and_eval(pretrained, reg, open_types, task_fn, seed, device):
    m = copy.deepcopy(pretrained)
    named = dict(m.named_parameters())
    reference = {n: p.detach().clone() for n, p in named.items()}
    base_before = _acc(m, base_batch, torch.Generator().manual_seed(7), device)
    dec = _decision_for(reg, open_types)
    popt = PlasticityOptimizer(torch.optim.AdamW(m.parameters(), lr=LR), reg, named)
    gen = torch.Generator().manual_seed(seed + 100)
    for _ in range(ADAPT_STEPS):
        m.train()
        x, y = task_fn(BATCH, gen, device)
        loss = F.cross_entropy(m(x).reshape(-1, VOCAB), y.reshape(-1))
        popt.zero_grad()
        loss.backward()
        popt.apply_and_step(dec, reference)
    new_acc = _acc(m, task_fn, torch.Generator().manual_seed(9), device)
    base_after = _acc(m, base_batch, torch.Generator().manual_seed(7), device)
    utility = new_acc - RETENTION_ALPHA * max(0.0, base_before - base_after)
    return {"new_acc": new_acc, "base_before": base_before, "base_after": base_after,
            "retention_drop": base_before - base_after, "utility": utility,
            "cost_params": sum(s.parameter_count for s in reg.specs if s.group_type in open_types)}


def run_seed(seed, device):
    pretrained = _pretrain(seed, device)
    reg = ParameterGroupRegistry.from_model(pretrained)
    per = {}   # task -> allocation -> metrics
    for task_name, task_fn in TASKS.items():
        per[task_name] = {alloc: _adapt_and_eval(pretrained, reg, ots, task_fn, seed, device)
                          for alloc, ots in ALLOCATIONS.items()}
    return {"seed": seed, "registry_checksum": reg.checksum(), "n_groups": reg.n_groups(),
            "base_pretrain_acc": _acc(pretrained, base_batch, torch.Generator().manual_seed(7), device),
            "tasks": per}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp3-plasticity-v1/oracle-gap/raw_runs"))
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        r = run_seed(seed, device)
        (args.out / f"seed{seed}.json").write_text(json.dumps(r, indent=2))
        line = f"[s{seed}] base={r['base_pretrain_acc']:.2f} "
        for t, allocs in r["tasks"].items():
            best = max(allocs, key=lambda a: allocs[a]["utility"])
            line += f"| {t}: best={best}(" + " ".join(f"{a}={allocs[a]['new_acc']:.2f}" for a in allocs) + ") "
        print(line)


if __name__ == "__main__":
    main()
