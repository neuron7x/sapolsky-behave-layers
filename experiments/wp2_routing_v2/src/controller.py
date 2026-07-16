"""Hard-capacity routing controller (Act §7). One need score per sequence;
exactly K sequences enter the semantic path via top-K. No soft FLOP penalty,
no post-hoc budget correction."""
from __future__ import annotations

import torch
import torch.nn as nn

from experiments.wp2_routing_v2.src.typed_modules import D_MODEL, _Embed, _rms


def topk_mask(need_score: torch.Tensor, k: int) -> torch.Tensor:
    """Bool [B] with exactly k True at the highest need scores."""
    mask = torch.zeros_like(need_score, dtype=torch.bool)
    if k <= 0:
        return mask
    idx = need_score.topk(min(k, need_score.numel())).indices
    mask[idx] = True
    return mask


class NeedController(nn.Module):
    """Produces one scalar "need for the expensive path" per sequence. Deliberately
    CHEAP (embed -> mean-pool -> small MLP): if a controller this light can predict the
    route, routing is worth it; if it cannot (as on the surface-matched task), the route
    decision costs as much as the computation (the route-decision-cost result). The
    controller only emits a *score*; the hard top-K budget is applied separately, so the
    budget is an external constraint the controller cannot relax."""

    def __init__(self):
        super().__init__()
        self.embed = _Embed()
        self.net = nn.Sequential(nn.Linear(D_MODEL, 64), nn.ReLU(), nn.Linear(64, 1))

    def need_score(self, tokens: torch.Tensor) -> torch.Tensor:
        """Scalar need score per sequence `[B]`; higher = more likely to need the
        semantic path. Ranking, not calibration, is what matters (top-K consumes it)."""
        x = self.embed(tokens)
        pooled = _rms(x).mean(dim=1)
        return self.net(pooled).squeeze(-1)   # [B]

    def route_logits(self, need: torch.Tensor) -> torch.Tensor:
        """Lift the scalar need into 2-way logits `[B, 2] = [direct, semantic]` as
        `[-need, +need]`, purely so the routing decision can be scored with the standard
        NMI/AUROC metrics against the binary task label. It encodes no extra information
        beyond `need` — it is a view, not a second head."""
        return torch.stack([-need, need], dim=1)
