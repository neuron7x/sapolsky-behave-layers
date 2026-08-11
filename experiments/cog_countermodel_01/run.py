from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cwc.causal.regime_identifiability import evaluate_regime_iv
from cwc.epistemics.countermodel_search import StructuralAssumptionBounds, search_countermodels

OUT = ROOT / "artifacts/cog-countermodel-01"
RESULT = ROOT / "research/results/COG-COUNTERMODEL-01"

COHORTS = {
    "PRIMARY": range(71000, 71064),
    "REPLICATION": range(81000, 81064),
}
FAMILIES = {
    "C0_VALID": {"k": 0.0, "sigy": 0.8, "confound_r": 0.0},
    "C1_COORDINATED_EXCLUSION": {"k": 0.5, "sigy": 0.8, "confound_r": 0.0},
    "C2_ALEATORIC_HIGH": {"k": 0.0, "sigy": 3.0, "confound_r": 0.0},
    "C3_UPSTREAM_INVALID": {"k": 0.0, "sigy": 0.8, "confound_r": 1.0},
}
BETA_GRID = np.linspace(-0.5, 2.0, 101)
MIN_SHIFT = 0.49
EXCLUSION_BOUND = StructuralAssumptionBounds(max_direct_effect_l2=0.08)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(seed: int, *, n: int = 4096, beta: float = 0.8, k: float = 0.0, sigy: float = 0.8, confound_r: float = 0.0):
    rng = np.random.default_rng(seed)
    u = rng.normal(size=n)
    e1 = rng.normal(size=n)
    e2 = rng.normal(size=n)
    r1 = np.where(e1 + confound_r * u >= 0.0, 1.0, -1.0)
    r2 = np.where(e2 + 0.7 * confound_r * u >= 0.0, 1.0, -1.0)
    lam = np.array([0.9, 0.5], dtype=np.float64)
    regimes = np.column_stack((r1, r2))
    x = regimes @ lam + 0.8 * u + rng.normal(scale=0.6, size=n)
    y = beta * x + u + k * (regimes @ lam) + rng.normal(scale=sigy, size=n)
    w = u + rng.normal(scale=0.5, size=n)
    return regimes, x, y, w


def _nearest_beta08(frontier) -> tuple[float | None, float | None]:
    near = [m for m in frontier if abs(m.beta - 0.8) <= 0.03]
    if not near:
        return None, None
    best = min(near, key=lambda m: (abs(m.beta - 0.8), m.direct_effect_l2, abs(m.latent_corr_xy)))
    return float(best.beta), float(best.max_path_reconstruction_error)


def run_cohort(name: str, seeds: range) -> tuple[dict, list[dict]]:
    rows: list[dict] = []
    for family, kwargs in FAMILIES.items():
        for seed in seeds:
            regimes, x, y, w = simulate(seed, **kwargs)
            upstream = evaluate_regime_iv(regimes=regimes, treatment=x, outcome=y, negative_control=w, alpha=0.01)
            ref = float(upstream.beta_hat) if upstream.beta_hat is not None else 0.8
            unrestricted = search_countermodels(
                regimes=regimes,
                treatment=x,
                outcome=y,
                reference_beta=ref,
                beta_grid=BETA_GRID,
                min_causal_shift=MIN_SHIFT,
                candidate_state=upstream.state,
                bounds=None,
            )
            constrained = search_countermodels(
                regimes=regimes,
                treatment=x,
                outcome=y,
                reference_beta=ref,
                beta_grid=BETA_GRID,
                min_causal_shift=MIN_SHIFT,
                candidate_state=upstream.state,
                bounds=EXCLUSION_BOUND,
            )
            near_beta, near_err = _nearest_beta08(unrestricted.pareto_frontier)
            frontier_max_err = (
                max((m.max_path_reconstruction_error for m in unrestricted.pareto_frontier), default=None)
                if unrestricted.pareto_frontier
                else None
            )
            rows.append(
                {
                    "cohort": name,
                    "family": family,
                    "seed": seed,
                    "upstream_state": upstream.state,
                    "reference_beta": ref,
                    "unrestricted_state": unrestricted.state,
                    "unrestricted_exact_equivalent_count": unrestricted.exact_equivalent_count,
                    "unrestricted_constrained_survivor_count": unrestricted.constrained_survivor_count,
                    "unrestricted_frontier_size": len(unrestricted.pareto_frontier),
                    "unrestricted_frontier_max_path_error": frontier_max_err,
                    "constrained_state": constrained.state,
                    "constrained_survivor_count": constrained.constrained_survivor_count,
                    "near_true_beta_countermodel": near_beta,
                    "near_true_beta_path_error": near_err,
                    "causal_authority_granted_unrestricted": unrestricted.causal_authority_granted,
                    "causal_authority_granted_constrained": constrained.causal_authority_granted,
                }
            )

    summary: dict[str, dict] = {}
    for family in FAMILIES:
        fam = [r for r in rows if r["family"] == family]
        n = len(fam)
        def rate(pred):
            return sum(1 for row in fam if pred(row)) / n
        errors = [
            float(r["near_true_beta_path_error"])
            for r in fam
            if r["near_true_beta_path_error"] not in (None, "")
        ]
        summary[family] = {
            "n": n,
            "upstream_candidate_rate": rate(lambda r: r["upstream_state"] == "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"),
            "upstream_invalid_rate": rate(lambda r: r["upstream_state"] != "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"),
            "unrestricted_countermodel_survival_rate": rate(lambda r: r["unrestricted_state"] == "OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES"),
            "strict_exclusion_assumption_conditional_rate": rate(lambda r: r["constrained_state"] == "ASSUMPTION_CONDITIONAL_IDENTIFICATION_COUNTERMODELS_OUTSIDE_BOUNDS"),
            "upstream_ineligible_countermodel_rate": rate(lambda r: r["unrestricted_state"] == "UPSTREAM_CANDIDATE_NOT_ELIGIBLE"),
            "nonempty_frontier_rate": rate(lambda r: int(r["unrestricted_frontier_size"]) > 0),
            "near_true_0p8_countermodel_rate": rate(lambda r: r["near_true_beta_countermodel"] is not None),
            "max_near_true_path_error": max(errors) if errors else None,
            "max_any_frontier_path_error": max(
                (float(r["unrestricted_frontier_max_path_error"]) for r in fam if r["unrestricted_frontier_max_path_error"] is not None),
                default=None,
            ),
            "causal_authority_count": sum(
                int(bool(r["causal_authority_granted_unrestricted"])) + int(bool(r["causal_authority_granted_constrained"]))
                for r in fam
            ),
        }
    return summary, rows


def cohort_pass(summary: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    c0 = summary["C0_VALID"]
    if c0["unrestricted_countermodel_survival_rate"] < 0.99:
        errors.append("C0 unrestricted countermodel survival")
    if c0["strict_exclusion_assumption_conditional_rate"] < 0.95:
        errors.append("C0 exclusion-conditional uniqueness")
    c1 = summary["C1_COORDINATED_EXCLUSION"]
    if c1["unrestricted_countermodel_survival_rate"] < 0.99:
        errors.append("C1 unrestricted countermodel survival")
    if c1["near_true_0p8_countermodel_rate"] < 0.95:
        errors.append("C1 near-0.8 countermodel recovery")
    if c1["max_near_true_path_error"] is None or c1["max_near_true_path_error"] > 1e-10:
        errors.append("C1 path reconstruction")
    c2 = summary["C2_ALEATORIC_HIGH"]
    if c2["unrestricted_countermodel_survival_rate"] < 0.99:
        errors.append("C2 aleatoric equivalence-class survival")
    c3 = summary["C3_UPSTREAM_INVALID"]
    if c3["upstream_ineligible_countermodel_rate"] < 0.95:
        errors.append("C3 upstream eligibility veto")
    for family, stats in summary.items():
        if stats["causal_authority_count"] != 0:
            errors.append(f"{family} emitted causal authority")
        if family != "C3_UPSTREAM_INVALID" and stats["nonempty_frontier_rate"] < 1.0:
            errors.append(f"{family} empty Pareto frontier")
    return not errors, errors


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    RESULT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    summaries: dict[str, dict] = {}
    rows: list[dict] = []
    errors: dict[str, list[str]] = {}
    for name, seeds in COHORTS.items():
        s, r = run_cohort(name, seeds)
        ok, e = cohort_pass(s)
        summaries[name] = s
        rows.extend(r)
        errors[name] = e
        if not ok:
            print(name, "FAIL", e, file=sys.stderr)

    scientific_pass = all(not v for v in errors.values())
    verdict = {
        "experiment_id": "COG-COUNTERMODEL-01",
        "verdict": "AUTONOMOUS_COUNTERMODEL_GENERATOR_QUALIFIED_SYNTHETIC_NARROWED" if scientific_pass else "AUTONOMOUS_COUNTERMODEL_GENERATOR_NOT_QUALIFIED",
        "scientific_pass": scientific_pass,
        "authority": "COUNTERMODEL_FALSIFICATION_GUARD_ONLY" if scientific_pass else "NO_PROMOTION",
        "preconfirmatory_preregistration_commit": "a6e2a6841e368aec854865f65ecdf298f40c1609",
        "beta_grid": {"min": -0.5, "max": 2.0, "points": 101, "step": 0.025},
        "min_causal_shift": MIN_SHIFT,
        "strict_exclusion_direct_effect_l2_bound": 0.08,
        "rows_per_seed": 4096,
        "seeds_per_family_per_cohort": 64,
        "cohorts": summaries,
        "cohort_errors": errors,
        "epistemic_boundary": {
            "countermodel_survival_blocks_consolidation": True,
            "no_countermodel_inside_assumption_bounds_proves_assumptions": False,
            "no_countermodel_in_finite_grid_proves_global_identification": False,
            "unconditional_causal_authority": False,
            "semantic_causality": False,
            "replay_control": False,
            "active_control": False,
            "architecture_promotion": False,
        },
        "wall_seconds": time.perf_counter() - started,
    }

    fields = list(rows[0].keys())
    with (OUT / "seed_results.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    (RESULT / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    payload = [OUT / "seed_results.csv", OUT / "verdict.json"]
    (OUT / "SHA256SUMS").write_text("".join(f"{_sha(p)}  {p.name}\n" for p in payload))
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if scientific_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
