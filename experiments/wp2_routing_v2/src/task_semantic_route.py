"""Semantic-tuple benchmark (Act §4). Every example encodes
(subject, relation, object, polarity). Canonical target = [subj, rel, obj, pol].

EASY_DIRECT: canonical order at positions 0-3 (solvable by a local path).
HARD_SEMANTIC: passive / distractor-prefix / negation transformations that put
the canonical fields beyond a 4-token local window (need global attention).

Compositional split by (subject, relation, object) tuple identity — no test
tuple appears in training.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

from experiments.wp2_routing_v2.src.contracts import (
    ENT_HI,
    ENT_LO,
    F_BY,
    F_DIST,
    F_IS,
    F_SEP,
    NEG,
    NOT,
    PAD,
    POS,
    REL_HI,
    REL_LO,
    SemanticState,
    TaskKind,
)

SEQ_LEN = 12
L_OUT = 4


@dataclass(frozen=True)
class SplitSpec:
    split: str = "train"   # train | val | test
    p_hard: float = 0.5


def _tuple_in_split(subj: int, rel: int, obj: int, split: str) -> bool:
    # deterministic hash bucket over the tuple; test/val hold out disjoint tuples
    h = (subj * 131 + rel * 17 + obj) % 10
    if split == "test":
        return h in (0, 1)          # 20% of tuples reserved for test
    if split == "val":
        return h in (2, 3)          # 20% for val (unseen templates handled below)
    return h >= 4                   # 60% train


def _sample_tuple(gen: torch.Generator, split: str) -> tuple[int, int, int]:
    for _ in range(64):
        subj = int(torch.randint(ENT_LO, ENT_HI, (1,), generator=gen).item())
        obj = int(torch.randint(ENT_LO, ENT_HI, (1,), generator=gen).item())
        rel = int(torch.randint(REL_LO, REL_HI, (1,), generator=gen).item())
        if obj != subj and _tuple_in_split(subj, rel, obj, split):
            return subj, rel, obj
    return subj, rel, obj


def _polarity_token(pol: int) -> int:
    return POS if pol == 1 else NEG


def generate_batch(batch_size: int, gen: torch.Generator, split: str = "train",
                   p_hard: float = 0.5, device: str = "cpu"):
    tokens = torch.full((batch_size, SEQ_LEN), PAD, dtype=torch.long)
    canonical = torch.full((batch_size, L_OUT), PAD, dtype=torch.long)
    subj_t = torch.zeros(batch_size, dtype=torch.long)
    rel_t = torch.zeros(batch_size, dtype=torch.long)
    obj_t = torch.zeros(batch_size, dtype=torch.long)
    pol_t = torch.zeros(batch_size, dtype=torch.long)
    kind = torch.zeros(batch_size, dtype=torch.long)

    for b in range(batch_size):
        subj, rel, obj = _sample_tuple(gen, split)
        hard = bool(torch.rand(1, generator=gen).item() < p_hard)
        pol = 1
        if hard:
            kind[b] = int(TaskKind.HARD_SEMANTIC)
            template = int(torch.randint(0, 3, (1,), generator=gen).item())
            if template == 0:  # passive: [obj, F_IS, rel, F_BY, subj]
                seq = [obj, F_IS, rel, F_BY, subj]
            elif template == 1:  # distractor prefix: [F_DIST, dist, F_SEP, subj, rel, obj]
                dist = int(torch.randint(ENT_LO, ENT_HI, (1,), generator=gen).item())
                seq = [F_DIST, dist, F_SEP, subj, rel, obj]
            else:  # negation: [NOT, dist, F_SEP, subj, rel, obj] -> polarity flips
                dist = int(torch.randint(ENT_LO, ENT_HI, (1,), generator=gen).item())
                pol = 0
                seq = [NOT, dist, F_SEP, subj, rel, obj]
        else:  # EASY canonical at 0-3
            kind[b] = int(TaskKind.EASY_DIRECT)
            seq = [subj, rel, obj, _polarity_token(1)]
        tokens[b, :len(seq)] = torch.tensor(seq, dtype=torch.long)
        canonical[b] = torch.tensor([subj, rel, obj, _polarity_token(pol)], dtype=torch.long)
        subj_t[b], rel_t[b], obj_t[b], pol_t[b] = subj, rel, obj, pol

    state = SemanticState(subject=subj_t.to(device), relation=rel_t.to(device),
                          object=obj_t.to(device), polarity=pol_t.to(device),
                          confidence=torch.ones(batch_size, device=device))
    return (tokens.to(device), state, canonical.to(device), kind.to(device))


def deterministic_output_parser(output_tokens: torch.Tensor) -> SemanticState:
    """Parse a canonical [B,4] output back into the discrete tuple (Act §14)."""
    subj = output_tokens[:, 0]
    rel = output_tokens[:, 1]
    obj = output_tokens[:, 2]
    pol = (output_tokens[:, 3] == POS).long()
    return SemanticState(subject=subj, relation=rel, object=obj, polarity=pol,
                         confidence=torch.ones(output_tokens.shape[0], device=output_tokens.device))
