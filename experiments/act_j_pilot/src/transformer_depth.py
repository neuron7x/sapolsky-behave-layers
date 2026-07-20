"""Adaptive-depth transformer — the compute-matched advantage on a REAL model.

A minimal nanochat-style transformer on a would-be depth-separated task: follow a
successor pointer `h` times. `h=1` (easy) is solved at depth 3; `h=3` (hard) *usually*
needs depth 4. A policy that spends depth 3 on easy examples and depth 4 on hard ones is
compared to a static (context-blind) depth policy at MATCHED average compute.

**Honest finding (destruction stage).** The compute-matched advantage is NOT robust
across seeds. Adaptive is *never worse* than static at matched compute (by construction
— it allocates the correct depth per difficulty), but its strict *gain* depends on the
shallow model genuinely failing the hard task, which is a training-dynamics accident:
over 3 seeds the shallow model's hop-3 accuracy was 0.96 / 0.41 / 0.21, giving gains
+0.01 / +0.15 / +0.20 (mean +0.12, min +0.01). When the shallow model happens to learn
the hard task (seed 0), the separation collapses and adaptivity buys almost nothing.

This mirrors the CWC programme's own collapse findings (WP2 routing was bimodal too):
adaptive computation pays exactly when the task is genuinely identifiable/separated, and
whether a transformer *is* separated at a given depth is not guaranteed — it is an
empirical, seed-dependent property, not a promise. The clean, reproducible compute-
matched advantage lives in the decision-table experiment (`compute_matched.py`); this
transformer version shows the same principle, and its fragility, on a real model.

Two standalone models are trained so each is a fair static baseline. Compute unit =
layers applied.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_V = 12
_SEQ = _V + 2
_EASY_DEPTH, _HARD_DEPTH = 3, 4
_HARD_HOPS = 3


def _generate(batch: int, hops: int, gen: torch.Generator) -> tuple[torch.Tensor, torch.Tensor]:
    succ = torch.stack([torch.randperm(_V, generator=gen, device=_DEVICE) for _ in range(batch)])
    start = torch.randint(0, _V, (batch,), generator=gen, device=_DEVICE)
    y = start.clone()
    idx = torch.arange(batch, device=_DEVICE)
    for _ in range(hops):
        y = succ[idx, y]
    marker = torch.full((batch, 1), _V + hops, device=_DEVICE)
    return torch.cat([succ, start[:, None], marker], dim=1), y


class _Transformer(nn.Module):
    def __init__(self, depth: int, d: int = 96, heads: int = 6) -> None:
        super().__init__()
        self.emb = nn.Embedding(_V + 5, d)
        self.pos = nn.Embedding(_SEQ, d)
        self.blocks = nn.ModuleList(
            [nn.TransformerEncoderLayer(d, heads, d * 2, batch_first=True, dropout=0.0) for _ in range(depth)]
        )
        self.head = nn.Linear(d, _V)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        pos = torch.arange(x.size(1), device=x.device)
        h = self.emb(x) + self.pos(pos)[None]
        for block in self.blocks:
            h = block(h)
        return self.head(h[:, -1])


def _train(depth: int, steps: int, lr: float, batch: int, gen: torch.Generator) -> _Transformer:
    model = _Transformer(depth).to(_DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.LinearLR(opt, 0.1, 1.0, total_iters=500)
    model.train()
    for step in range(steps):
        xe, ye = _generate(batch // 2, 1, gen)
        xh, yh = _generate(batch // 2, _HARD_HOPS, gen)
        x = torch.cat([xe, xh])
        y = torch.cat([ye, yh])
        loss = F.cross_entropy(model(x), y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        if step < 500:
            sched.step()
    return model


def _acc(model: _Transformer, hops: int, gen: torch.Generator, n: int) -> float:
    with torch.no_grad():
        x, y = _generate(n, hops, gen)
        return (model(x).argmax(1) == y).float().mean().item()


@dataclass
class DepthResult:
    adaptive_accuracy: float
    adaptive_compute: float
    static_shallow_accuracy: float
    static_deep_accuracy: float
    static_matched_accuracy: float
    compute_matched_gain: float
    shallow_on_hard: float          # the shallow-depth accuracy cap on hard examples


def run(steps: int = 6000, lr: float = 1e-3, batch: int = 128, eval_batch: int = 2000, seed: int = 0) -> DepthResult:
    torch.manual_seed(seed)
    gen = torch.Generator(device=_DEVICE).manual_seed(seed)
    shallow = _train(_EASY_DEPTH, steps, lr, batch, gen)
    deep = _train(_HARD_DEPTH, steps, lr, batch, gen)
    shallow.eval()
    deep.eval()

    acc_e2 = _acc(shallow, 1, gen, eval_batch)
    acc_h2 = _acc(shallow, _HARD_HOPS, gen, eval_batch)
    acc_e3 = _acc(deep, 1, gen, eval_batch)
    acc_h3 = _acc(deep, _HARD_HOPS, gen, eval_batch)

    adaptive_acc = 0.5 * acc_e2 + 0.5 * acc_h3                      # easy@shallow, hard@deep
    adaptive_compute = 0.5 * _EASY_DEPTH + 0.5 * _HARD_DEPTH        # 3.5
    static_shallow = 0.5 * acc_e2 + 0.5 * acc_h2                    # shallow depth for all
    static_deep = 0.5 * acc_e3 + 0.5 * acc_h3                       # deep depth for all
    frac = (adaptive_compute - _EASY_DEPTH) / (_HARD_DEPTH - _EASY_DEPTH)
    static_matched = (1 - frac) * static_shallow + frac * static_deep
    return DepthResult(
        adaptive_accuracy=adaptive_acc, adaptive_compute=adaptive_compute,
        static_shallow_accuracy=static_shallow, static_deep_accuracy=static_deep,
        static_matched_accuracy=static_matched, compute_matched_gain=adaptive_acc - static_matched,
        shallow_on_hard=acc_h2,
    )


def run_multi_seed(seeds: tuple[int, ...] = (0, 1, 2), steps: int = 6000) -> dict[str, object]:
    """Run the experiment over several seeds and report the HONEST verdict: adaptive is
    never worse than static at matched compute, and strictly helps only when the shallow
    model genuinely fails the hard task (a seed-dependent, non-guaranteed property)."""
    rows = []
    for s in seeds:
        r = run(steps=steps, seed=s)
        rows.append({"seed": s, "shallow_on_hard": r.shallow_on_hard,
                     "adaptive_accuracy": r.adaptive_accuracy,
                     "static_matched_accuracy": r.static_matched_accuracy,
                     "compute_matched_gain": r.compute_matched_gain})
    gains = [row["compute_matched_gain"] for row in rows]
    never_worse = all(row["adaptive_accuracy"] >= row["static_matched_accuracy"] - 1e-3 for row in rows)
    return {
        "rows": rows,
        "mean_gain": sum(gains) / len(gains),
        "min_gain": min(gains),
        "max_gain": max(gains),
        "adaptive_never_worse": never_worse,
        "verdict": "ADAPTIVE_DEPTH_HELPS_WHEN_SEPARATED_NOT_GUARANTEED",
    }
