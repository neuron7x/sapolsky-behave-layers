from __future__ import annotations

from cwc.governance.causal_obligations import IdentifiabilityStatus, certify_declared_interventional_query
from cwc.governance.metareasoning_gap_v2 import perfect_information_myopic_gap_bound
from cwc.governance.drift_contract_v2 import bounded_drift_current_mean_lcb
from cwc.governance.restricted_sampling import certify_restricted_adaptive_policy


def _must_raise(name: str, fn) -> None:
    try:
        fn()
    except (ValueError, TypeError):
        print(f"KILLED {name}")
        return
    raise AssertionError(f"SURVIVED {name}")


def main() -> int:
    _must_raise("NEGATIVE_DRIFT_BUDGET", lambda: bounded_drift_current_mean_lcb([0.5], lower=0, upper=1, delta=0.05, drift_to_current=[-1e-6]))
    _must_raise("INFEASIBLE_PROPENSITY_FLOOR", lambda: certify_restricted_adaptive_policy(target_distribution={"a": 0.5, "b": 0.5}, minimum_propensity=0.51))
    _must_raise("IMPOSSIBLE_EVPI_UPPER", lambda: perfect_information_myopic_gap_bound(current_action_regrets=[0.0, 0.1], probability_upper_expectation=0.2, minimum_future_compute_cost=0.0, myopic_value=0.0))
    cert = certify_declared_interventional_query(structural_model_digest="model", intervention_declared=True, outcome_mapping_declared=True, no_hidden_confounding_asserted=False, transport_required=False, transport_assumptions_declared=False)
    if cert.status is not IdentifiabilityStatus.NOT_IDENTIFIED:
        raise AssertionError("SURVIVED IDENTIFIABILITY_BY_DECLARATION")
    print("KILLED IDENTIFIABILITY_BY_DECLARATION")
    print("DGC-MATH-V2C-ATTACK: PASS 4/4 KILLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
