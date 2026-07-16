"""Typed-operation task for RCFR (Act F). One shared module must perform R
distinct symbol operations chosen per example by a role. Each operation is a
fixed random permutation of the S symbols; the model must apply the role's
permutation element-wise to the operand sequence.

A single fixed linear operator cannot be R different permutations, so a role
that modulates the operator's weights (RCFR) is the mechanism under test.

Compositional generalization: a held-out set of (role, symbol) pairs never
appears in training but is tested (unseen compositions).
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

N_SYMBOLS = 16
N_ROLES = 8
SEQ_LEN = 8
# vocab: [0..S) symbols, [S..S+R) role tokens, PAD
PAD = N_SYMBOLS + N_ROLES
VOCAB = N_SYMBOLS + N_ROLES + 1


@dataclass(frozen=True)
class OpTaskConfig:
    n_symbols: int = N_SYMBOLS
    n_roles: int = N_ROLES
    seq_len: int = SEQ_LEN


def build_permutations(seed: int = 12345) -> torch.Tensor:
    """R fixed permutations of S symbols. Deterministic given seed."""
    g = torch.Generator().manual_seed(seed)
    perms = torch.stack([torch.randperm(N_SYMBOLS, generator=g) for _ in range(N_ROLES)])
    return perms  # (R, S)


PERMS = build_permutations()


def generate_batch(batch_size: int, gen: torch.Generator, split: str = "train",
                   device: str = "cpu"):
    """Returns tokens (B, 1+L) [role, x0..x_{L-1}], target (B, L) = perm applied,
    roles (B,), operands (B, L).

    Operations are arbitrary permutations, so each (role, symbol) must appear in
    training to be learnable. `split` only changes the RNG stream: the test set
    is novel SEQUENCE arrangements of trained (role, symbol) pairs — a genuine
    compositional-generalization test for an element-wise operator, satisfiable
    only if the module learned the operation rather than memorizing sequences.
    """
    L = SEQ_LEN
    tokens = torch.full((batch_size, 1 + L), PAD, dtype=torch.long)
    target = torch.zeros((batch_size, L), dtype=torch.long)
    roles = torch.zeros(batch_size, dtype=torch.long)
    for b in range(batch_size):
        r = int(torch.randint(0, N_ROLES, (1,), generator=gen).item())
        roles[b] = r
        operands = torch.randint(0, N_SYMBOLS, (L,), generator=gen)
        tokens[b, 0] = N_SYMBOLS + r          # role token
        tokens[b, 1:1 + L] = operands
        target[b] = PERMS[r][operands]
    return tokens.to(device), target.to(device), roles.to(device)
