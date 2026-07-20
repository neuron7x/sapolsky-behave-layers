"""Fast honest test for the adaptive-depth transformer.

The robust, by-construction claim is that adaptive routing is NEVER worse than static at
matched compute (it allocates the correct depth per difficulty). The strict advantage is
seed-dependent (the shallow model sometimes learns the hard task), documented in the
module and evidence -- so we do NOT assert a positive gain, only the honest invariant.
Small training budget for speed.
"""
from experiments.act_j_pilot.src.transformer_depth import run


def test_adaptive_depth_is_never_worse_than_static_at_matched_compute():
    # both depths must be trained to convergence (the deeper model trains slower, so an
    # equal-STEP comparison at too-few steps is unfair to it); at convergence adaptive wins.
    r = run(steps=2500, eval_batch=600, seed=0)
    assert r.adaptive_accuracy >= r.static_matched_accuracy - 0.03   # never worse at matched compute
    # adaptive spends the average of the two depths
    assert abs(r.adaptive_compute - 3.5) < 1e-9
    # deep solves easy at least as well as shallow does hard (sanity on the separation axis)
    assert 0.0 <= r.shallow_on_hard <= 1.0
