from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping, Sequence

from cwc.governance.metareasoning import MetaOperation


@dataclass(frozen=True, slots=True)
class MetaActionInterval:
    action: str
    lower_value: float
    upper_value: float


@dataclass(frozen=True, slots=True)
class BoundedMetaPlanCertificate:
    root_state: str
    horizon: int
    expansion_depth: int
    lower_value: float
    upper_value: float
    residual_optimality_gap: float
    lower_policy_action: str
    certified_optimal_action: str | None
    action_intervals: tuple[MetaActionInterval, ...]
    upper_bound_authority_digest: str
    pure_information_certified: bool
    exact: bool
    method: str = "FINITE_HORIZON_ADMISSIBLE_META_BRANCH_BOUND_V1"


def certify_bounded_horizon_meta_plan(
    *, root_state: str, decision_values: Mapping[str, float],
    operations: Mapping[str, Sequence[MetaOperation]],
    state_value_upper: Mapping[str, float], horizon: int,
    expansion_depth: int, upper_bound_authority_digest: str,
    pure_information_certified: bool,
) -> BoundedMetaPlanCertificate:
    """Bound a finite-horizon metalevel MDP with an admissible leaf upper bound.

    Caller supplies U(s) such that every relevant finite-horizon optimal value
    satisfies V_h(s)<=U(s). At an unexpanded leaf use [D(s),U(s)]; expansion
    propagates child intervals through Bellman expectation. With nonnegative
    transition probabilities, L_d(s)<=V_h(s)<=U_d(s). The root width is a
    certified residual optimality gap under the declared upper-bound authority.
    At expansion_depth==horizon the finite model is solved exactly.

    This is not an infinite-horizon or unknown-model planner.
    """
    if not root_state.strip() or not upper_bound_authority_digest.strip():
        raise ValueError("root state and upper-bound authority digest required")
    if not pure_information_certified:
        raise ValueError("pure-information authority required for this planner")
    if horizon < 0 or expansion_depth < 0 or expansion_depth > horizon:
        raise ValueError("require 0 <= expansion_depth <= horizon")
    dvals={str(s):float(v) for s,v in decision_values.items()}
    uvals={str(s):float(v) for s,v in state_value_upper.items()}
    if root_state not in dvals or set(dvals)!=set(uvals):
        raise ValueError("decision and upper-value maps must cover same states including root")
    for state in dvals:
        if not state.strip() or not math.isfinite(dvals[state]) or not math.isfinite(uvals[state]):
            raise ValueError("finite values for non-empty states required")
        if uvals[state] < dvals[state]-1e-12:
            raise ValueError("state upper bound cannot be below stop value")
    for state,ops in operations.items():
        if state not in dvals: raise ValueError("operation state missing decision value")
        seen=set()
        for op in ops:
            if op.operation_id in seen: raise ValueError("duplicate operation id within state")
            seen.add(op.operation_id)
            for t in op.transitions:
                if t.next_state not in dvals: raise ValueError("transition to unknown state")

    @lru_cache(maxsize=None)
    def bound(state:str,h:int,depth:int):
        stop=dvals[state]
        if h==0:
            row=MetaActionInterval("STOP",stop,stop)
            return stop,stop,(row,),"STOP","STOP"
        if depth==0:
            row=MetaActionInterval("STOP",stop,stop)
            certified="STOP" if math.isclose(uvals[state],stop,rel_tol=0.0,abs_tol=1e-12) else None
            return stop,uvals[state],(row,),"STOP",certified
        rows=[MetaActionInterval("STOP",stop,stop)]
        for op in operations.get(state,()):
            qlo=-op.cost; qhi=-op.cost
            for t in op.transitions:
                clo,chi,_,_,_=bound(t.next_state,h-1,depth-1)
                qlo += t.probability*clo; qhi += t.probability*chi
            if qhi < qlo-1e-10: raise RuntimeError("internal interval inversion")
            rows.append(MetaActionInterval(op.operation_id,qlo,qhi))
        lower_value=max(r.lower_value for r in rows)
        lower_candidates=sorted(r.action for r in rows if math.isclose(r.lower_value,lower_value,rel_tol=0.0,abs_tol=1e-12))
        lower_action="STOP" if "STOP" in lower_candidates else lower_candidates[0]
        upper_value=max(r.upper_value for r in rows)
        certified=None
        for row in sorted(rows,key=lambda r:r.action):
            other_upper=max((r.upper_value for r in rows if r.action!=row.action),default=-math.inf)
            if row.lower_value >= other_upper-1e-12:
                certified=row.action; break
        return lower_value,upper_value,tuple(rows),lower_action,certified

    lower,upper,intervals,lower_action,certified=bound(root_state,horizon,expansion_depth)
    gap=max(0.0,upper-lower)
    exact=expansion_depth==horizon
    if exact and not math.isclose(lower,upper,rel_tol=0.0,abs_tol=1e-10):
        raise RuntimeError("full expansion must be exact")
    return BoundedMetaPlanCertificate(root_state,horizon,expansion_depth,lower,upper,gap,lower_action,certified,intervals,upper_bound_authority_digest,True,exact)
