from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "experiments/research_s03_latent_dynamics/run.py"
spec = importlib.util.spec_from_file_location("s03_latent_dynamics", MODPATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_feature_dimensions_are_capacity_matched() -> None:
    a = np.arange(5, dtype=float)
    for kind in ("STATELESS", "DYNAMIC_HISTORY", "LEAKAGE_ORACLE"):
        X = mod.features(kind, a, a, a, a, a if kind == "LEAKAGE_ORACLE" else None)
        assert X.shape == (5, 4)


def test_admissible_features_do_not_accept_future_observation() -> None:
    a = np.arange(3, dtype=float)
    x1 = mod.features("DYNAMIC_HISTORY", a, a, a, a, np.array([99.0, 99.0, 99.0]))
    x2 = mod.features("DYNAMIC_HISTORY", a, a, a, a, np.array([-99.0, -99.0, -99.0]))
    np.testing.assert_allclose(x1, x2)


def test_hidden_velocity_system_is_deterministic_given_seed() -> None:
    x1, a1 = mod.simulate(123, 30, rho=0.8, action_scale=1.0)
    x2, a2 = mod.simulate(123, 30, rho=0.8, action_scale=1.0)
    np.testing.assert_allclose(x1, x2)
    np.testing.assert_allclose(a1, a2)
