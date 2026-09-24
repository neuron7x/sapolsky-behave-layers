from __future__ import annotations

import math

import pytest

from cwc.governance.average_conditional_mean_cs import (
    ASSUMPTION_BOUNDARY,
    BOUNDARY_C,
    BOUNDARY_METHOD,
    BOUNDARY_PARAMETER_DIGEST,
    CONFSEQ_REFERENCE_COMMIT,
    ETA,
    METHOD,
    PREDICTOR_RULE,
    S,
    V_MIN,
    ZETA_S,
    ZETA_S_HEX,
    average_conditional_mean_bound,
    boundary_parameter_payload,
    certify_multi_baseline_anytime_valid,
    polynomial_stitching_boundary,
)
from cwc.governance.pareto import PairedBaselineEvidence


def evidence(baseline_id: str, *, n: int, cost: float = 0.2, quality: float = 0.0, regret: float = 0.0):
    return PairedBaselineEvidence(
        baseline_id=baseline_id,
        paired_task_digest="a" * 64,
        coverage=1.0,
        baseline_minus_dgc_cost=(cost,) * n,
        dgc_minus_baseline_quality=(quality,) * n,
        baseline_minus_dgc_catastrophic_regret=(regret,) * n,
        cost_gain_support=(-1.0, 1.0),
        quality_gain_support=(-1.0, 1.0),
        catastrophic_gain_support=(-1.0, 1.0),
    )


def test_polynomial_stitching_matches_authors_confseq_reference_vector():
    # gostevehoward/confseq commit 5ffe733..., uniform_boundaries_unittest.cpp:
    # poly_stitching_bound(100, 0.05, 10, 3) == 64.48755 +/- 1e-5.
    observed = polynomial_stitching_boundary(
        100.0,
        crossing_alpha=0.05,
        v_min=10.0,
        c=3.0,
    )
    assert CONFSEQ_REFERENCE_COMMIT == "5ffe733ca2447a2e28c2c91f3b00086173f2ab2c"
    assert observed == pytest.approx(64.48755, abs=1e-5)


def test_boundary_parameter_identity_matches_author_reference_binary64():
    # boost::math::zeta(1.4) on the pinned confseq implementation path is
    # frozen by its binary64 hex representation, not by a rounded decimal string.
    assert ZETA_S_HEX == "0x1.8d8292bd8c3a6p+1"
    assert ZETA_S.hex() == ZETA_S_HEX
    assert ZETA_S == 3.105547277977581
    assert ETA == 2.0
    assert S == 1.4
    assert V_MIN == 1.0
    assert BOUNDARY_C == 1.0
    assert BOUNDARY_PARAMETER_DIGEST == "4deabb17370edfc770b7612235ee9dfddf932dfc21e894161fb2757ea45a1329"
    assert boundary_parameter_payload() == {
        "eta": 2.0,
        "s": 1.4,
        "v_min": 1.0,
        "c": 1.0,
        "zeta_s_binary64_hex": "0x1.8d8292bd8c3a6p+1",
    }
    assert BOUNDARY_PARAMETER_DIGEST[:16] in BOUNDARY_METHOD


def test_terminal_slice_matches_exact_polynomial_stitching_formula():
    result = average_conditional_mean_bound(
        (0.1,) * 1000,
        lower=-1.0,
        upper=1.0,
        alpha=0.05 / 24.0,
    )
    assert result.method == METHOD
    assert result.boundary_method == BOUNDARY_METHOD
    assert result.predictor_rule == PREDICTOR_RULE
    assert result.assumption_boundary == ASSUMPTION_BOUNDARY
    assert result.sample_mean == pytest.approx(0.1)
    assert result.boundary_crossing_alpha == pytest.approx((0.05 / 24.0) / 2.0)
    assert result.half_width == pytest.approx(0.040265687829903966, abs=1e-15)
    assert result.lower == pytest.approx(0.05973431217009604, abs=1e-15)


def test_removed_v1_shortcut_was_anti_conservative_and_cannot_return():
    # The invalid shortcut k1*sqrt(v*ell)+k2*c*ell omits (k2*c*ell)^2 under
    # the canonical square root. This regression test makes that mutation visible.
    v = 1.0
    crossing_alpha = 0.01
    log_eta = math.log(ETA)
    ell = S * math.log(math.log(ETA * v)) + math.log(ZETA_S / (crossing_alpha * (log_eta ** S)))
    k1 = (ETA ** 0.25 + ETA ** -0.25) / math.sqrt(2.0)
    k2 = (math.sqrt(ETA) + 1.0) / 2.0
    invalid_shortcut = k1 * math.sqrt(v * ell) + k2 * ell
    canonical = polynomial_stitching_boundary(v, crossing_alpha=crossing_alpha)
    assert canonical > invalid_shortcut


def test_bound_shrinks_with_more_low_variance_observations_without_iid_claim():
    small = average_conditional_mean_bound((0.1,) * 100, lower=-1.0, upper=1.0, alpha=0.01)
    large = average_conditional_mean_bound((0.1,) * 1000, lower=-1.0, upper=1.0, alpha=0.01)
    assert large.half_width < small.half_width
    assert "NO_IID_REQUIRED" in large.assumption_boundary


def test_stricter_alpha_produces_no_narrower_interval():
    loose = average_conditional_mean_bound((0.1, 0.2, 0.3, 0.4) * 100, lower=0.0, upper=1.0, alpha=0.05)
    strict = average_conditional_mean_bound((0.1, 0.2, 0.3, 0.4) * 100, lower=0.0, upper=1.0, alpha=0.001)
    assert strict.half_width >= loose.half_width


def test_affine_rescaling_is_equivariant():
    source = (0.1, 0.2, 0.3, 0.4) * 100
    base = average_conditional_mean_bound(source, lower=0.0, upper=1.0, alpha=0.01)
    scaled_values = tuple(10.0 + 4.0 * x for x in source)
    scaled = average_conditional_mean_bound(scaled_values, lower=10.0, upper=14.0, alpha=0.01)
    assert scaled.sample_mean == pytest.approx(10.0 + 4.0 * base.sample_mean)
    assert scaled.lower == pytest.approx(10.0 + 4.0 * base.lower)
    assert scaled.upper == pytest.approx(10.0 + 4.0 * base.upper)
    assert scaled.half_width == pytest.approx(4.0 * base.half_width)


def test_support_alpha_and_boundary_inputs_fail_closed():
    with pytest.raises(ValueError, match="outside declared support"):
        average_conditional_mean_bound((0.0, 1.1), lower=0.0, upper=1.0, alpha=0.01)
    with pytest.raises(ValueError, match="alpha"):
        average_conditional_mean_bound((0.0, 0.1), lower=0.0, upper=1.0, alpha=1.0)
    with pytest.raises(ValueError, match="crossing_alpha"):
        polynomial_stitching_boundary(1.0, crossing_alpha=0.0)
    with pytest.raises(ValueError, match="variance_process"):
        polynomial_stitching_boundary(-1.0, crossing_alpha=0.01)


def test_multi_baseline_union_allocation_is_exact():
    cert = certify_multi_baseline_anytime_valid(
        tuple(evidence(f"B{i}", n=20000) for i in range(4)),
        alpha=0.025,
        quality_noninferiority_margin=0.02,
        catastrophic_noninferiority_margin=0.01,
    )
    assert cert.per_metric_alpha == pytest.approx(0.025 / 12.0)
    assert all(
        row.cost_gain.boundary_crossing_alpha == pytest.approx((0.025 / 12.0) / 2.0)
        for row in cert.results
    )
    assert cert.all_baselines_certified is True
    assert len(cert.results) == 4


def test_small_population_does_not_manufacture_support():
    cert = certify_multi_baseline_anytime_valid(
        tuple(evidence(f"B{i}", n=10, cost=0.01) for i in range(4)),
        alpha=0.025,
        quality_noninferiority_margin=0.02,
        catastrophic_noninferiority_margin=0.01,
    )
    assert cert.all_baselines_certified is False
