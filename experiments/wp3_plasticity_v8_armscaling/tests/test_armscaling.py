"""Tests for L4f. The full analyze() is ~1.7 min, so the frozen verdict.json is asserted for
the scientific content and only a K=2 slice is recomputed as a determinism spot-check.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from experiments.wp3_plasticity_v8_armscaling.src import armscaling as A

VERDICT = json.loads((Path(A.OUT) / "verdict.json").read_text())


def test_verdict_arm_scaling_mapped():
    assert VERDICT["verdict"] == "L4F_ARM_SCALING_MAPPED"


def test_exponent_monotone_shallowing():
    exps = [VERDICT["exponents"][str(k)] for k in A.ARMS]
    assert not any(math.isnan(e) for e in exps)
    assert all(exps[i + 1] >= exps[i] - 0.10 for i in range(len(exps) - 1))   # monotone shallowing
    assert exps[-1] - exps[0] >= 0.25                                          # clearly shallows
    assert exps[0] <= -0.9                                                     # 2-arm drift limit


def test_two_arm_slice_reproduces_drift_limit():
    # cheap determinism / reproducibility spot-check: recompute only K=2
    dstar = {n: A._dstar(2, n) for n in A.BUDGETS}
    assert not any(math.isnan(v) for v in dstar.values())
    exp2 = A._loglog_slope(A.BUDGETS, [dstar[n] for n in A.BUDGETS])
    assert exp2 <= -0.9
    assert math.isclose(exp2, VERDICT["exponents"]["2"], abs_tol=1e-6)         # deterministic
