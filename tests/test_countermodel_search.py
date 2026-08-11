from __future__ import annotations

import numpy as np

from cwc.causal.regime_identifiability import evaluate_regime_iv
from cwc.epistemics.countermodel_search import (
    StructuralAssumptionBounds,
    construct_exact_countermodel,
    fit_reduced_form,
    search_countermodels,
)


def _sim(seed: int, *, n: int = 4096, beta: float = 0.8, k: float = 0.0, sigy: float = 0.8):
    rng = np.random.default_rng(seed)
    u = rng.normal(size=n)
    r1 = rng.choice((-1.0, 1.0), size=n)
    r2 = rng.choice((-1.0, 1.0), size=n)
    lam = np.array([0.9, 0.5])
    r = np.column_stack((r1, r2))
    x = r @ lam + 0.8 * u + rng.normal(scale=0.6, size=n)
    y = beta * x + u + k * (r @ lam) + rng.normal(scale=sigy, size=n)
    w = u + rng.normal(scale=0.5, size=n)
    return r, x, y, w


def test_exact_reparameterization_reconstructs_every_observed_path():
    r, x, y, _ = _sim(1)
    rf = fit_reduced_form(regimes=r, treatment=x, outcome=y)
    m = construct_exact_countermodel(
        reduced_form=rf,
        beta=1.4,
        reference_beta=0.8,
        regimes=r,
        treatment=x,
        outcome=y,
    )
    assert m.observational_kl_nats == 0.0
    assert m.max_path_reconstruction_error < 1e-12
    assert abs(m.causal_shift - 0.6) < 1e-12


def test_unrestricted_factual_law_contains_causally_distinct_countermodels():
    r, x, y, w = _sim(2)
    iv = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    assert iv.state == "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"
    d = search_countermodels(
        regimes=r,
        treatment=x,
        outcome=y,
        reference_beta=float(iv.beta_hat),
        beta_grid=np.linspace(-0.5, 2.0, 101),
        min_causal_shift=0.49,
    )
    assert d.state == "OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES"
    assert d.exact_equivalent_count > 0
    assert d.constrained_survivor_count == d.exact_equivalent_count
    assert d.causal_authority_granted is False


def test_exclusion_bound_only_yields_assumption_conditional_identification():
    r, x, y, w = _sim(3)
    iv = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    d = search_countermodels(
        regimes=r,
        treatment=x,
        outcome=y,
        reference_beta=float(iv.beta_hat),
        beta_grid=np.linspace(-0.5, 2.0, 101),
        min_causal_shift=0.49,
        bounds=StructuralAssumptionBounds(max_direct_effect_l2=0.08),
    )
    assert d.exact_equivalent_count > 0
    assert d.constrained_survivor_count == 0
    assert d.state == "ASSUMPTION_CONDITIONAL_IDENTIFICATION_COUNTERMODELS_OUTSIDE_BOUNDS"
    assert d.causal_authority_granted is False


def test_coordinated_exclusion_generator_recovers_near_true_0p8_alternative():
    r, x, y, w = _sim(4, k=0.5)
    iv = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    assert iv.state == "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"
    assert iv.beta_hat is not None and abs(iv.beta_hat - 1.3) < 0.08
    d = search_countermodels(
        regimes=r,
        treatment=x,
        outcome=y,
        reference_beta=float(iv.beta_hat),
        beta_grid=np.linspace(-0.5, 2.0, 101),
        min_causal_shift=0.49,
    )
    close = [m for m in d.pareto_frontier if abs(m.beta - 0.8) <= 0.03]
    assert close
    assert close[0].max_path_reconstruction_error < 1e-12
    assert d.causal_authority_granted is False


def test_aleatoric_noise_does_not_destroy_exact_countermodel_construction():
    r, x, y, w = _sim(5, sigy=3.0)
    iv = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    d = search_countermodels(
        regimes=r,
        treatment=x,
        outcome=y,
        reference_beta=float(iv.beta_hat),
        beta_grid=np.linspace(-0.5, 2.0, 101),
        min_causal_shift=0.49,
    )
    assert d.exact_equivalent_count > 0
    assert max(m.max_path_reconstruction_error for m in d.pareto_frontier) < 1e-11


def test_invalid_upstream_state_cannot_be_upgraded_by_countermodel_search():
    r, x, y, _ = _sim(6)
    d = search_countermodels(
        regimes=r,
        treatment=x,
        outcome=y,
        reference_beta=0.8,
        beta_grid=[0.0, 1.6],
        min_causal_shift=0.4,
        candidate_state="IDENTIFYING_ASSUMPTION_VIOLATED",
    )
    assert d.state == "UPSTREAM_CANDIDATE_NOT_ELIGIBLE"
    assert d.causal_authority_granted is False


def test_unrestricted_equivalence_is_explicitly_set_valued_not_truth_selected():
    r, x, y, w = _sim(7, k=0.5)
    iv = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    d = search_countermodels(
        regimes=r,
        treatment=x,
        outcome=y,
        reference_beta=float(iv.beta_hat),
        beta_grid=np.linspace(-0.5, 2.0, 101),
        min_causal_shift=0.40,
    )
    assert d.unrestricted_beta_set_kind == "ALL_REAL_BETA_UNDER_UNRESTRICTED_REPARAMETERIZATION"
    assert d.finite_grid_alternative_beta_diameter > 1.0
    assert d.causal_authority_granted is False


def test_direct_effect_bound_produces_analytic_assumption_conditional_interval():
    r, x, y, w = _sim(8)
    iv = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w)
    d = search_countermodels(
        regimes=r,
        treatment=x,
        outcome=y,
        reference_beta=float(iv.beta_hat),
        beta_grid=np.linspace(-0.5, 2.0, 101),
        min_causal_shift=0.40,
        bounds=StructuralAssumptionBounds(max_direct_effect_l2=0.15),
    )
    interval = d.declared_direct_effect_beta_interval
    assert interval is not None and not interval.is_empty
    assert interval.width < 0.40
    assert d.material_countermodel_within_declared_bounds is False
    assert d.state == "ASSUMPTION_CONDITIONAL_IDENTIFICATION_COUNTERMODELS_OUTSIDE_BOUNDS"
