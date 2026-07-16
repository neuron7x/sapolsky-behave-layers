"""Plasticity-separable continual benchmark (spec §11). Different task families
are best adapted by DIFFERENT parameter groups, so a per-task oracle allocation
can beat any fixed allocation (the identifiability condition).

- BASE (identity): output = input. Pretraining task.
- LEXICAL (relabel): output = π(input), a fixed symbol permutation. Best adapted
  by the OUTPUT map (head) / per-token MLP; attention cannot cleanly remap a
  per-token vocabulary.
- RELATIONAL (shift): output_i = input_{i-1}. REQUIRES attention to move
  information across positions; head/mlp are per-token and cannot.
"""
from __future__ import annotations

import torch

from experiments.wp3_plasticity_v1.src.model import SEQ_LEN, VOCAB

_g = torch.Generator().manual_seed(4242)
PERM = torch.randperm(VOCAB, generator=_g)   # fixed lexical relabeling


def _inputs(batch: int, gen: torch.Generator, device: str) -> torch.Tensor:
    return torch.randint(0, VOCAB, (batch, SEQ_LEN), generator=gen).to(device)


def base_batch(batch: int, gen: torch.Generator, device: str = "cpu"):
    x = _inputs(batch, gen, device)
    return x, x.clone()                       # identity


def lexical_batch(batch: int, gen: torch.Generator, device: str = "cpu"):
    x = _inputs(batch, gen, device)
    return x, PERM.to(device)[x]              # relabel


def relational_batch(batch: int, gen: torch.Generator, device: str = "cpu"):
    x = _inputs(batch, gen, device)
    y = torch.roll(x, shifts=1, dims=1)       # output_i = input_{i-1}
    y[:, 0] = x[:, 0]                          # position 0 keeps itself
    return x, y


TASKS = {"lexical": lexical_batch, "relational": relational_batch}
