"""Compute-matched adaptive vs static — the Act-J shape on the COMPUTE axis.

The rest of the pilot measures value versus *information*. Act J is about value versus
*compute*: does an adaptive controller beat a static one at **equal FLOPs**? Here each
mechanism `a` carries a compute cost `K[a]`; an adaptive router `P(a|c)` is trained to
maximise value under a compute price `mu` (`E[U] - mu*E[cost]`), tracing a value-vs-compute
frontier. The static baselines spend the same average compute *context-blind*.

The theory predicts (constrained oracle gap): adaptive strictly dominates the static
frontier exactly when a binding budget forbids the dominant mechanism everywhere — and
ties it when one mechanism weakly dominates. This module measures that, with a trained
network, at matched compute.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


@dataclass
class ComputePoint:
    compute: float   # E[cost] actually spent (FLOP units)
    value: float     # E[U] achieved


class _Router(nn.Module):
    def __init__(self, n_contexts: int, n_actions: int, *, hidden: int = 64, embed: int = 16) -> None:
        super().__init__()
        self.emb = nn.Embedding(n_contexts, embed)
        self.net = nn.Sequential(nn.Linear(embed, hidden), nn.GELU(), nn.Linear(hidden, n_actions))

    def forward(self, ctx: torch.Tensor) -> torch.Tensor:
        return self.net(self.emb(ctx))


def adaptive_frontier(
    utility: list[list[float]], cost: list[float], prior: list[float],
    mus: list[float], *, steps: int = 4000, lr: float = 3e-3, seed: int = 0,
) -> list[ComputePoint]:
    """Train `P(a|c)` at each compute price `mu` and return (E[cost], E[U]) points."""
    n_c, n_a = len(utility), len(utility[0])
    U = torch.tensor(utility, dtype=torch.float32, device=_DEVICE)
    K = torch.tensor(cost, dtype=torch.float32, device=_DEVICE)
    p = torch.tensor(prior, dtype=torch.float32, device=_DEVICE)
    ctx = torch.arange(n_c, device=_DEVICE)
    out: list[ComputePoint] = []
    for mu in mus:
        torch.manual_seed(seed)
        model = _Router(n_c, n_a).to(_DEVICE)
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        model.train()
        for _step in range(steps):
            pa = F.softmax(model(ctx), dim=1)                     # [K, A]
            value = (p[:, None] * pa * U).sum()
            compute = (p[:, None] * pa * K[None, :]).sum()
            loss = -(value - mu * compute)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            pa = F.softmax(model(ctx), dim=1)
            value_v = float((p[:, None] * pa * U).sum())
            compute_v = float((p[:, None] * pa * K[None, :]).sum())
        out.append(ComputePoint(compute=compute_v, value=value_v))
    return out


def static_value_at_compute(
    utility: list[list[float]], cost: list[float], prior: list[float], target_compute: float,
) -> float:
    """Best CONTEXT-BLIND value at a given average compute.

    A context-blind policy is a fixed distribution `q(a)` over mechanisms (same for every
    context); its compute is `sum_a q(a) K[a]` and its value is `sum_c p_c sum_a q(a) U[c,a]`.
    Maximising a linear objective over the simplex under one linear (compute) constraint,
    the optimum mixes the two mechanisms whose (value, cost) bracket the target — a line in
    the value-compute plane between single-mechanism vertices.
    """
    n_c, n_a = len(utility), len(utility[0])
    mean_u = [sum(prior[c] * utility[c][a] for c in range(n_c)) for a in range(n_a)]
    verts = sorted(range(n_a), key=lambda a: cost[a])
    best = -1e18
    for i in range(n_a):
        for j in range(n_a):
            ci, cj = cost[verts[i]], cost[verts[j]]
            if ci <= target_compute <= cj and cj > ci:
                t = (target_compute - ci) / (cj - ci)
                v = (1 - t) * mean_u[verts[i]] + t * mean_u[verts[j]]
                best = max(best, v)
            elif ci == cj == target_compute:
                best = max(best, mean_u[verts[i]], mean_u[verts[j]])
    # also allow spending less than target on a single cheaper-or-equal mechanism
    for a in range(n_a):
        if cost[a] <= target_compute + 1e-9:
            best = max(best, mean_u[a])
    return best


def compute_matched_gap(
    utility: list[list[float]], cost: list[float], prior: list[float],
    mus: list[float], *, steps: int = 4000, seed: int = 0,
) -> list[dict[str, float]]:
    """For each trained adaptive point, the static value at the SAME compute, and the gap."""
    rows: list[dict[str, float]] = []
    for pt in adaptive_frontier(utility, cost, prior, mus, steps=steps, seed=seed):
        static_v = static_value_at_compute(utility, cost, prior, pt.compute)
        rows.append({"compute": pt.compute, "adaptive_value": pt.value,
                     "static_value": static_v, "compute_matched_gap": pt.value - static_v})
    return rows
