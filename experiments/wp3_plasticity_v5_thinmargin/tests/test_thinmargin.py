"""Tests for L4c — lock in the FROZEN FALSIFICATION deterministically.

The preregistered (sigma/Delta)^2 scaling prediction was refuted; these tests pin that
negative so a future change cannot silently 'improve' it into an unearned positive.
"""
from __future__ import annotations

from experiments.wp3_plasticity_v5_thinmargin.src import thinmargin as T


def _r():
    return T.analyze()


def test_verdict_scaling_violated_and_deterministic():
    r1, r2 = _r(), _r()
    assert r1 == r2
    assert r1["verdict"] == "L4C_SCALING_VIOLATED"


def test_collapse_exists():
    r = _r()
    for k in r["curves"]:
        recs = [c["recovery"] for c in r["curves"][k]]
        assert recs[0] >= 0.9            # wide margin -> learned
        assert recs[-1] <= 0.5           # thin margin -> degraded


def test_sqrt_law_scaling_is_refuted():
    r = _r()
    assert r["sqrt_law_scaling_holds"] is False
    # noise-independence tell: ratio well below the predicted ~2
    assert r["scaling_ratio_2sigma_over_sigma"] < 1.4


def test_noise_does_not_monotonically_hurt():
    # the falsifying observation: at Delta=0.05 more noise did not reduce recovery
    r = _r()
    d05_lo = next(c["recovery"] for c in r["curves"]["sigma_0.10"] if c["delta"] == 0.05)
    d05_hi = next(c["recovery"] for c in r["curves"]["sigma_0.20"] if c["delta"] == 0.05)
    assert d05_hi >= d05_lo - 0.05       # 2x noise not worse (contra (sigma/Delta)^2)
