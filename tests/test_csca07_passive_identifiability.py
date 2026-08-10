import math

from cwc.replay.passive_identifiability import (
    AR1Law,
    AR1MixtureEProcess,
    ar1_relative_entropy_rate,
    fiber_ambiguity_counterexample,
    hidden_autocatalytic_fixed_point,
    passive_information_certificate,
    replay_authority_state,
    simulate_ar1,
    spectral_topology_counterexample,
)


def test_ar1_kl_rate_zero_only_for_same_law():
    p = AR1Law(.75, .5)
    assert abs(ar1_relative_entropy_rate(p, p)) < 1e-15
    assert ar1_relative_entropy_rate(p, AR1Law(.25, .5)) > .2


def test_zero_information_rate_implies_infinite_passive_cost():
    cert = passive_information_certificate(alpha=.01, target_power=.95, information_rate_nats_per_transition=0.0, available_transitions=256)
    assert math.isinf(cert.necessary_transitions)
    assert cert.state == "PASSIVELY_UNFALSIFIABLE_OBSERVATIONAL_EQUIVALENCE"


def test_spectral_counterexample_same_path_and_spectrum_different_graph():
    c = spectral_topology_counterexample()
    assert c.max_observation_path_error < 1e-12
    assert c.spectral_distance < 1e-12
    assert c.adjacency_a != c.adjacency_b


def test_stable_hidden_fixed_point_carries_no_observational_information():
    c = hidden_autocatalytic_fixed_point()
    assert 0 < c.spectral_radius < 1
    assert c.context_derivative == 0
    assert c.observational_information_about_hidden_state == 0


def test_zero_per_model_fiber_entropy_does_not_identify_model():
    c = fiber_ambiguity_counterexample()
    assert c.per_model_fiber_entropy_bits == 0
    assert c.mixture_fiber_entropy_bits == 1
    assert c.mutual_information_model_trace_bits == 0


def test_passive_eprocess_rejects_large_predictive_misspecification():
    true = AR1Law(.75, .5)
    candidate = AR1Law(.25, .5)
    alternatives = [AR1Law(a, .5) for a in (-.75,-.4,0,.5,.68,.75,.9)]
    trace = simulate_ar1(true, transitions=256, seed=12345)
    out = AR1MixtureEProcess(candidate=candidate, alternatives=alternatives, alpha=.01).run(trace)
    assert out["rejected"] is True


def test_passive_nonrejection_never_becomes_causal_authority_without_assumptions():
    assert replay_authority_state(passive_rejected=False, causal_assumptions_identified=False) == "PASSIVE_EQUIVALENCE_UNRESOLVED_CAUSAL_AUTHORITY_BLOCKED"
