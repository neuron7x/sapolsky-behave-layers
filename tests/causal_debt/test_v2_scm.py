from __future__ import annotations

import random

from experiments.causal_debt_v2.run import counterfactual_probe, observational_effect, sample_unit


def test_descendant_spurious_is_more_observationally_salient_but_noncausal() -> None:
    rng = random.Random(1234)
    units = [sample_unit(rng, variant="descendant", context="same") for _ in range(10000)]
    c_obs = abs(observational_effect(units, "C"))
    s_obs = abs(observational_effect(units, "S"))
    assert s_obs > c_obs
    assert all(counterfactual_probe(u, "S").signed_effect == 0.0 for u in units[:1000])


def test_proxy_environment_keeps_causal_feature_strong() -> None:
    rng = random.Random(4321)
    units = [sample_unit(rng, variant="proxy", context="same") for _ in range(10000)]
    assert observational_effect(units, "C") > 0.7
    assert observational_effect(units, "S") > 0.6
