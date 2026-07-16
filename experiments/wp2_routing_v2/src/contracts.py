"""Observable semantic state + routing trace (Act §3). Every field has an exact
ground-truth target; an unconstrained embedding is NOT a semantic state."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import torch


class TaskKind(IntEnum):
    EASY_DIRECT = 0
    HARD_SEMANTIC = 1


class RoutingMode(IntEnum):
    DENSE_SEMANTIC = 0   # every sample -> semantic path (quality ceiling)
    DIRECT_ONLY = 1      # every sample -> cheap path
    ORACLE = 2           # route by true task_kind
    RANDOM = 3           # exactly K random samples -> semantic
    FROZEN = 4           # frozen random-init controller
    LEARNED = 5          # trainable controller
    SHUFFLED_LEARNED = 6  # learned frequencies, decisions permuted across batch


# --- vocabulary layout (vocab_size = 40) ---
PAD, POS, NEG, NOT, F_IS, F_BY, F_DIST, F_SEP = 0, 1, 2, 3, 4, 5, 6, 7
ENT_LO, ENT_HI = 10, 26      # 16 entities
REL_LO, REL_HI = 30, 38      # 8 relations
VOCAB_SIZE = 40


@dataclass(frozen=True)
class SemanticState:
    subject: torch.Tensor       # int64 [B]
    relation: torch.Tensor      # int64 [B]
    object: torch.Tensor        # int64 [B]
    polarity: torch.Tensor      # int64 [B], {0,1}
    confidence: torch.Tensor    # float32 [B]


@dataclass(frozen=True)
class RoutingTrace:
    need_score: torch.Tensor       # float32 [B]
    semantic_mask: torch.Tensor    # bool [B]
    route_logits: torch.Tensor     # float32 [B, 2]
    active_cost: torch.Tensor      # int64 [B]
    capacity: int
