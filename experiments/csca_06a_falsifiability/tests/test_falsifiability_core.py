from __future__ import annotations

import math

from cwc.counterfactual.falsifiability import (
    AlternativeComponent,
    CompositeNullEProcess,
    GaussianInterventionalLaw,
    InterventionDesign,
    NuisanceEnvelope,
    latent_aleatoric_equivalence,
    model_class_falsifiability_state,
    profiled_kl_to_model_class,
)

NUIS = NuisanceEnvelope(-0.75, 0.75, 0.5, 2.5)
COST = {-1.0: 1.0, 1.0: 1.0}


def test_two_sided_intervention_separates_slope_from_shared_nuisance_intercept():
    design = InterventionDesign({-1.0: 1, 1.0: 1}, COST)
    kl, _ = profiled_kl_to_model_class(
        GaussianInterventionalLaw(0.8, 0.0, 1.0), design, model_slope=0.0, nuisance=NUIS
    )
    assert kl > 0.0


def test_single_intervention_can_be_exactly_equivalent_via_intercept():
    design = InterventionDesign({-1.0: 0, 1.0: 1}, COST)
    kl, _ = profiled_kl_to_model_class(
        GaussianInterventionalLaw(0.7, 0.0, 1.0), design, model_slope=0.0, nuisance=NUIS
    )
    assert kl < 1e-12


def test_latent_and_aleatoric_variance_are_not_separately_identified():
    pairs = latent_aleatoric_equivalence(1.7, points=17)
    variances = [g * g + s * s for g, s in pairs]
    assert max(variances) - min(variances) < 1e-12
    assert len({round(g, 8) for g, _ in pairs}) > 2


def test_eprocess_compute_budget_fails_closed():
    e = CompositeNullEProcess(
        model_slope=0.0,
        nuisance=NUIS,
        alternative=[AlternativeComponent(0.8, 0.0, 1.0)],
        alpha=0.01,
        max_cost=1.0,
    )
    design = InterventionDesign({-1.0: 1, 1.0: 1}, COST)
    try:
        e.step([0.0, 0.0], design)
    except RuntimeError as exc:
        assert "budget" in str(exc)
    else:
        raise AssertionError("budget overflow must fail closed")


def test_authority_never_converts_zero_separation_to_graph_falsification():
    state = model_class_falsifiability_state(
        separation_rate=0.0,
        observed_rejection=True,
        nuisance_scope_certified=True,
        budget_exhausted=False,
    )
    assert state == "UNRESOLVED_INTERVENTIONAL_EQUIVALENCE"


def test_information_converse_blocks_weak_edge_before_spend():
    from cwc.counterfactual.falsifiability import information_budget_certificate
    strong = information_budget_certificate(
        alpha=0.01, target_power=0.95,
        separation_rate_per_cost=0.22438095693074434, available_cost=256.0,
    )
    weak = information_budget_certificate(
        alpha=0.01, target_power=0.95,
        separation_rate_per_cost=0.00985793158220849, available_cost=256.0,
    )
    assert abs(strong.required_information_nats - 4.176898950135489) < 1e-12
    assert abs(strong.necessary_cost_lower_bound - 18.61521141219082) < 1e-10
    assert strong.state == "BUDGET_NOT_RULED_OUT_BY_INFORMATION_CONVERSE"
    assert abs(weak.necessary_cost_lower_bound - 423.70946839131244) < 1e-9
    assert weak.state == "BUDGET_BELOW_NECESSARY_INFORMATION_BOUND"


def test_information_converse_zero_separation_is_infinite_cost():
    import math
    from cwc.counterfactual.falsifiability import information_budget_certificate
    cert = information_budget_certificate(
        alpha=0.01, target_power=0.95, separation_rate_per_cost=0.0, available_cost=10**9,
    )
    assert math.isinf(cert.necessary_cost_lower_bound)
    assert cert.state == "INTERVENTIONALLY_UNFALSIFIABLE_AT_THIS_DESIGN"
