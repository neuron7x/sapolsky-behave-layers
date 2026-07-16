"""AMG data contracts (spec §6). Group-level, budgeted, public traces only —
no `_last_mask` or hidden mutable diagnostic state."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import torch


class AdaptationMode(IntEnum):
    NO_UPDATE = 0
    UPDATE_EXISTING = 1
    UPDATE_ADAPTER_ONLY = 2
    REPLAY_PROTECTED_UPDATE = 3
    REQUEST_NEW_CAPACITY = 4   # recorded but REJECTED in the first experiment


@dataclass(frozen=True)
class ParameterGroupSpec:
    group_id: int
    name: str
    module_path: str
    parameter_names: tuple[str, ...]
    group_type: str
    parameter_count: int
    estimated_update_flops: int
    estimated_optimizer_bytes: int
    mutable: bool


@dataclass(frozen=True)
class PlasticityDecision:
    group_mask: torch.Tensor        # bool [G]
    lr_multiplier: torch.Tensor     # float32 [G]
    consolidation: torch.Tensor     # float32 [G]
    max_update_norm: torch.Tensor   # float32 [G]
    replay_fraction: float
    mode: AdaptationMode
    selected_cost: int
    budget: int

    def budget_ok(self) -> bool:
        return bool(self.group_mask.sum().item() <= self.budget)
