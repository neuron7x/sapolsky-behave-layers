from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci


def test_bootstrap_is_reproducible_but_not_degenerate_for_n8():
    values = [0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8]
    first = _bootstrap_ci(values, iters=2000, seed=17)
    second = _bootstrap_ci(values, iters=2000, seed=17)
    assert first == second
    assert first[0] < first[1]


def test_bootstrap_constant_input_is_exact():
    assert _bootstrap_ci([0.25] * 8, iters=500, seed=3) == (0.25, 0.25)
