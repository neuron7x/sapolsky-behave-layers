from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cwc.governance.adaptive_eprocess import AdaptiveImportanceSample, adaptive_importance_mean_eprocess
from cwc.governance.ambiguity import certify_no_information_worth_cost
from cwc.governance.decision_stability import certify_action_stability
from cwc.governance.pareto import certify_paired_pareto_improvement
from cwc.governance.metareasoning import MetaOperation, MetaTransition, finite_horizon_meta_values, myopic_meta_values
from cwc.governance.robust_voc import RobustnessBudget, robust_voc_lower_bound


def run_attacks() -> dict[str, bool]:
    killed: dict[str, bool] = {}

    # Attack 1: nominal-positive VOC created by ignoring distribution shift.
    tv = robust_voc_lower_bound(
        nominal_gross_lower=0.50, nominal_cost=0.45,
        gross_lower_support=0.0, gross_upper_support=1.0,
        budget=RobustnessBudget(total_variation_radius=0.10),
    )
    killed["MATH_OMIT_TV_SHIFT"] = tv.nominal_voc_lower > 0.0 and tv.robust_voc_lower < 0.0

    # Attack 2: regret utility sensitivity is 2*eta, not eta.
    util = robust_voc_lower_bound(
        nominal_gross_lower=0.25, nominal_cost=0.10,
        gross_lower_support=0.0, gross_upper_support=0.5,
        budget=RobustnessBudget(utility_sup_error=0.08),
    )
    one_eta_wrong = 0.25 - 0.10 - 0.08
    killed["MATH_REGRET_ONE_ETA_UNDERPENALTY"] = one_eta_wrong > 0.0 and util.robust_voc_lower < 0.0

    # Attack 3: midpoint prior says information is cheap; credal extreme says otherwise.
    stop = certify_no_information_worth_cost(
        current_action_regrets=[0.0, 0.20],
        probability_lower=[0.2, 0.2], probability_upper=[0.8, 0.8],
        minimum_compute_cost=0.11,
    )
    midpoint_evpi = 0.10
    killed["MATH_CREDAL_MIDPOINT_PRIOR"] = midpoint_evpi <= 0.11 and not stop.stop_certified

    # Attack 4: a robust action margin can shrink by 2*eta.
    stability = certify_action_stability(
        ({"A": 1.0, "B": 0.90},), action="A", utility_sup_error=0.06,
    )
    killed["MATH_ACTION_MARGIN_ONE_ETA"] = not stability.stable

    # Attack 5: cost-only Pareto reporting hides quality regression.
    pareto = certify_paired_pareto_improvement(
        baseline_minus_dgc_cost=[0.4] * 1000,
        dgc_minus_baseline_quality=[-0.1] * 1000,
        cost_gain_support=(0.0, 1.0), quality_gain_support=(-0.2, 0.2),
    )
    killed["MATH_COST_ONLY_PARETO"] = pareto.certified_cost_reduction and not pareto.certified_pareto_improvement

    # Attack 6: myopic STOP can miss complementary multi-step computation.
    dv = {"s0": 0.0, "s1": 0.0, "s2": 1.0}
    ops = {
        "s0": [MetaOperation("c1", 0.1, (MetaTransition("s1", 1.0),))],
        "s1": [MetaOperation("c2", 0.1, (MetaTransition("s2", 1.0),))],
    }
    one = myopic_meta_values(decision_values=dv, operations=ops)
    two = finite_horizon_meta_values(decision_values=dv, operations=ops, horizon=2)
    killed["MATH_MYOPIC_COMPLEMENTARITY"] = one["s0"].selected_operation is None and two["s0"].selected_operation == "c1"

    # Attack 7: adaptive IPW without positivity can create arbitrarily unstable weights.
    try:
        adaptive_importance_mean_eprocess(
            [AdaptiveImportanceSample("A", 1.0, 0.01)],
            target_distribution={"A": 0.5, "B": 0.5}, lower=0.0, upper=1.0, alpha=0.05, lambdas=[0.1],
            max_importance_weight=10.0, null_mean=0.5,
        )
        killed["MATH_ADAPTIVE_PROPENSITY_COLLAPSE"] = False
    except ValueError:
        killed["MATH_ADAPTIVE_PROPENSITY_COLLAPSE"] = True

    return killed


def main() -> int:
    attacks = run_attacks()
    for name, caught in sorted(attacks.items()):
        print(f"DGC-MATH-ATTACK: {'KILLED' if caught else 'SURVIVED'} {name}")
    survived = [name for name, caught in attacks.items() if not caught]
    if survived:
        print("DGC-MATH-GATE: FAIL", ",".join(sorted(survived)))
        return 1
    print(f"DGC-MATH-GATE: PASS ({len(attacks)}/{len(attacks)} attacks killed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
