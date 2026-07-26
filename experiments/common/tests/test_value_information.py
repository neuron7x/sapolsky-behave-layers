import itertools
import random

import pytest

from experiments.common.value_information import information_value_certificate


def test_independent_signal_has_zero_value_and_information():
    result = information_value_certificate([[0.25, 0.25], [0.25, 0.25]], [[1.0, 0.0], [0.0, 1.0]])
    assert result["gross_value"] == pytest.approx(0.0)
    assert result["mutual_information_nats"] == pytest.approx(0.0)


def test_perfect_signal_can_be_net_negative_after_cost():
    result = information_value_certificate([[0.5, 0.0], [0.0, 0.5]], [[1.0, 0.0], [0.0, 1.0]], route_cost=0.6)
    assert result["gross_value"] == pytest.approx(0.5)
    assert result["net_value"] == pytest.approx(-0.1)
    assert result["bound_holds"] is True


def test_bound_holds_over_exhaustive_joint_grid():
    utility = [[0.0, 0.3, 1.0], [0.7, -0.2, 0.4]]
    for masses in itertools.product(range(4), repeat=4):
        total = sum(masses)
        if total:
            joint = [[masses[0] / total, masses[1] / total], [masses[2] / total, masses[3] / total]]
            assert information_value_certificate(joint, utility)["bound_holds"] is True


def test_bound_holds_under_seeded_adversarial_search():
    rng = random.Random(20260720)
    for _ in range(1000):
        masses = [rng.expovariate(1.0) for _ in range(12)]
        total = sum(masses)
        joint = [[masses[4 * c + z] / total for z in range(4)] for c in range(3)]
        utility = [[rng.uniform(-5, 7) for _ in range(5)] for _ in range(3)]
        assert information_value_certificate(joint, utility)["bound_holds"] is True


def test_signal_permutation_and_independent_refinement_are_invariant():
    joint = [[0.30, 0.10], [0.05, 0.55]]
    utility = [[1.0, -0.2], [0.1, 1.4]]
    baseline = information_value_certificate(joint, utility)
    permuted = information_value_certificate(
        [[row[1], row[0]] for row in joint], utility
    )
    refined = information_value_certificate(
        [[0.4 * row[0], 0.6 * row[0], row[1]] for row in joint], utility
    )
    for key in (
        "prior_value",
        "informed_value",
        "gross_value",
        "mutual_information_nats",
        "information_upper_bound",
    ):
        assert permuted[key] == pytest.approx(baseline[key], abs=1e-12)
        assert refined[key] == pytest.approx(baseline[key], abs=1e-12)


@pytest.mark.parametrize(
    "joint,utility",
    [
        ([], [[1.0]]),
        ([[0.4, 0.4]], [[1.0]]),
        ([[0.5, -0.5], [0.5, 0.5]], [[1.0], [0.0]]),
    ],
)
def test_malformed_problems_fail_closed(joint, utility):
    with pytest.raises(ValueError):
        information_value_certificate(joint, utility)
