"""Accounting test for the backend-sensitive adaptive-depth transformer pilot.

The analytic oracle dominates at matched compute, but independently trained finite
models do not inherit that theorem. This test therefore validates the reported
quantities without turning an empirical performance hypothesis into an invariant.
"""
from experiments.act_j_pilot.src.transformer_depth import run


def test_adaptive_depth_reports_compute_matched_outcome_without_assuming_its_sign():
    r = run(steps=2500, eval_batch=600, seed=0)
    assert abs(r.compute_matched_gain - (r.adaptive_accuracy - r.static_matched_accuracy)) < 1e-12
    assert abs(r.adaptive_compute - 3.5) < 1e-9
    for value in (
        r.adaptive_accuracy,
        r.static_shallow_accuracy,
        r.static_deep_accuracy,
        r.static_matched_accuracy,
        r.shallow_on_hard,
    ):
        assert 0.0 <= value <= 1.0
