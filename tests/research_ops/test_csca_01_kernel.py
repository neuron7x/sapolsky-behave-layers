from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "experiments/csca_01/run.py"
spec = importlib.util.spec_from_file_location("csca01", PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_exact_kernel_assigns_zero_to_noncauses() -> None:
    row = mod.Row(A=1, C=1, D=-1, B=1, U=1, epsilon=0.4, beta=1.0, gamma=2.0)
    phi, _, error = mod.exact_shapley(row)
    assert abs(phi["A"] - 1.0) <= 1e-12
    assert abs(phi["C"]) <= 1e-12
    assert abs(phi["D"]) <= 1e-12
    assert abs(phi["B"]) <= 1e-12
    assert error <= 1e-12


def test_destroyed_link_zeroes_exact_credit() -> None:
    row = mod.Row(A=1, C=1, D=-1, B=1, U=1, epsilon=0.4, beta=0.0, gamma=2.0)
    phi, _, _ = mod.exact_shapley(row)
    assert max(abs(v) for v in phi.values()) <= 1e-12


def test_mc_estimator_is_deterministic_for_fixed_rng() -> None:
    row = mod.Row(A=-1, C=1, D=-1, B=-1, U=1, epsilon=0.2, beta=1.0, gamma=0.25)
    a, ea = mod.mc_permutation_shapley(row, permutations=16, rng=random.Random(123))
    b, eb = mod.mc_permutation_shapley(row, permutations=16, rng=random.Random(123))
    assert a == b
    assert ea == eb
