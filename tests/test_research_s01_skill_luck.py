from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "experiments/research_s01_skill_luck/run.py"
spec = importlib.util.spec_from_file_location("s01_skill_luck", MODPATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_luck_terminal_action_gets_zero_counterfactual_credit() -> None:
    luck = mod.Trajectory(1, 1, 1)
    assert mod.shapley(luck)[2] == 0


def test_skill_terminal_action_gets_positive_credit() -> None:
    skill = mod.Trajectory(0, 1, 1)
    assert mod.shapley(skill)[2] > 0


def test_shapley_efficiency() -> None:
    for obs in (mod.Trajectory(0, 1, 1), mod.Trajectory(1, 1, 1)):
        phi = mod.shapley(obs)
        assert phi[1] + phi[2] == phi["f_all"]
