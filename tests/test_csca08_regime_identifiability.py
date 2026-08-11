from __future__ import annotations

import numpy as np

from cwc.causal.regime_identifiability import coordinated_exclusion_counterexample, evaluate_regime_iv


def _sim(seed: int, *, n: int = 4096, lamb=(0.9, 0.5), eta=(0.0, 0.0), confound_r=0.0, sigy=0.8):
    rng = np.random.default_rng(seed)
    u = rng.normal(size=n)
    e1 = rng.normal(size=n)
    e2 = rng.normal(size=n)
    r1 = np.where(e1 + confound_r * u >= 0, 1.0, -1.0)
    r2 = np.where(e2 + 0.7 * confound_r * u >= 0, 1.0, -1.0)
    x = lamb[0] * r1 + lamb[1] * r2 + 0.8 * u + rng.normal(scale=0.6, size=n)
    y = 0.8 * x + 1.0 * u + eta[0] * r1 + eta[1] * r2 + rng.normal(scale=sigy, size=n)
    w = u + rng.normal(scale=0.5, size=n)
    return np.column_stack((r1, r2)), x, y, w


def test_valid_contract_returns_candidate_not_authority():
    r, x, y, w = _sim(1)
    d = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    assert d.state == "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"
    assert d.causal_authority_granted is False
    assert d.beta_hat is not None and abs(d.beta_hat - 0.8) < 0.12
    assert "A3_EXCLUSION_NOT_TESTABLE_FROM_FACTUAL_CHANNEL" in d.unresolved_assumption_debt


def test_nonproportional_direct_effect_is_falsified_by_overidentification():
    r, x, y, w = _sim(2, eta=(0.5, 0.0))
    d = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    assert d.state == "IDENTIFYING_ASSUMPTION_VIOLATED"
    assert d.max_overidentification_z > d.z_critical


def test_regime_confounding_is_falsified_by_negative_control():
    r, x, y, w = _sim(3, confound_r=1.0)
    d = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    assert d.state == "IDENTIFYING_ASSUMPTION_VIOLATED"
    assert d.max_negative_control_z > d.z_critical


def test_aleatoric_noise_is_not_structural_violation():
    r, x, y, w = _sim(4, sigy=3.0)
    d = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    assert d.state == "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"


def test_weak_regimes_abstain_for_information():
    r, x, y, w = _sim(5, lamb=(0.015, 0.01))
    d = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    assert d.state == "INSUFFICIENT_INFORMATION_BUDGET"


def test_coordinated_exclusion_is_exact_observational_equivalence():
    c = coordinated_exclusion_counterexample(seed=9)
    assert c.beta_invalid == 0.8
    assert c.beta_valid_reparameterized == 1.3
    assert c.max_x_path_error == 0.0
    assert c.max_y_path_error < 1e-12
    assert c.max_w_path_error == 0.0
