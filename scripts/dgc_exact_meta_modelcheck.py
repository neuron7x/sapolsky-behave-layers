from __future__ import annotations

from fractions import Fraction
import itertools

from cwc.governance.bounded_meta_planner import certify_bounded_horizon_meta_plan
from cwc.governance.metareasoning import MetaOperation, MetaTransition


def exact_values(decision, ops, horizon):
    prev=dict(decision)
    for _ in range(horizon):
        cur={}
        for s in sorted(decision):
            best=decision[s]
            for cost,nxt in ops[s]:
                q=-cost+prev[nxt]
                if q>best: best=q
            cur[s]=best
        prev=cur
    return prev


def main():
    states=("s0","s1"); stop_grid=(Fraction(0),Fraction(1)); costs=(Fraction(0),Fraction(1,2),Fraction(1))
    op_choices=tuple((c,n) for c in costs for n in states)
    models=0; certificates=0
    for stops in itertools.product(stop_grid,repeat=2):
        decision=dict(zip(states,stops,strict=True)); max_stop=max(stops)
        for choice0,choice1 in itertools.product(op_choices,repeat=2):
            raw={"s0":(choice0,),"s1":(choice1,)}
            ops={s:(MetaOperation(f"{s}-c",float(raw[s][0][0]),(MetaTransition(raw[s][0][1],1.0),)),) for s in states}
            models+=1
            for horizon in (1,2,3,4):
                exact=exact_values(decision,raw,horizon)["s0"]; previous=None
                for depth in range(horizon+1):
                    cert=certify_bounded_horizon_meta_plan(root_state="s0",decision_values={s:float(decision[s]) for s in states},operations=ops,state_value_upper={s:float(max_stop) for s in states},horizon=horizon,expansion_depth=depth,upper_bound_authority_digest="EXACT_RATIONAL_MODEL_CHECK",pure_information_certified=True)
                    lo=Fraction(str(cert.lower_value)); hi=Fraction(str(cert.upper_value))
                    if lo>exact or exact>hi: raise AssertionError((decision,raw,horizon,depth,lo,exact,hi))
                    if previous is not None and cert.residual_optimality_gap>previous+1e-12: raise AssertionError("residual gap increased")
                    previous=cert.residual_optimality_gap; certificates+=1
                if Fraction(str(cert.lower_value))!=exact or Fraction(str(cert.upper_value))!=exact: raise AssertionError("full expansion not exact")
    print(f"DGC-EXACT-META-MODELCHECK: PASS models={models} certificates={certificates}")
    return 0

if __name__=="__main__": raise SystemExit(main())
