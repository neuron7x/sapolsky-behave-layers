from __future__ import annotations

import csv
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/research-s01-ood-credit"
PLAYERS = ("A", "C", "D", "B")
CONTEXTS = {
    "TRAIN_CONFOUNDED": 2.0,
    "OOD_WEAK_CONFOUNDER": 0.2,
    "OOD_SIGN_FLIP": -1.5,
}
SEEDS = tuple(range(1000, 1128))
N_PER_CONTEXT = 256
BETA = 1.0
NOISE_SD = 0.20


@dataclass(frozen=True, slots=True)
class Row:
    A: int
    C: int
    D: int
    B: int
    U: int
    epsilon: float
    gamma: float

    @property
    def y(self) -> float:
        return BETA * self.A + self.gamma * self.U + self.epsilon


def structural_y(*, A: int, C: int, D: int, B: int, U: int, epsilon: float, gamma: float) -> float:
    # C/D/B are intentionally absent: only A is a manipulable candidate cause.
    del C, D, B
    return BETA * A + gamma * U + epsilon


def _assignments(names: tuple[str, ...]) -> Iterable[dict[str, int]]:
    if not names:
        yield {}
        return
    for values in itertools.product((0, 1), repeat=len(names)):
        yield dict(zip(names, values, strict=True))


def expected_counterfactual_y(row: Row, coalition: frozenset[str]) -> tuple[float, int]:
    """Exact Bernoulli(0.5) baseline integration for intervened candidates."""
    names = tuple(sorted(coalition))
    total = 0.0
    count = 0
    base = {name: getattr(row, name) for name in PLAYERS}
    for assignment in _assignments(names):
        vals = base | assignment
        total += structural_y(
            A=vals["A"], C=vals["C"], D=vals["D"], B=vals["B"],
            U=row.U, epsilon=row.epsilon, gamma=row.gamma,
        )
        count += 1
    return total / count, count


def coalition_value(row: Row, coalition: frozenset[str]) -> tuple[float, int]:
    expected_y, count = expected_counterfactual_y(row, coalition)
    return row.y - expected_y, count


def exact_shapley(row: Row) -> tuple[dict[str, float], int, float]:
    """Exact four-player Shapley credit and coalition-evaluation accounting."""
    n = len(PLAYERS)
    values: dict[frozenset[str], float] = {}
    evals = 0
    for r in range(n + 1):
        for subset in itertools.combinations(PLAYERS, r):
            key = frozenset(subset)
            values[key], used = coalition_value(row, key)
            evals += used

    phi: dict[str, float] = {}
    denom = math.factorial(n)
    for player in PLAYERS:
        acc = 0.0
        others = tuple(p for p in PLAYERS if p != player)
        for r in range(len(others) + 1):
            weight = math.factorial(r) * math.factorial(n - r - 1) / denom
            for subset in itertools.combinations(others, r):
                s = frozenset(subset)
                acc += weight * (values[s | {player}] - values[s])
        phi[player] = acc
    efficiency_error = abs(sum(phi.values()) - (values[frozenset(PLAYERS)] - values[frozenset()]))
    return phi, evals, efficiency_error


def pearson_abs(x: np.ndarray, y: np.ndarray) -> float:
    if float(np.std(x)) <= 1e-15 or float(np.std(y)) <= 1e-15:
        return 0.0
    return abs(float(np.corrcoef(x, y)[0, 1]))


def rank_unique_first(scores: dict[str, float], target: str = "A", tol: float = 1e-12) -> bool:
    best_other = max(score for name, score in scores.items() if name != target)
    return scores[target] > best_other + tol


def normalized_false_mass(scores: dict[str, float], target: str = "A") -> float:
    total = sum(abs(v) for v in scores.values())
    if total <= 1e-15:
        return 0.0
    return sum(abs(v) for k, v in scores.items() if k != target) / total


def generate(seed: int, gamma: float) -> tuple[list[Row], dict[str, np.ndarray]]:
    rng = np.random.default_rng(seed)
    A = rng.integers(0, 2, size=N_PER_CONTEXT, dtype=np.int8)
    U = rng.integers(0, 2, size=N_PER_CONTEXT, dtype=np.int8)
    C = U.copy()
    D = rng.integers(0, 2, size=N_PER_CONTEXT, dtype=np.int8)
    B = rng.integers(0, 2, size=N_PER_CONTEXT, dtype=np.int8)
    eps = rng.normal(0.0, NOISE_SD, size=N_PER_CONTEXT)
    Y = BETA * A.astype(float) + gamma * U.astype(float) + eps
    rows = [
        Row(int(A[i]), int(C[i]), int(D[i]), int(B[i]), int(U[i]), float(eps[i]), gamma)
        for i in range(N_PER_CONTEXT)
    ]
    arrays = {"A": A.astype(float), "C": C.astype(float), "D": D.astype(float), "B": B.astype(float), "Y": Y}
    return rows, arrays


def evaluate_seed(seed: int, context: str, gamma: float) -> dict[str, object]:
    rows, arrays = generate(seed, gamma)
    abs_phi = {p: [] for p in PLAYERS}
    total_evals = 0
    max_efficiency_error = 0.0
    for row in rows:
        phi, evals, err = exact_shapley(row)
        total_evals += evals
        max_efficiency_error = max(max_efficiency_error, err)
        for player in PLAYERS:
            abs_phi[player].append(abs(phi[player]))
    shapley_scores = {p: float(np.mean(abs_phi[p])) for p in PLAYERS}
    obs_scores = {p: pearson_abs(arrays[p], arrays["Y"]) for p in PLAYERS}
    recency_scores = {p: (idx + 1) / len(PLAYERS) for idx, p in enumerate(PLAYERS)}
    equal_scores = {p: 1.0 for p in PLAYERS}
    methods = {
        "EXACT_CF_SHAPLEY": shapley_scores,
        "OBS_ASSOC": obs_scores,
        "RECENCY": recency_scores,
        "EQUAL": equal_scores,
    }
    return {
        "seed": seed,
        "context": context,
        "gamma": gamma,
        "methods": methods,
        "top1": {m: rank_unique_first(s) for m, s in methods.items()},
        "false_credit_mass": {m: normalized_false_mass(s) for m, s in methods.items()},
        "max_shapley_efficiency_error": max_efficiency_error,
        "counterfactual_structural_evaluations": total_evals,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for context, gamma in CONTEXTS.items():
        for seed in SEEDS:
            results.append(evaluate_seed(seed, context, gamma))

    with (OUT / "seed_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "seed", "context", "gamma", "method", "top1_A", "false_credit_mass",
            "score_A", "score_C", "score_D", "score_B", "max_efficiency_error",
            "counterfactual_structural_evaluations",
        ])
        for row in results:
            for method, scores in row["methods"].items():
                writer.writerow([
                    row["seed"], row["context"], row["gamma"], method,
                    int(row["top1"][method]), row["false_credit_mass"][method],
                    scores["A"], scores["C"], scores["D"], scores["B"],
                    row["max_shapley_efficiency_error"], row["counterfactual_structural_evaluations"],
                ])

    summary: dict[str, object] = {}
    for context in CONTEXTS:
        subset = [r for r in results if r["context"] == context]
        summary[context] = {
            method: {
                "top1_A_rate": float(np.mean([r["top1"][method] for r in subset])),
                "mean_false_credit_mass": float(np.mean([r["false_credit_mass"][method] for r in subset])),
                "mean_scores": {
                    player: float(np.mean([r["methods"][method][player] for r in subset]))
                    for player in PLAYERS
                },
            }
            for method in ("EXACT_CF_SHAPLEY", "OBS_ASSOC", "RECENCY", "EQUAL")
        }

    ood = [r for r in results if r["context"].startswith("OOD_")]
    primary = {
        "ood_shapley_unique_A_all": all(r["top1"]["EXACT_CF_SHAPLEY"] for r in ood),
        "ood_shapley_false_mass_le_1e12": all(r["false_credit_mass"]["EXACT_CF_SHAPLEY"] <= 1e-12 for r in ood),
        "max_efficiency_error_le_1e12": max(float(r["max_shapley_efficiency_error"]) for r in results) <= 1e-12,
    }
    passed = all(primary.values())
    total_cf_evals = sum(int(r["counterfactual_structural_evaluations"]) for r in results)
    payload = {
        "experiment": "S01 OOD causal-credit qualifier",
        "scope": "controlled synthetic qualification; not full S01 paper reproduction",
        "frozen_preregistration": "experiments/research_s01_ood_credit/PREREGISTRATION.md",
        "seeds": [SEEDS[0], SEEDS[-1]],
        "seed_count": len(SEEDS),
        "n_per_context_seed": N_PER_CONTEXT,
        "contexts": CONTEXTS,
        "summary": summary,
        "primary_predicates": primary,
        "max_shapley_efficiency_error": max(float(r["max_shapley_efficiency_error"]) for r in results),
        "counterfactual_structural_evaluations": total_cf_evals,
        "verdict": "S01_OOD_CAUSAL_CREDIT_QUALIFIED" if passed else "S01_OOD_CAUSAL_CREDIT_NOT_QUALIFIED",
        "architecture_promotion_authority": False,
        "paper_reproduction_authority": False,
        "next_gate": "matched-budget approximate estimator vs resolution_aware_debt and RPE",
    }
    (OUT / "verdict.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
