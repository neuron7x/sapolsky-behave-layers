from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
PLAYERS = ("A", "C", "D", "B")
POSITIONS = {"A": 0, "C": 1, "D": 2, "B": 3}
CONTEXTS = {
    "TRAIN_CONFOUNDED": {"gamma": 2.0, "c_sign": 1},
    "OOD_WEAK_CONFOUNDER": {"gamma": 0.25, "c_sign": 1},
    "OOD_SIGN_INVERSION": {"gamma": 1.5, "c_sign": -1},
}
N_PER_CONTEXT = 128
BETA = 1.0
NOISE_SD = 0.20
MC_BUDGETS = (4, 16, 64)
TD_LAMBDA = 0.80


@dataclass(frozen=True, slots=True)
class Row:
    A: int
    C: int
    D: int
    B: int
    U: int
    epsilon: float
    beta: float
    gamma: float

    @property
    def y(self) -> float:
        return self.beta * self.A + self.gamma * self.U + self.epsilon


def structural_y(*, A: int, C: int, D: int, B: int, U: int, epsilon: float, beta: float, gamma: float) -> float:
    del C, D, B
    return beta * A + gamma * U + epsilon


def _binary_assignments(names: tuple[str, ...]) -> Iterable[dict[str, int]]:
    if not names:
        yield {}
        return
    for values in itertools.product((-1, 1), repeat=len(names)):
        yield dict(zip(names, values, strict=True))


def exact_counterfactual_y(row: Row, coalition: frozenset[str]) -> tuple[float, int]:
    names = tuple(sorted(coalition))
    base = {name: getattr(row, name) for name in PLAYERS}
    total = 0.0
    count = 0
    for assignment in _binary_assignments(names):
        vals = base | assignment
        total += structural_y(
            A=vals["A"], C=vals["C"], D=vals["D"], B=vals["B"],
            U=row.U, epsilon=row.epsilon, beta=row.beta, gamma=row.gamma,
        )
        count += 1
    return total / count, count


def exact_value(row: Row, coalition: frozenset[str]) -> tuple[float, int]:
    cf, evaluations = exact_counterfactual_y(row, coalition)
    return row.y - cf, evaluations


def exact_shapley(row: Row) -> tuple[dict[str, float], int, float]:
    n = len(PLAYERS)
    values: dict[frozenset[str], float] = {}
    evaluations = 0
    for r in range(n + 1):
        for subset in itertools.combinations(PLAYERS, r):
            key = frozenset(subset)
            values[key], used = exact_value(row, key)
            evaluations += used
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
    efficiency = abs(sum(phi.values()) - (values[frozenset(PLAYERS)] - values[frozenset()]))
    return phi, evaluations, efficiency


def sampled_value(row: Row, coalition: frozenset[str], rng: random.Random) -> tuple[float, int]:
    vals = {name: getattr(row, name) for name in PLAYERS}
    for name in coalition:
        vals[name] = -1 if rng.random() < 0.5 else 1
    cf = structural_y(
        A=vals["A"], C=vals["C"], D=vals["D"], B=vals["B"],
        U=row.U, epsilon=row.epsilon, beta=row.beta, gamma=row.gamma,
    )
    return row.y - cf, 1


def mc_permutation_shapley(row: Row, *, permutations: int, rng: random.Random) -> tuple[dict[str, float], int]:
    credits = {name: 0.0 for name in PLAYERS}
    evaluations = 0
    order = list(PLAYERS)
    for _ in range(permutations):
        rng.shuffle(order)
        coalition: frozenset[str] = frozenset()
        previous, used = sampled_value(row, coalition, rng)
        evaluations += used
        for player in order:
            coalition = coalition | {player}
            current, used = sampled_value(row, coalition, rng)
            evaluations += used
            credits[player] += current - previous
            previous = current
    return {name: value / permutations for name, value in credits.items()}, evaluations


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return statistics.fmean(vals) if vals else 0.0


def pearson_abs(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    mx, my = mean(x), mean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    vx = sum(v * v for v in dx)
    vy = sum(v * v for v in dy)
    if vx <= 1e-15 or vy <= 1e-15:
        return 0.0
    return abs(sum(a * b for a, b in zip(dx, dy, strict=True)) / math.sqrt(vx * vy))


def covariance_abs(x: list[float], y: list[float]) -> float:
    mx, my = mean(x), mean(y)
    return abs(mean((a - mx) * (b - my) for a, b in zip(x, y, strict=True)))


def rank_unique_first(scores: dict[str, float], target: str = "A", tol: float = 1e-12) -> bool:
    best_other = max(score for name, score in scores.items() if name != target)
    return scores[target] > best_other + tol


def false_credit_mass(scores: dict[str, float], target: str = "A") -> float:
    total = sum(abs(v) for v in scores.values())
    if total <= 1e-15:
        return 0.0
    return sum(abs(v) for name, v in scores.items() if name != target) / total


def stable_seed(*parts: object) -> int:
    payload = "|".join(map(str, parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def generate_rows(*, seed: int, context: str, mode: str = "NORMAL") -> list[Row]:
    cfg = CONTEXTS[context]
    rng = random.Random(stable_seed(seed, context, mode, "data"))
    beta = BETA
    gamma = float(cfg["gamma"])
    noise_sd = NOISE_SD
    if mode in {"DESTROY_CAUSAL_LINK", "CORRELATION_ONLY"}:
        beta = 0.0
        gamma = 2.0
    if mode == "PURE_NOISE":
        beta = 0.0
        gamma = 0.0
    if mode == "HIGH_NOISE":
        noise_sd = 1.0

    rows: list[Row] = []
    for _ in range(N_PER_CONTEXT):
        A = -1 if rng.random() < 0.5 else 1
        U = -1 if rng.random() < 0.5 else 1
        c_base = U if int(cfg["c_sign"]) > 0 else -U
        # Tiny observation noise prevents an unrealistically perfect proxy in all rows.
        C = c_base if rng.random() > 0.08 else -c_base
        # Temporally adjacent B is associated with A but is not in the structural equation.
        B = A if rng.random() < 0.80 else -A
        D = -1 if rng.random() < 0.5 else 1
        epsilon = rng.gauss(0.0, noise_sd)
        rows.append(Row(A, C, D, B, U, epsilon, beta, gamma))
    return rows


def aggregate_methods(rows: list[Row], *, seed: int, context: str, mc_budgets: tuple[int, ...] = MC_BUDGETS) -> tuple[dict[str, dict[str, float]], dict[str, int], float]:
    abs_exact = {p: [] for p in PLAYERS}
    abs_mc = {budget: {p: [] for p in PLAYERS} for budget in mc_budgets}
    eval_counts = {"EXACT_CF_SHAPLEY": 0, **{f"MC_CF_SHAPLEY_{b}": 0 for b in mc_budgets}}
    max_efficiency_error = 0.0
    for index, row in enumerate(rows):
        exact, used, error = exact_shapley(row)
        eval_counts["EXACT_CF_SHAPLEY"] += used
        max_efficiency_error = max(max_efficiency_error, error)
        for p in PLAYERS:
            abs_exact[p].append(abs(exact[p]))
        for budget in mc_budgets:
            rng = random.Random(stable_seed(seed, context, index, budget, "mc"))
            approx, used = mc_permutation_shapley(row, permutations=budget, rng=rng)
            eval_counts[f"MC_CF_SHAPLEY_{budget}"] += used
            for p in PLAYERS:
                abs_mc[budget][p].append(abs(approx[p]))

    arrays = {p: [float(getattr(r, p)) for r in rows] for p in PLAYERS}
    ys = [r.y for r in rows]
    methods: dict[str, dict[str, float]] = {
        "EXACT_CF_SHAPLEY": {p: mean(abs_exact[p]) for p in PLAYERS},
        "OBS_ASSOC": {p: pearson_abs(arrays[p], ys) for p in PLAYERS},
        "RECENCY": {p: float(POSITIONS[p] + 1) / len(PLAYERS) for p in PLAYERS},
        "UNIFORM": {p: 1.0 for p in PLAYERS},
    }
    for budget in mc_budgets:
        methods[f"MC_CF_SHAPLEY_{budget}"] = {p: mean(abs_mc[budget][p]) for p in PLAYERS}

    # A delayed-error + eligibility-trace proxy. It is deliberately named a proxy: this
    # environment has no learned value function, so it is not presented as canonical TD.
    residual = [y - mean(ys) for y in ys]
    methods["TD_ELIGIBILITY_PROXY"] = {
        p: covariance_abs(arrays[p], residual) * (TD_LAMBDA ** (len(PLAYERS) - 1 - POSITIONS[p]))
        for p in PLAYERS
    }
    rrng = random.Random(stable_seed(seed, context, "random_credit"))
    methods["RANDOM"] = {p: rrng.random() for p in PLAYERS}
    return methods, eval_counts, max_efficiency_error


def evaluate_cohort(*, seed_start: int, seed_count: int, mode: str) -> dict[str, object]:
    rows_out: list[dict[str, object]] = []
    started = time.perf_counter()
    for seed in range(seed_start, seed_start + seed_count):
        for context in CONTEXTS:
            rows = generate_rows(seed=seed, context=context, mode=mode)
            methods, eval_counts, max_eff = aggregate_methods(rows, seed=seed, context=context)
            for method, scores in methods.items():
                rows_out.append({
                    "seed": seed,
                    "context": context,
                    "mode": mode,
                    "method": method,
                    "top1_A": rank_unique_first(scores),
                    "false_credit_mass": false_credit_mass(scores),
                    "score_A": scores["A"],
                    "score_C": scores["C"],
                    "score_D": scores["D"],
                    "score_B": scores["B"],
                    "structural_evaluations": eval_counts.get(method, 0),
                    "max_efficiency_error": max_eff if method == "EXACT_CF_SHAPLEY" else None,
                })
    elapsed = time.perf_counter() - started
    return {"rows": rows_out, "wall_seconds": elapsed}


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {}
    methods = sorted({str(r["method"]) for r in rows})
    contexts = sorted({str(r["context"]) for r in rows})
    for method in methods:
        by_context: dict[str, object] = {}
        for context in contexts:
            subset = [r for r in rows if r["method"] == method and r["context"] == context]
            by_context[context] = {
                "n": len(subset),
                "causal_rank_accuracy": mean(float(bool(r["top1_A"])) for r in subset),
                "mean_false_credit_mass": mean(float(r["false_credit_mass"]) for r in subset),
                "mean_scores": {
                    p: mean(float(r[f"score_{p}"]) for r in subset) for p in PLAYERS
                },
                "structural_evaluations": sum(int(r["structural_evaluations"]) for r in subset),
            }
        summary[method] = by_context
    return summary


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "seed", "context", "mode", "method", "top1_A", "false_credit_mass",
        "score_A", "score_C", "score_D", "score_B", "structural_evaluations", "max_efficiency_error",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-start", type=int, required=True)
    parser.add_argument("--seed-count", type=int, default=32)
    parser.add_argument("--mode", choices=("NORMAL", "DESTROY_CAUSAL_LINK", "CORRELATION_ONLY", "PURE_NOISE", "HIGH_NOISE"), default="NORMAL")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    payload = evaluate_cohort(seed_start=args.seed_start, seed_count=args.seed_count, mode=args.mode)
    rows = payload["rows"]
    assert isinstance(rows, list)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "seed_results.csv", rows)
    result = {
        "experiment": "CSCA-01 Counterfactual Credit Kernel",
        "scope": "independent controlled mechanism reproduction; not paper-level reproduction",
        "seed_start": args.seed_start,
        "seed_count": args.seed_count,
        "mode": args.mode,
        "n_per_context": N_PER_CONTEXT,
        "contexts": CONTEXTS,
        "mc_permutation_budgets": MC_BUDGETS,
        "td_baseline": {"name": "TD_ELIGIBILITY_PROXY", "lambda": TD_LAMBDA, "boundary": "not canonical TD; no learned value function in this simulator"},
        "summary": summarize(rows),
        "wall_seconds": payload["wall_seconds"],
    }
    (args.out / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
