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
    def __init__(self):
        super().__init__()
        self.embed = _Embed()
        self.net = nn.Sequential(nn.Linear(D_MODEL, 64), nn.ReLU(), nn.Linear(64, 1))

    def need_score(self, tokens: torch.Tensor) -> torch.Tensor:
        x = self.embed(tokens)
        pooled = _rms(x).mean(dim=1)
        return self.net(pooled).squeeze(-1)   # [B]

    def route_logits(self, need: torch.Tensor) -> torch.Tensor:
        # 2-way logits [direct, semantic] from the scalar need (for NMI/AUROC)
        return torch.stack([-need, need], dim=1)
