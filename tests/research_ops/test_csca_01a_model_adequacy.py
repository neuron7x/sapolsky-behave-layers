from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "experiments/csca_01a_model_adequacy/run.py"
spec = importlib.util.spec_from_file_location("csca01a", PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_spurious_model_edge_creates_spurious_shapley_credit() -> None:
    phi = mod.shapley(A=1, C=-1, beta_hat=1.0, alpha=0.25)
    assert abs(abs(phi["A"]) - 1.0) <= 1e-12
    assert abs(abs(phi["C"]) - 0.25) <= 1e-12


def test_spurious_model_edge_can_reverse_credit_ranking() -> None:
    phi = mod.shapley(A=1, C=1, beta_hat=0.5, alpha=1.25)
    assert abs(phi["C"]) > abs(phi["A"])
