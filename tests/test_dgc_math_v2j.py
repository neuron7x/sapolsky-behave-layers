from __future__ import annotations

import pytest

from cwc.governance.finite_strata_transport import target_mean_lcb_under_finite_strata_shift


def _cert(source_values, source_strata, target_strata, **kwargs):
    return target_mean_lcb_under_finite_strata_shift(
        source_values,
        source_strata,
        target_strata,
        lower=0.0,
        upper=1.0,
        delta=0.05,
        conditional_mean_invariance_attested=True,
        source_target_independence_attested=True,
        stratum_schema_digest="schema-v1",
        invariance_authority_digest="invariance-v1",
        **kwargs,
    )


def test_ratio_free_transport_tracks_target_mix():
    n = 400
    source_values = [0.0] * n + [1.0] * n
    source_strata = ["low"] * n + ["high"] * n
    target_strata = ["high"] * 380 + ["low"] * 20
    cert = _cert(source_values, source_strata, target_strata)
    assert cert.target_mean_lower > 0.80
    assert cert.strata_count == 2


def test_target_shift_toward_low_stratum_prevents_source_mean_overclaim():
    n = 400
    source_values = [0.0] * n + [1.0] * n
    source_strata = ["low"] * n + ["high"] * n
    target_strata = ["low"] * 380 + ["high"] * 20
    cert = _cert(source_values, source_strata, target_strata)
    assert cert.target_mean_lower < 0.1


def test_unseen_target_stratum_fails_closed():
    with pytest.raises(ValueError, match="positivity/support failure"):
        _cert([0.5, 0.6], ["seen", "seen"], ["seen", "new"])


def test_invariance_and_independence_are_mandatory_authorities():
    base = dict(
        source_values=[0.5, 0.6],
        source_strata=["a", "a"],
        target_strata=["a", "a"],
        lower=0.0,
        upper=1.0,
        delta=0.05,
        stratum_schema_digest="schema",
        invariance_authority_digest="inv",
    )
    with pytest.raises(ValueError, match="invariance"):
        target_mean_lcb_under_finite_strata_shift(
            **base,
            conditional_mean_invariance_attested=False,
            source_target_independence_attested=True,
        )
    with pytest.raises(ValueError, match="independence"):
        target_mean_lcb_under_finite_strata_shift(
            **base,
            conditional_mean_invariance_attested=True,
            source_target_independence_attested=False,
        )


def test_more_data_tightens_lower_bound():
    small = _cert([1.0] * 20, ["a"] * 20, ["a"] * 20)
    large = _cert([1.0] * 1000, ["a"] * 1000, ["a"] * 1000)
    assert large.target_mean_lower > small.target_mean_lower
    assert large.target_mean_lower > 0.9


def test_sparse_target_observed_source_stratum_is_conservative():
    cert = _cert(
        [1.0] * 100 + [1.0],
        ["dense"] * 100 + ["sparse"],
        ["sparse"] * 100,
    )
    assert cert.target_mean_lower == 0.0


def test_certificate_digest_is_deterministic():
    args = ([0.2, 0.8, 0.3, 0.9], ["a", "b", "a", "b"], ["a", "b", "b", "a"])
    first = _cert(*args)
    second = _cert(*args)
    assert first.certificate_digest == second.certificate_digest
