from __future__ import annotations

from cwc.replay.stats import exact_max_t_fwer


def test_exact_max_t_detects_strong_paired_positive_effect() -> None:
    diffs_a = [1.0 + i * 0.01 for i in range(10)]
    diffs_b = [0.8 + i * 0.01 for i in range(10)]
    p_a, p_b = exact_max_t_fwer([diffs_a, diffs_b])
    assert p_a <= 0.01
    assert p_b <= 0.01


def test_exact_max_t_preserves_familywise_penalty() -> None:
    diffs_a = [0.1, -0.1, 0.1, -0.1]
    diffs_b = [0.0, 0.0, 0.0, 0.0]
    p_a, p_b = exact_max_t_fwer([diffs_a, diffs_b])
    assert 0.0 <= p_a <= 1.0
    assert 0.0 <= p_b <= 1.0
