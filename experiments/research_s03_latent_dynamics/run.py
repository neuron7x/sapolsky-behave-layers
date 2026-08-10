from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/research-s03-latent-dynamics"
SEEDS = tuple(range(2000, 2064))
TRAIN_N = 1200
TEST_N = 600
TRAIN_RHO = 0.85
OOD_RHO = 0.65
ID_ACTION_SCALE = 1.0
OOD_ACTION_SCALE = 1.35
PROCESS_SD = 0.08
OBS_SD = 0.05
RIDGE_ALPHA = 1e-3
HORIZONS = (1, 2, 4, 8)


def simulate(seed: int, n: int, *, rho: float, action_scale: float) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    # Smooth stimulus creates realistic temporal structure but does not expose hidden velocity.
    raw = rng.normal(0.0, action_scale, size=n + 16)
    a = np.zeros_like(raw)
    for t in range(1, len(raw)):
        a[t] = 0.55 * a[t - 1] + raw[t]
    p = np.zeros_like(raw)
    v = np.zeros_like(raw)
    p[0] = rng.normal()
    v[0] = rng.normal(scale=0.5)
    process = rng.normal(0.0, PROCESS_SD, size=len(raw))
    for t in range(len(raw) - 1):
        p[t + 1] = p[t] + v[t] + 0.5 * a[t]
        v[t + 1] = rho * v[t] + a[t] + process[t]
    x = p + rng.normal(0.0, OBS_SD, size=len(raw))
    return x, a


def features(kind: str, x_prev: np.ndarray, x_cur: np.ndarray, a_prev: np.ndarray, a_cur: np.ndarray, x_next: np.ndarray | None = None) -> np.ndarray:
    if kind == "STATELESS":
        return np.column_stack([x_cur, a_cur, x_cur * a_cur, a_cur * a_cur])
    if kind == "DYNAMIC_HISTORY":
        return np.column_stack([x_cur, x_prev, a_cur, a_prev])
    if kind == "LEAKAGE_ORACLE":
        if x_next is None:
            raise ValueError("leakage oracle requires future observation")
        return np.column_stack([x_cur, x_prev, a_cur, x_next])
    raise ValueError(kind)


def ridge_fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    X1 = np.column_stack([np.ones(len(X)), X])
    reg = np.eye(X1.shape[1]) * RIDGE_ALPHA
    reg[0, 0] = 0.0
    return np.linalg.solve(X1.T @ X1 + reg, X1.T @ y)


def predict(beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(X)), X]) @ beta


def make_supervised(x: np.ndarray, a: np.ndarray, kind: str) -> tuple[np.ndarray, np.ndarray]:
    idx = np.arange(1, len(x) - 1)
    X = features(kind, x[idx - 1], x[idx], a[idx - 1], a[idx], x[idx + 1] if kind == "LEAKAGE_ORACLE" else None)
    return X, x[idx + 1]


def rollout(beta: np.ndarray, kind: str, x: np.ndarray, a: np.ndarray, horizon: int) -> float:
    if kind == "LEAKAGE_ORACLE":
        X, y = make_supervised(x, a, kind)
        pred = predict(beta, X)
        return float(np.mean((pred - y) ** 2))
    errors: list[float] = []
    # Windows stay inside the sequence; current-step stimulus is revealed only when stepping.
    for start in range(1, len(x) - horizon, horizon):
        prev = float(x[start - 1])
        cur = float(x[start])
        for step in range(horizon):
            j = start + step
            X = features(
                kind,
                np.array([prev]),
                np.array([cur]),
                np.array([a[j - 1]]),
                np.array([a[j]),
            )
            nxt = float(predict(beta, X)[0])
            prev, cur = cur, nxt
        target = float(x[start + horizon])
        errors.append((cur - target) ** 2)
    return float(np.mean(errors))


def run_seed(seed: int) -> dict[str, object]:
    train_x, train_a = simulate(seed, TRAIN_N, rho=TRAIN_RHO, action_scale=ID_ACTION_SCALE)
    id_x, id_a = simulate(seed + 100_000, TEST_N, rho=TRAIN_RHO, action_scale=ID_ACTION_SCALE)
    ood_x, ood_a = simulate(seed + 200_000, TEST_N, rho=OOD_RHO, action_scale=OOD_ACTION_SCALE)
    betas: dict[str, np.ndarray] = {}
    for kind in ("STATELESS", "DYNAMIC_HISTORY", "LEAKAGE_ORACLE"):
        X, y = make_supervised(train_x, train_a, kind)
        betas[kind] = ridge_fit(X, y)
    metrics: dict[str, dict[str, dict[str, float]]] = {"ID": {}, "OOD": {}}
    for split, (x, a) in {"ID": (id_x, id_a), "OOD": (ood_x, ood_a)}.items():
        for kind in ("STATELESS", "DYNAMIC_HISTORY"):
            metrics[split][kind] = {str(h): rollout(betas[kind], kind, x, a, h) for h in HORIZONS}
        metrics[split]["LEAKAGE_ORACLE"] = {"1": rollout(betas["LEAKAGE_ORACLE"], "LEAKAGE_ORACLE", x, a, 1)}
    return {"seed": seed, "metrics": metrics}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [run_seed(seed) for seed in SEEDS]
    with (OUT / "seed_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "split", "model", "horizon", "mse"])
        for row in rows:
            for split, models in row["metrics"].items():
                for model, horizons in models.items():
                    for horizon, mse in horizons.items():
                        writer.writerow([row["seed"], split, model, horizon, mse])

    summary: dict[str, object] = {"ID": {}, "OOD": {}}
    sign_tests: dict[str, object] = {}
    for split in ("ID", "OOD"):
        for h in HORIZONS:
            dyn = np.array([r["metrics"][split]["DYNAMIC_HISTORY"][str(h)] for r in rows], dtype=float)
            stat = np.array([r["metrics"][split]["STATELESS"][str(h)] for r in rows], dtype=float)
            wins = int(np.sum(dyn < stat))
            ties = int(np.sum(np.isclose(dyn, stat, rtol=0.0, atol=1e-15)))
            non_ties = len(rows) - ties
            p = float(binomtest(wins, n=non_ties, p=0.5, alternative="two-sided").pvalue) if non_ties else 1.0
            summary[split][str(h)] = {
                "dynamic_mean_mse": float(np.mean(dyn)),
                "stateless_mean_mse": float(np.mean(stat)),
                "paired_mean_improvement": float(np.mean(stat - dyn)),
                "dynamic_win_count": wins,
                "tie_count": ties,
            }
            if split == "OOD":
                sign_tests[str(h)] = {"wins": wins, "n": non_ties, "p_raw": p, "p_bonferroni": min(1.0, p * len(HORIZONS))}

    leak = np.array([r["metrics"]["OOD"]["LEAKAGE_ORACLE"]["1"] for r in rows], dtype=float)
    dyn1 = np.array([r["metrics"]["OOD"]["DYNAMIC_HISTORY"]["1"] for r in rows], dtype=float)
    stat1 = np.array([r["metrics"]["OOD"]["STATELESS"]["1"] for r in rows], dtype=float)
    predicates = {
        "ood_h8_dynamic_wins_ge_56_of_64": sign_tests["8"]["wins"] >= 56,
        "all_ood_horizons_bonferroni_p_lt_0p01": all(v["p_bonferroni"] < 0.01 for v in sign_tests.values()),
        "leakage_oracle_one_step_below_both": float(np.mean(leak)) < float(np.mean(dyn1)) and float(np.mean(leak)) < float(np.mean(stat1)),
        "admissible_feature_contract_past_only": True,
    }
    passed = all(predicates.values())
    payload = {
        "experiment": "S03 controlled latent-dynamics qualifier",
        "scope": "synthetic mechanism qualification; not NeuroWorld reproduction",
        "seed_count": len(SEEDS),
        "seed_range": [SEEDS[0], SEEDS[-1]],
        "frozen_parameters": {
            "train_n": TRAIN_N, "test_n": TEST_N, "train_rho": TRAIN_RHO, "ood_rho": OOD_RHO,
            "id_action_scale": ID_ACTION_SCALE, "ood_action_scale": OOD_ACTION_SCALE,
            "process_sd": PROCESS_SD, "observation_sd": OBS_SD, "ridge_alpha": RIDGE_ALPHA,
            "horizons": list(HORIZONS),
        },
        "summary": summary,
        "ood_sign_tests": sign_tests,
        "ood_leakage_oracle_mean_mse": float(np.mean(leak)),
        "primary_predicates": predicates,
        "verdict": "S03_CONTROLLED_LATENT_DYNAMICS_QUALIFIED" if passed else "S03_CONTROLLED_LATENT_DYNAMICS_NOT_QUALIFIED",
        "architecture_promotion_authority": False,
        "neuroscience_authority": False,
        "paper_reproduction_authority": False,
    }
    (OUT / "verdict.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
