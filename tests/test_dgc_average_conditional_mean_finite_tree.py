from __future__ import annotations

from cwc.governance.average_conditional_mean_cs import average_conditional_mean_bound


def _exact_crossing_probability(*, horizon: int, alpha: float) -> float:
    """Enumerate the full binary tree of a history-adapted bounded process.

    X_t is Bernoulli with p_t=0.5 initially, then p_t=0.8 after a zero and
    p_t=0.2 after a one.  The observations are therefore non-iid and their
    conditional distribution is explicitly history-dependent.  We accumulate
    exact path probabilities for the event that the true running average
    conditional mean exits the V5 confidence sequence at any t <= horizon.

    This is a deterministic finite-horizon falsifier, not a proof of the theorem.
    """
    crossing_probability = 0.0

    def visit(
        observations: tuple[float, ...],
        conditional_means: tuple[float, ...],
        path_probability: float,
        crossed: bool,
    ) -> None:
        nonlocal crossing_probability
        t = len(observations)
        if t:
            interval = average_conditional_mean_bound(
                observations,
                lower=0.0,
                upper=1.0,
                alpha=alpha,
            )
            true_average_conditional_mean = sum(conditional_means) / t
            crossed = crossed or not (
                interval.lower - 1e-15
                <= true_average_conditional_mean
                <= interval.upper + 1e-15
            )
        if t == horizon:
            if crossed:
                crossing_probability += path_probability
            return

        if not observations:
            p_next = 0.5
        else:
            p_next = 0.8 if observations[-1] == 0.0 else 0.2
        visit(
            observations + (1.0,),
            conditional_means + (p_next,),
            path_probability * p_next,
            crossed,
        )
        visit(
            observations + (0.0,),
            conditional_means + (p_next,),
            path_probability * (1.0 - p_next),
            crossed,
        )

    visit((), (), 1.0, False)
    return crossing_probability


def test_exact_finite_tree_adapted_process_crossing_probability_is_below_alpha():
    alpha = 0.10
    probability = _exact_crossing_probability(horizon=14, alpha=alpha)
    # The exact finite tree contains 2^14 leaves and has a nonzero crossing event,
    # so this checks more than the vacuous "no path crossed" case.
    assert probability > 0.0
    assert probability <= alpha + 1e-15
    assert probability == 8.191999999999991e-10


def test_stricter_confidence_level_does_not_increase_exact_tree_crossing_probability():
    loose = _exact_crossing_probability(horizon=14, alpha=0.10)
    strict = _exact_crossing_probability(horizon=14, alpha=0.05)
    assert strict <= loose + 1e-15
    assert strict == 0.0
