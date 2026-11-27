from __future__ import annotations

from fractions import Fraction
from itertools import product

import pytest

from cwc.epistemics.evidence_value import EvidenceProbe, robust_evidence_value

BASE_WEIGHTS = (Fraction(1, 2), Fraction(1, 2), 0, 0)
COST = Fraction(1, 10)
TARGET = Fraction(1, 2)
NOMINAL = ((0, 2, -2), (0, -2, 2))


def channels(reliability: Fraction) -> tuple[EvidenceProbe, EvidenceProbe]:
    good = (reliability, 1 - reliability)
    reverse = good[::-1]
    return (
        EvidenceProbe("A", COST, ((1, 0), (0, 1), (0, 1), (1, 0))),
        EvidenceProbe("B", COST, (good, reverse, good, reverse)),
    )


def scores_in_distribution(utilities, payoffs, distribution):
    informed = sum(p * u for p, u in zip(distribution, payoffs, strict=True))
    free = max(sum(p * u for p, u in zip(distribution, column, strict=True))
               for column in zip(*utilities, strict=True))
    return informed - free


def oracle(utilities, probes):
    """Find the last feasible point among affine intersections of actual mixtures."""
    candidates = []
    for probe in probes:
        for policy in product(range(3), repeat=2):
            payoffs = tuple(law[0] * row[policy[0]] + law[1] * row[policy[1]] - probe.cost
                            for law, row in zip(probe.laws, utilities, strict=True))
            initial = scores_in_distribution(utilities, payoffs, BASE_WEIGHTS)
            if initial < TARGET:
                continue
            endpoints = {Fraction(0), Fraction(1)}
            for action in range(3):
                initial_gain = sum(BASE_WEIGHTS[w] * (payoffs[w] - utilities[w][action]) for w in range(4))
                for challenge in (2, 3):
                    end_gain = payoffs[challenge] - utilities[challenge][action]
                    if end_gain != initial_gain:
                        crossing = (TARGET - initial_gain) / (end_gain - initial_gain)
                        if 0 <= crossing <= 1:
                            endpoints.add(Fraction(crossing))
            accepted = []
            for epsilon in endpoints:
                distributions = (
                    ((1 - epsilon) / 2, (1 - epsilon) / 2, epsilon, 0),
                    ((1 - epsilon) / 2, (1 - epsilon) / 2, 0, epsilon),
                )
                if all(scores_in_distribution(utilities, payoffs, d) >= TARGET for d in distributions):
                    accepted.append(epsilon)
            candidates.append((max(accepted), initial, probe.probe_id, policy))
    robust = min(candidates, key=lambda r: (-r[0], -r[1], r[2], r[3]))
    nominal = min(candidates, key=lambda r: (-r[1], -r[0], r[2], r[3]))
    return robust, nominal


def test_reliable_probe_beats_nominally_perfect_brittle_probe() -> None:
    result = robust_evidence_value(
        utilities=NOMINAL + NOMINAL, nominal_weights=BASE_WEIGHTS,
        probes=channels(Fraction(4, 5)), target_advantage=TARGET,
    )
    assert result.robust_first is not None and result.nominal_first is not None
    assert (result.robust_first.probe_id, result.robust_first.radius) == ("B", Fraction(3, 10))
    assert (result.nominal_first.probe_id, result.nominal_first.radius) == ("A", Fraction(7, 30))
    assert result.evaluated_policies == 18


def test_uninformative_coin_cannot_look_beneficial_against_all_free_actions() -> None:
    coin = EvidenceProbe("coin", COST, ((Fraction(1, 2), Fraction(1, 2)),) * 4)
    shifted = ((0, 3, -1), (0, -1, 3)) * 2
    result = robust_evidence_value(
        utilities=shifted, nominal_weights=BASE_WEIGHTS, probes=[coin], target_advantage=TARGET,
    )
    assert result.robust_first is None and result.nominal_first is None


def test_zero_radius_is_distinct_from_an_empty_feasible_set() -> None:
    kwargs = {"utilities": NOMINAL + NOMINAL, "nominal_weights": BASE_WEIGHTS,
              "probes": channels(Fraction(4, 5))[:1]}
    zero = robust_evidence_value(target_advantage=Fraction(19, 10), **kwargs)
    assert zero.robust_first is not None and zero.robust_first.radius == 0
    empty = robust_evidence_value(target_advantage=2, **kwargs)
    assert empty.robust_first is None


def test_renaming_observations_preserves_value_and_reverses_actions() -> None:
    original = channels(Fraction(4, 5))[1]
    inverted = EvidenceProbe(original.probe_id, original.cost, tuple(row[::-1] for row in original.laws))
    kwargs = {"utilities": NOMINAL + NOMINAL, "nominal_weights": BASE_WEIGHTS,
              "target_advantage": TARGET}
    first = robust_evidence_value(probes=[original], **kwargs).robust_first
    second = robust_evidence_value(probes=[inverted], **kwargs).robust_first
    assert first is not None and second is not None
    assert (first.radius, first.nominal_advantage) == (second.radius, second.nominal_advantage)
    assert first.outcome_actions == second.outcome_actions[::-1]


def test_outside_challenge_world_can_invalidate_the_claimed_radius() -> None:
    probe = channels(Fraction(4, 5))[1]
    initial = robust_evidence_value(
        utilities=NOMINAL + NOMINAL, nominal_weights=BASE_WEIGHTS, probes=[probe], target_advantage=TARGET,
    ).robust_first
    extension = robust_evidence_value(
        utilities=(*NOMINAL, *NOMINAL, (0, -100, 100)),
        nominal_weights=(*BASE_WEIGHTS, 0),
        probes=[EvidenceProbe(probe.probe_id, probe.cost, (*probe.laws, (1, 0)))],
        target_advantage=TARGET,
    ).robust_first
    assert extension is not None and initial is not None
    assert extension.radius < initial.radius


@pytest.mark.parametrize("probe", [
    EvidenceProbe("boolean", True, ((1, 0),) * 4),
    EvidenceProbe("mass", COST, ((1, 1),) * 4),
    EvidenceProbe("roster", COST, ((1, 0),)),
])
def test_malformed_input_fails_closed(probe: EvidenceProbe) -> None:
    with pytest.raises(ValueError):
        robust_evidence_value(
            utilities=NOMINAL + NOMINAL, nominal_weights=BASE_WEIGHTS,
            probes=[probe], target_advantage=TARGET,
        )


def test_frozen_panel_matches_independent_extreme_distribution_oracle() -> None:
    altered_probe = radius_gain = reduced_margin = count = 0
    for a, b, c, d in product((-2, 0, 2), repeat=4):
        utilities = (*NOMINAL, (0, a, b), (0, c, d))
        for probability in (Fraction(3, 4), Fraction(4, 5), Fraction(9, 10)):
            probes = channels(probability)
            actual = robust_evidence_value(
                utilities=utilities, nominal_weights=BASE_WEIGHTS, probes=probes, target_advantage=TARGET,
            )
            assert actual.robust_first is not None and actual.nominal_first is not None
            robust, nominal = actual.robust_first, actual.nominal_first
            reference_robust, reference_nominal = oracle(utilities, probes)
            for selected, reference in ((robust, reference_robust), (nominal, reference_nominal)):
                assert (selected.radius, selected.nominal_advantage,
                        selected.probe_id, selected.outcome_actions) == reference
            altered_probe += int(robust.probe_id != nominal.probe_id)
            radius_gain += int(robust.radius > nominal.radius)
            reduced_margin += int(robust.nominal_advantage < nominal.nominal_advantage)
            count += 1
    assert (count, altered_probe, radius_gain, reduced_margin) == (243, 44, 100, 100)
