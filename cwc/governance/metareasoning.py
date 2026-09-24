from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class MetaTransition:
    next_state: str
    probability: float

    def __post_init__(self) -> None:
        if not self.next_state.strip():
            raise ValueError("next_state required")
        p = float(self.probability)
        if not math.isfinite(p) or p < 0.0 or p > 1.0:
            raise ValueError("probability must be in [0,1]")
        object.__setattr__(self, "probability", p)


@dataclass(frozen=True, slots=True)
class MetaOperation:
    operation_id: str
    cost: float
    transitions: tuple[MetaTransition, ...]

    def __post_init__(self) -> None:
        if not self.operation_id.strip() or not self.transitions:
            raise ValueError("operation id and transitions required")
        cost = float(self.cost)
        if not math.isfinite(cost) or cost < 0.0:
            raise ValueError("cost must be finite and >= 0")
        object.__setattr__(self, "cost", cost)
        total = math.fsum(t.probability for t in self.transitions)
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("transition probabilities must sum to 1")


@dataclass(frozen=True, slots=True)
class MetaValue:
    state: str
    horizon: int
    value: float
    selected_operation: str | None
    stop_value: float
    method: str = "FINITE_HORIZON_META_BELLMAN_V1"


def finite_horizon_meta_values(
    *,
    decision_values: Mapping[str, float],
    operations: Mapping[str, Sequence[MetaOperation]],
    horizon: int,
) -> dict[str, MetaValue]:
    """Exact finite-horizon metareasoning Bellman recursion.

    V_0(s)=D(s), where D is the value of stopping and taking the best external
    action. For h>=1,

      V_h(s)=max(D(s), max_c[-Cost(c)+E[V_{h-1}(S')|s,c]]).

    This oracle is finite-state/finite-horizon only. It is used to quantify the
    approximation error of myopic one-step VOC, not as a scalable runtime.
    """
    if horizon < 0:
        raise ValueError("horizon must be >= 0")
    values = {str(s): float(v) for s, v in decision_values.items()}
    if not values or any(not s.strip() or not math.isfinite(v) for s, v in values.items()):
        raise ValueError("finite decision values for non-empty states required")
    for state, ops in operations.items():
        if state not in values:
            raise ValueError("operation state missing decision value")
        for op in ops:
            for transition in op.transitions:
                if transition.next_state not in values:
                    raise ValueError("transition to unknown state")

    prev = {
        s: MetaValue(s, 0, d, None, d)
        for s, d in values.items()
    }
    for h in range(1, horizon + 1):
        current: dict[str, MetaValue] = {}
        for state in sorted(values):
            stop = values[state]
            best_value = stop
            best_op: str | None = None
            for op in operations.get(state, ()):  # a state may have no compute action
                q = -op.cost + math.fsum(
                    t.probability * prev[t.next_state].value for t in op.transitions
                )
                if q > best_value + 1e-15 or (
                    math.isclose(q, best_value, rel_tol=0.0, abs_tol=1e-15)
                    and best_op is not None and op.operation_id < best_op
                ):
                    best_value = q
                    best_op = op.operation_id
            current[state] = MetaValue(state, h, best_value, best_op, stop)
        prev = current
    return prev


def myopic_meta_values(
    *, decision_values: Mapping[str, float], operations: Mapping[str, Sequence[MetaOperation]]
) -> dict[str, MetaValue]:
    return finite_horizon_meta_values(decision_values=decision_values, operations=operations, horizon=1)
