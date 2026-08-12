"""AMG data contracts (spec §6): the immutable vocabulary the governor speaks.

WHY frozen dataclasses. Every type here is `frozen=True` / an `IntEnum` on purpose:
a plasticity decision is *evidence*, and evidence must not be mutated after the fact.
This is the same discipline the routing subsystem enforces by banning `_last_mask` —
there is no hidden, mutable diagnostic state anywhere in the control path, so a logged
decision always equals the decision that was executed.

Everything is expressed at the granularity of a parameter *group* (length-G tensors),
never per individual weight: the governor's unit of control is the structured group
(see `registry`), which is what makes a decision human-interpretable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import torch


class AdaptationMode(IntEnum):
    """The kind of update a decision authorizes. Integer-valued so it serializes into
    a trace without a lookup table. `REQUEST_NEW_CAPACITY` is present in the vocabulary
    but is *recorded and then rejected* by the first experiment's governor — the
    ability to ask for growth is modelled, the ability to grant it is withheld until a
    structural-plasticity study licenses it (kept explicit rather than silently absent).
    """

    NO_UPDATE = 0
    UPDATE_EXISTING = 1
    UPDATE_ADAPTER_ONLY = 2
    REPLAY_PROTECTED_UPDATE = 3
    REQUEST_NEW_CAPACITY = 4  # recorded but REJECTED in the first experiment


@dataclass(frozen=True)
class ParameterGroupSpec:
    """Static description of one parameter group — the governor's unit of control.

    A group is a set of parameters that share a role and a block (e.g. all of
    `attention.qkv` in block 3). The `estimated_*` fields make the *cost* of updating
    this group explicit and comparable, so the budget in a `PlasticityDecision` is
    denominated in real resources, not in an abstract count:
      - `estimated_update_flops`   ~ 2 . parameter_count (one multiply + one add each);
      - `estimated_optimizer_bytes`~ parameter_count . bytes_per_param . state_mult
                                     (e.g. Adam keeps ~2 state tensors per parameter).
    `mutable` records whether the group is *allowed* to change at all; `group_id` is a
    content-derived stable hash (see registry) so specs are reproducible and diffable.
    """

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
    """One governor decision, expressed as length-G tensors over the G groups.

    Operational reading (index g = group g):
      - `group_mask[g]`      : may group g change this step? (the budgeted choice);
      - `lr_multiplier[g]`   : scale on group g's gradient (metaplastic learning rate);
      - `consolidation[g]`   : lambda pulling group g back toward the reference weights
                               (the EWC/SI/MAS elastic term), weighted by importance Omega;
      - `max_update_norm[g]` : hard per-group cap on the update norm (0 = uncapped);
      - `replay_fraction`    : fraction of the batch drawn from replay;
      - `selected_cost`/`budget` : chosen vs allowed number of active groups.

    `budget` is the binding constraint that makes adaptivity *identifiable* at all
    (see the package charter); `budget_ok()` is the invariant the optimizer refuses to
    violate.
    """

    group_mask: torch.Tensor  # bool [G]
    lr_multiplier: torch.Tensor  # float32 [G]
    consolidation: torch.Tensor  # float32 [G]
    max_update_norm: torch.Tensor  # float32 [G]
    replay_fraction: float
    mode: AdaptationMode
    selected_cost: int
    budget: int

    def budget_ok(self) -> bool:
        """True iff no more groups are active than the budget allows. The optimizer
        raises rather than silently overspending, so a budget violation can never be
        laundered into a result."""
        return bool(self.group_mask.sum().item() <= self.budget)
