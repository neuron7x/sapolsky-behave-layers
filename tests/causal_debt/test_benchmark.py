from __future__ import annotations

import random

from experiments.causal_debt_v1.run import counterfactual_probe, observational_effect, sample_unit


def test_scm_counterfactual_separates_cause_from_spurious() -> None:
    rng = random.Random(123)
    c_effect = 0.0
    s_effect = 0.0
    n = 2000
    for _ in range(n):
        unit = sample_unit(rng, "same")
        c_effect += counterfactual_probe(unit, "C").signed_effect
        s_effect += counterfactual_probe(unit, "S").signed_effect
    assert c_effect / n > 0.7
    assert s_effect == 0.0


def test_spurious_observational_association_changes_by_context() -> None:
    rng = random.Random(321)
    same = [sample_unit(rng, "same") for _ in range(4000)]
    reversed_units = [sample_unit(rng, "reversed") for _ in range(4000)]
    assert observational_effect(same, "S") > 0.6
    assert observational_effect(reversed_units, "S") < -0.6
    assert observational_effect(same, "C") > 0.6
    assert observational_effect(reversed_units, "C") > 0.6
