from experiments.wp4_adaptive_depth.src.analyze_exact_compute_v3 import (
    exact_positive_randomization_p,
    holm_adjust,
)


def test_exact_randomization_detects_all_positive_pairs():
    assert exact_positive_randomization_p([1.0] * 4) == 1 / 16


def test_exact_randomization_rejects_empty_input():
    try:
        exact_positive_randomization_p([])
    except ValueError:
        pass
    else:
        raise AssertionError("empty randomization input accepted")


def test_holm_adjustment_is_monotone_and_bounded():
    adjusted = holm_adjust({"a": 0.001, "b": 0.02, "c": 0.5})
    assert 0 <= adjusted["a"] <= adjusted["b"] <= adjusted["c"] <= 1
