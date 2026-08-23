from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from cwc.governance.metareasoning import MetaOperation


@dataclass(frozen=True, slots=True)
class MetaOperationInterval:
    operation_id: str
    lower_value: float
    upper_value: float


@dataclass(frozen=True, slots=True)
class MetaActionBoundCertificate:
    stop_value: float
    policy_lower_value: float
    global_value_upper: float
    suboptimality_upper_bound: float
    certified_optimal_action: str | None
    operation_intervals: tuple[MetaOperationInterval, ...]
    upper_bound_authority_digest: str
    method: str = "TRANSITION_LOCAL_META_BRANCH_BOUND_V1"


def certify_meta_action_with_transition_bounds(*, stop_value: float, operations: Sequence[MetaOperation], next_state_stop_values: Mapping[str,float], next_state_value_upper: Mapping[str,float], upper_bound_authority_digest: str) -> MetaActionBoundCertificate:
    """Horizon-independent branch-and-bound certificate for a meta action.

    For each next state s', caller supplies D(s') and an externally justified
    U(s') >= optimal future meta-value from s' for every remaining horizon.
    Then for operation c:
      -cost(c)+E[D(S')] <= Q*(c) <= -cost(c)+E[U(S')].
    This yields a root lower policy value, global upper value, a certified gap,
    and can prove STOP or one operation globally optimal without solving the
    full metalevel MDP. Invalid upper-bound authority invalidates the theorem.
    """
    if not upper_bound_authority_digest.strip():
        raise ValueError("upper-bound authority digest required")
    stop=float(stop_value)
    if not math.isfinite(stop): raise ValueError("finite stop value required")
    intervals=[]
    for op in operations:
        lo=-op.cost; hi=-op.cost
        for t in op.transitions:
            if t.next_state not in next_state_stop_values or t.next_state not in next_state_value_upper:
                raise ValueError("missing next-state lower/upper value")
            d=float(next_state_stop_values[t.next_state]); u=float(next_state_value_upper[t.next_state])
            if not math.isfinite(d) or not math.isfinite(u) or u < d-1e-12:
                raise ValueError("next-state upper bound must be finite and >= stop value")
            lo += t.probability*d
            hi += t.probability*u
        intervals.append(MetaOperationInterval(op.operation_id,lo,hi))
    best_lower=max([stop]+[r.lower_value for r in intervals])
    global_upper=max([stop]+[r.upper_value for r in intervals])
    certified=None
    max_op_upper=max((r.upper_value for r in intervals),default=-math.inf)
    if stop >= max_op_upper-1e-12:
        certified="STOP"
    else:
        for r in sorted(intervals,key=lambda z:z.operation_id):
            other_upper=max([stop]+[o.upper_value for o in intervals if o.operation_id!=r.operation_id])
            if r.lower_value >= other_upper-1e-12:
                certified=r.operation_id
                break
    return MetaActionBoundCertificate(stop,best_lower,global_upper,max(0.0,global_upper-best_lower),certified,tuple(intervals),upper_bound_authority_digest)
