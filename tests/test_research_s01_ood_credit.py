from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "experiments/research_s01_ood_credit/run.py"
spec = importlib.util.spec_from_file_location("s01_ood_credit", MODPATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_noncauses_have_zero_exact_shapley_credit() -> None:
    row = mod.Row(A=1, C=1, D=1, B=1, U=1, epsilon=0.37, gamma=2.0)
    phi, _, err = mod.exact_shapley(row)
    assert abs(phi["A"] - 0.5) <= 1e-12
    assert abs(phi["C"]) <= 1e-12
    assert abs(phi["D"]) <= 1e-12
    assert abs(phi["B"]) <= 1e-12
    assert err <= 1e-12


def test_correlated_readout_is_observational_not_structural_parent() -> None:
    y0 = mod.structural_y(A=1, C=0, D=0, B=0, U=1, epsilon=0.0, gamma=2.0)
    y1 = mod.structural_y(A=1, C=1, D=0, B=0, U=1, epsilon=0.0, gamma=2.0)
    assert y0 == y1


def test_true_cause_intervention_changes_expected_outcome() -> None:
    row = mod.Row(A=1, C=1, D=0, B=0, U=1, epsilon=0.0, gamma=2.0)
    empty, _ = mod.coalition_value(row, frozenset())
    a_only, _ = mod.coalition_value(row, frozenset({"A"}))
    assert abs(empty) <= 1e-12
    assert a_only > 0
