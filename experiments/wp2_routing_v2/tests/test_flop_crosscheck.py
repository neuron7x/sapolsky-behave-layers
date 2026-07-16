"""Fast structural test for the Act B2 profiler FLOP cross-check.

Uses a tiny batch on CPU. Asserts the JSON payload is produced with the
required structure and that e_F is a finite float in [0, 1] for every module.
Does NOT require the gate to PASS — attention coverage gaps are expected.
"""
from __future__ import annotations

import math

from scripts.flop_profiler_crosscheck import compute_crosscheck


def test_crosscheck_structure_and_bounded_e_f():
    result = compute_crosscheck(batch_size=4, device="cpu", seed=0)

    assert result["FLOPS_STATUS"] in ("PASS", "PARTIALLY_ESTIMATED")
    assert result["batch_size"] == 4
    assert result["device"] == "cpu"

    conv = result["profiler_convention"]
    assert conv["profiler_to_logical_multiplier"] in (1, 2)
    assert math.isfinite(conv["calibration_ratio_raw_over_mac"])

    modules = result["modules"]
    assert set(modules) == {"DirectPath", "SemanticParser", "SemanticRenderer"}

    for name, m in modules.items():
        e_f = m["e_F"]
        assert isinstance(e_f, float), name
        assert math.isfinite(e_f), name
        assert 0.0 <= e_f <= 1.0, (name, e_f)
        assert m["F_logical"] > 0, name
        assert m["F_profiler_raw"] >= 0, name
        assert m["F_profiler_adjusted"] == m["F_profiler_raw"] * conv["profiler_to_logical_multiplier"]
        assert isinstance(m["profiler_uncounted_compute_ops"], list)
