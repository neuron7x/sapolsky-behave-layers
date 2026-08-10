from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/research-s01-skill-luck"


@dataclass(frozen=True)
class Trajectory:
    x1: int
    x2: int
    u: int

    @property
    def branch(self) -> str:
        return "skill" if self.x1 == 0 else "luck"

    @property
    def y(self) -> int:
        return self.x2 if self.x1 == 0 else self.u


def outcome(x1: int, x2: int, u: int) -> int:
    return x2 if x1 == 0 else u


def counterfactual_expected_y(obs: Trajectory, coalition: frozenset[int]) -> Fraction:
    """Exact counterfactual expectation for players 1 and 2.

    Intervened actions use uniform baseline. If X1 changes the branch and X2 is not
    intervened, X2 is resampled from the uniform current policy because its state
    parent differs from the observed trajectory. Exogenous luck U is reused on the
    unchanged Luck parent configuration and irrelevant on Skill.
    """
    total = Fraction(0, 1)
    mass = Fraction(0, 1)
    x1_choices = [(obs.x1, Fraction(1, 1))] if 1 not in coalition else [(0, Fraction(1, 2)), (1, Fraction(1, 2))]
    for x1, p1 in x1_choices:
        branch_changed = x1 != obs.x1
        if 2 in coalition or branch_changed:
            x2_choices = [(0, Fraction(1, 2)), (1, Fraction(1, 2))]
        else:
            x2_choices = [(obs.x2, Fraction(1, 1))]
        for x2, p2 in x2_choices:
            p = p1 * p2
            total += p * outcome(x1, x2, obs.u)
            mass += p
    assert mass == 1
    return total


def contribution(obs: Trajectory, coalition: frozenset[int]) -> Fraction:
    return Fraction(obs.y, 1) - counterfactual_expected_y(obs, coalition)


def shapley(obs: Trajectory) -> dict[int, Fraction]:
    players = (1, 2)
    f = {frozenset(s): contribution(obs, frozenset(s)) for r in range(3) for s in itertools.combinations(players, r)}
    # Two-player exact Shapley.
    phi1 = Fraction(1, 2) * ((f[frozenset({1})] - f[frozenset()]) + (f[frozenset({1, 2})] - f[frozenset({2})]))
    phi2 = Fraction(1, 2) * ((f[frozenset({2})] - f[frozenset()]) + (f[frozenset({1, 2})] - f[frozenset({1})]))
    return {1: phi1, 2: phi2, "f_all": f[frozenset({1, 2})]}


def as_float_map(d):
    return {str(k): float(v) for k, v in d.items()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    skill = Trajectory(0, 1, 1)
    luck = Trajectory(1, 1, 1)
    skill_phi = shapley(skill)
    luck_phi = shapley(luck)
    predicates = {
        "skill_terminal_positive": skill_phi[2] > 0,
        "luck_terminal_zero": luck_phi[2] == 0,
        "naive_return_confounded": skill.y == luck.y == 1,
        "skill_efficiency": skill_phi[1] + skill_phi[2] == skill_phi["f_all"],
        "luck_efficiency": luck_phi[1] + luck_phi[2] == luck_phi["f_all"],
    }
    verdict = "S01_SKILLLUCK_CONCEPT_REPRODUCED" if all(predicates.values()) else "S01_SKILLLUCK_CONCEPT_NOT_REPRODUCED"
    payload = {
        "experiment": "S01 minimal Skill/Luck conceptual reproduction",
        "scope": "conceptual property only; not full paper reproduction",
        "skill": {"trajectory": skill.__dict__, "observed_y": skill.y, "phi": as_float_map(skill_phi)},
        "luck": {"trajectory": luck.__dict__, "observed_y": luck.y, "phi": as_float_map(luck_phi)},
        "naive_return_credit_x2": {"skill": float(skill.y), "luck": float(luck.y)},
        "predicates": predicates,
        "verdict": verdict,
        "architecture_promotion_authority": False,
    }
    (OUT / "verdict.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if all(predicates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
