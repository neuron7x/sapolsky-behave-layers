from cwc.credit.ablation_shapley import AblationShapleyEstimate
from cwc.inference.composed_authority import ShadowCreditPolicy, decide_shadow_credit


def test_shadow_authority_accepts_only_separated_context_bound_credit():
    estimate = AblationShapleyEstimate(
        credits={"A": 1.0, "B": 0.1, "C": 0.0, "D": 0.0},
        estimator_variance={"A": 1e-6, "B": 1e-6, "C": 1e-6, "D": 1e-6},
        logical_evaluations=20,
        unique_forward_evaluations=12,
        sampling_units=4,
        method="ANTITHETIC_PERMUTATION_ABLATION_SHAPLEY",
    )
    policy = ShadowCreditPolicy("p1", 3.29, 0.1, 16)
    d = decide_shadow_credit(estimate, policy, context="PROSE")
    assert d.state == "ACCEPT_SHADOW_CREDIT_CONTEXT_BOUND"
    assert d.candidate == "A"
    assert not d.architecture_authority


def test_shadow_authority_abstains_when_variance_not_estimable():
    estimate = AblationShapleyEstimate(
        credits={"A": 1.0, "B": 0.0},
        estimator_variance={"A": 0.0, "B": 0.0},
        logical_evaluations=10,
        unique_forward_evaluations=8,
        sampling_units=1,
        method="ANTITHETIC_PERMUTATION_ABLATION_SHAPLEY",
    )
    d = decide_shadow_credit(estimate, ShadowCreditPolicy("p1", 3.29, 0.0, 16), context="CODE")
    assert d.state == "ABSTAIN_UNRESOLVED_CREDIT"
