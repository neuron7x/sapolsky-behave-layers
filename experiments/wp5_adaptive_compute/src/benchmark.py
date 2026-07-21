"""Cyclic-shift benchmark for the adaptive-compute mechanism.

Target y_i = x_{(i-d) mod T}: a shift by distance d. One trained Block iteration advances the
shift by 1, so a shift-by-d answer needs d units of compute. Difficulty class = required d.
"""
from __future__ import annotations

import torch

from experiments.wp5_adaptive_compute.src.model import SEQ_LEN, VOCAB

DEPTHS = [1, 2, 3]          # required shift distances (difficulty classes)
K_CHOICES = [1, 2, 3]       # compute budgets (block iterations)


def shift_batch(batch: int, d: int, gen: torch.Generator, device: str = "cpu"):
    x = torch.randint(0, VOCAB, (batch, SEQ_LEN), generator=gen).to(device)
    y = torch.roll(x, shifts=d, dims=1)     # y_i = x_{i-d}
    return x, y
