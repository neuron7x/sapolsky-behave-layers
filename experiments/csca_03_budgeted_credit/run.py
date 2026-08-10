from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import time
from pathlib import Path
from typing import Callable

from cwc.credit.budgeted_shapley import (
    ShapleyEstimate,
    antithetic_crn_mc,
    crn_chain_mc,
    double_antithetic_crn_mc,
    exact_resampling_shapley,
    legacy_independent_mc,
)
from cwc.credit.context_authority import decide_context_direction

from .environment import PLAYERS, Case, generate_cases, make_evaluator, stable_seed

BUDGETS = (8, 16, 32, 64, 128, 256)
METHODS = (
    "LEGACY_INDEPENDENT_MC",
    "CRN_CHAIN_MC",
    "ANTITHETIC_CRN_MC",
    "DOUBLE_ANTITHETIC_CRN_MC",
)
FAMILIES = (
    "E0_SINGLE_CAUSE",
    "E1_TWO_CAUSE_INTERACTION",
    "E2_CONTEXT_SIGN_FLIP",
    "E3_PRECISELY_WRONG_MODEL",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _estimate(method: str, case: Case, evaluator: Callable[[dict[str, int]], float], *, budget: int, seed: int) -> ShapleyEstimate:
    n = len(PLAYERS)
    rng = random.Random(seed)
    if method == "LEGACY_INDEPENDENT_MC":
        return legacy_independent_mc(case.factual, PLAYERS, evaluator, permutations=max(1, budget // n), rng=rng)
    if method == "CRN_CHAIN_MC":
        return crn_chain_mc(case.factual, PLAYERS, evaluator, permutations=max(1, budget // n), rng=rng)
    if method == "ANTITHETIC_CRN_MC":
        return antithetic_crn_mc(case.factual, PLAYERS, evaluator, pairs=max(1, budget // (2 * n)), rng=rng)
    if method == "DOUBLE_ANTITHETIC_CRN_MC":
        return double_antithetic_crn_mc(case.factual, PLAYERS, evaluator, quartets=max(1, budget // (4 * n)), rng=rng)
    raise ValueError(method)


def _true_causes(family: str) -> set[str]:
    return {"A", "B"} if family == "E1_TWO_CAUSE_INTERACTION" else {"A"}


def _false_mass(credits: dict[str, float], true_causes: set[str]) -> float:
    denom = sum(abs(v) for v in credits.values())
    if denom <= 1e-15:
        return 0.0
    return sum(abs(v) for p, v in credits.items() if p not in true_causes) / denom


def _topset_ok(credits: dict[str, float], true_causes: set[str]) -> bool:
    ranked = sorted(credits, key=lambda p: (-abs(credits[p]), p))
    return set(ranked[: len(true_causes)]) == true_causes


def _sq_error(a: dict[str, float], b: dict[str, float]) -> float:
    return sum((a[p] - b[p]) ** 2 for p in PLAYERS) / len(PLAYERS)


def _mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else 0.0


def run_cohort(*, seed_start: int, seed_count: int, rows_per_context: int, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    context_signed: dict[tuple[str, int, str, int], dict[str, list[float]]] = {}
    started = time.perf_counter()
    exact_evals = 0
    approx_evals = 0

    for seed in range(seed_start, seed_start + seed_count):
        for family in FAMILIES:
            cases = generate_cases(family=family, seed=seed, n=rows_per_context)
            for case_index, case in enumerate(cases):
                true_eval = make_evaluator(case, model="TRUE")
                true_teacher = exact_resampling_shapley(case.factual, PLAYERS, true_eval)
                exact_evals += true_teacher.structural_evaluations
                model_eval = make_evaluator(case, model="WRONG_SHARED_SPURIOUS_EDGE") if family == "E3_PRECISELY_WRONG_MODEL" else true_eval
                model_teacher = exact_resampling_shapley(case.factual, PLAYERS, model_eval)
                exact_evals += model_teacher.structural_evaluations if family == "E3_PRECISELY_WRONG_MODEL" else 0
                true_causes = _true_causes(family)

                for budget in BUDGETS:
                    for method in METHODS:
                        est = _estimate(method, case, model_eval, budget=budget, seed=stable_seed(seed, family, case_index, budget, method))
                        approx_evals += est.structural_evaluations
                        rec = {
                            "seed": seed, "family": family, "context": case.context, "case_index": case_index,
                            "budget": budget, "method": method, "actual_evaluations": est.structural_evaluations,
                            "sampling_units": est.sampling_units,
                            "rmse_true_teacher": math.sqrt(_sq_error(est.credits, true_teacher.credits)),
                            "rmse_model_teacher": math.sqrt(_sq_error(est.credits, model_teacher.credits)),
                            "false_credit_mass_true": _false_mass(est.credits, true_causes),
                            "topset_recovery": int(_topset_ok(est.credits, true_causes)),
                            "max_estimator_variance": max(est.estimator_variance.values(), default=0.0),
                            "model_teacher_false_mass_true": _false_mass(model_teacher.credits, true_causes),
                            "true_teacher_A": true_teacher.credits["A"], "model_teacher_A": model_teacher.credits["A"],
                            "model_teacher_C": model_teacher.credits["C"],
                        }
                        for p in PLAYERS:
                            rec[f"credit_{p}"] = est.credits[p]
                            rec[f"var_{p}"] = est.estimator_variance[p]
                        records.append(rec)
                        if family == "E2_CONTEXT_SIGN_FLIP":
                            key = (family, seed, method, budget)
                            slot = context_signed.setdefault(key, {})
                            bucket = slot.setdefault(str(case.context), [])
                            # Directional leverage for centered binary A: phi_A / A = phi_A * A.
                            bucket.append(est.credits["A"] * float(case.A))

    authority_rows: list[dict[str, object]] = []
    for (family, seed, method, budget), by_context in sorted(context_signed.items()):
        signed = {ctx: {"A": _mean(vals), "B": 0.0, "C": 0.0, "D": 0.0} for ctx, vals in by_context.items()}
        decision = decide_context_direction(signed, tolerance=1e-6)
        authority_rows.append({
            "family": family, "seed": seed, "method": method, "budget": budget,
            "state": decision.state, "candidate": decision.candidate, "sign": decision.sign,
            "context_signs": json.dumps(decision.context_signs, sort_keys=True),
        })

    csv_path = out_dir / "case_results.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys())); writer.writeheader(); writer.writerows(records)
    auth_path = out_dir / "context_authority.csv"
    with auth_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(authority_rows[0].keys())); writer.writeheader(); writer.writerows(authority_rows)

    groups: dict[tuple[str, str, int], list[dict[str, object]]] = {}
    for rec in records:
        groups.setdefault((str(rec["family"]), str(rec["method"]), int(rec["budget"])), []).append(rec)
    aggregate: list[dict[str, object]] = []
    for (family, method, budget), rows in sorted(groups.items()):
        aggregate.append({
            "family": family, "method": method, "budget": budget, "n_rows": len(rows),
            "mean_rmse_true_teacher": _mean([float(r["rmse_true_teacher"]) for r in rows]),
            "mean_rmse_model_teacher": _mean([float(r["rmse_model_teacher"]) for r in rows]),
            "mean_false_credit_mass_true": _mean([float(r["false_credit_mass_true"]) for r in rows]),
            "max_false_credit_mass_true": max(float(r["false_credit_mass_true"]) for r in rows),
            "topset_recovery": _mean([float(r["topset_recovery"]) for r in rows]),
            "mean_max_estimator_variance": _mean([float(r["max_estimator_variance"]) for r in rows]),
            "max_estimator_variance": max(float(r["max_estimator_variance"]) for r in rows),
            "mean_actual_evaluations": _mean([float(r["actual_evaluations"]) for r in rows]),
            "mean_model_teacher_false_mass_true": _mean([float(r["model_teacher_false_mass_true"]) for r in rows]),
        })
    agg_path = out_dir / "aggregate.csv"
    with agg_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregate[0].keys())); writer.writeheader(); writer.writerows(aggregate)

    elapsed = time.perf_counter() - started
    summary = {
        "seed_start": seed_start, "seed_count": seed_count, "rows_per_context": rows_per_context,
        "budgets": list(BUDGETS), "families": list(FAMILIES), "methods": list(METHODS),
        "case_records": len(records), "context_authority_records": len(authority_rows),
        "exact_structural_evaluations": exact_evals, "approx_structural_evaluations": approx_evals,
        "total_structural_evaluations": exact_evals + approx_evals, "wall_seconds": elapsed,
        "artifacts": {"case_results_sha256": _sha256(csv_path), "aggregate_sha256": _sha256(agg_path), "context_authority_sha256": _sha256(auth_path)},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-start", type=int, required=True)
    parser.add_argument("--seed-count", type=int, required=True)
    parser.add_argument("--rows-per-context", type=int, default=64)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_cohort(seed_start=args.seed_start, seed_count=args.seed_count, rows_per_context=args.rows_per_context, out_dir=args.out), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
