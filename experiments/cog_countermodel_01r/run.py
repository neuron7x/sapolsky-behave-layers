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

OUT = ROOT / "artifacts/cog-countermodel-01r"
RESULT = ROOT / "research/results/COG-COUNTERMODEL-01R"

COHORTS = {
    "PRIMARY": range(91000, 91064),
    "REPLICATION": range(101000, 101064),
}
FAMILIES = {
    "R0_VALID": {"k": 0.0, "sigy": 0.8, "confound_r": 0.0},
    "R1_COORDINATED_EXCLUSION": {"k": 0.5, "sigy": 0.8, "confound_r": 0.0},
    "R2_ALEATORIC_HIGH": {"k": 0.0, "sigy": 3.0, "confound_r": 0.0},
    "R3_UPSTREAM_INVALID": {"k": 0.0, "sigy": 0.8, "confound_r": 1.0},
}
BETA_GRID = np.linspace(-0.5, 2.0, 101)
MIN_SHIFT = 0.40
DIRECT_BOUND = 0.15
BOUNDS = StructuralAssumptionBounds(max_direct_effect_l2=DIRECT_BOUND)


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
                bounds=BOUNDS,
            )
            interval = constrained.declared_direct_effect_beta_interval
            rows.append(
                {
                    "cohort": name,
                    "family": family,
                    "seed": seed,
                    "upstream_state": upstream.state,
                    "reference_beta": ref,
                    "unrestricted_state": unrestricted.state,
                    "unrestricted_beta_set_kind": unrestricted.unrestricted_beta_set_kind,
                    "unrestricted_exact_equivalent_count": unrestricted.exact_equivalent_count,
                    "unrestricted_finite_grid_beta_min": unrestricted.finite_grid_alternative_beta_min,
                    "unrestricted_finite_grid_beta_max": unrestricted.finite_grid_alternative_beta_max,
                    "unrestricted_finite_grid_beta_diameter": unrestricted.finite_grid_alternative_beta_diameter,
                    "unrestricted_frontier_size": len(unrestricted.pareto_frontier),
                    "unrestricted_frontier_max_path_error": max((m.max_path_reconstruction_error for m in unrestricted.pareto_frontier), default=None),
                    "constrained_state": constrained.state,
                    "direct_interval_exists": bool(interval is not None and not interval.is_empty),
                    "direct_interval_lower": None if interval is None else interval.lower,
                    "direct_interval_upper": None if interval is None else interval.upper,
                    "direct_interval_width": None if interval is None else interval.width,
                    "material_countermodel_within_bound": constrained.material_countermodel_within_declared_bounds,
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
        widths = [float(r["direct_interval_width"]) for r in fam if r["direct_interval_exists"] and r["direct_interval_width"] is not None]
        frontier_errs = [float(r["unrestricted_frontier_max_path_error"]) for r in fam if r["unrestricted_frontier_max_path_error"] is not None]
        summary[family] = {
            "n": n,
            "upstream_candidate_rate": rate(lambda r: r["upstream_state"] == "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"),
            "upstream_ineligible_rate": rate(lambda r: r["unrestricted_state"] == "UPSTREAM_CANDIDATE_NOT_ELIGIBLE"),
            "all_real_unrestricted_set_rate": rate(lambda r: r["unrestricted_beta_set_kind"] == "ALL_REAL_BETA_UNDER_UNRESTRICTED_REPARAMETERIZATION"),
            "material_exact_countermodel_survival_rate": rate(lambda r: r["unrestricted_state"] == "OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES"),
            "finite_grid_diameter_ge_1_rate": rate(lambda r: float(r["unrestricted_finite_grid_beta_diameter"]) >= 1.0),
            "nonempty_frontier_rate": rate(lambda r: int(r["unrestricted_frontier_size"]) > 0),
            "max_frontier_path_error": max(frontier_errs) if frontier_errs else None,
            "direct_interval_exists_rate": rate(lambda r: bool(r["direct_interval_exists"])),
            "direct_interval_width_lt_material_shift_rate": rate(lambda r: bool(r["direct_interval_exists"]) and float(r["direct_interval_width"]) < MIN_SHIFT),
            "no_material_countermodel_within_bound_rate": rate(lambda r: bool(r["direct_interval_exists"]) and not bool(r["material_countermodel_within_bound"])),
            "assumption_conditional_state_rate": rate(lambda r: r["constrained_state"] == "ASSUMPTION_CONDITIONAL_IDENTIFICATION_COUNTERMODELS_OUTSIDE_BOUNDS"),
            "median_direct_interval_width": float(np.median(widths)) if widths else None,
            "causal_authority_count": sum(
                int(bool(r["causal_authority_granted_unrestricted"])) + int(bool(r["causal_authority_granted_constrained"]))
                for r in fam
            ),
        }
    return summary, rows


def cohort_pass(summary: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for family in ("R0_VALID", "R1_COORDINATED_EXCLUSION", "R2_ALEATORIC_HIGH"):
        s = summary[family]
        if s["all_real_unrestricted_set_rate"] < 1.0:
            errors.append(f"{family} unrestricted set kind")
        if s["material_exact_countermodel_survival_rate"] < 0.99:
            errors.append(f"{family} material countermodel survival")
        if s["finite_grid_diameter_ge_1_rate"] < 0.99:
            errors.append(f"{family} finite-grid ambiguity diameter")
        if s["nonempty_frontier_rate"] < 1.0:
            errors.append(f"{family} nonempty frontier")
        if s["max_frontier_path_error"] is None or s["max_frontier_path_error"] > 1e-10:
            errors.append(f"{family} path reconstruction")
        if s["causal_authority_count"] != 0:
            errors.append(f"{family} unsafe authority")

    for family in ("R0_VALID", "R1_COORDINATED_EXCLUSION"):
        s = summary[family]
        if s["direct_interval_exists_rate"] < 0.95:
            errors.append(f"{family} direct interval existence")
        if s["direct_interval_width_lt_material_shift_rate"] < 0.95:
            errors.append(f"{family} direct interval width")
        if s["no_material_countermodel_within_bound_rate"] < 0.95:
            errors.append(f"{family} material alternative inside bound")
        if s["assumption_conditional_state_rate"] < 0.95:
            errors.append(f"{family} assumption-conditional state")

    r3 = summary["R3_UPSTREAM_INVALID"]
    if r3["upstream_ineligible_rate"] < 0.95:
        errors.append("R3 upstream eligibility veto")
    if r3["causal_authority_count"] != 0:
        errors.append("R3 unsafe authority")
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
        "experiment_id": "COG-COUNTERMODEL-01R",
        "parent_experiment": "COG-COUNTERMODEL-01",
        "parent_verdict": "AUTONOMOUS_COUNTERMODEL_GENERATOR_NOT_QUALIFIED",
        "verdict": "SET_VALUED_COUNTERMODEL_GUARD_QUALIFIED_SYNTHETIC_NARROWED" if scientific_pass else "SET_VALUED_COUNTERMODEL_GUARD_NOT_QUALIFIED",
        "scientific_pass": scientific_pass,
        "authority": "COUNTERMODEL_SET_GUARD_ONLY" if scientific_pass else "NO_PROMOTION",
        "preconfirmatory_preregistration_commit": "9eeca5f0aceeff9ca3683b3e1edb8aef2ee0599b",
        "rows_per_seed": 4096,
        "seeds_per_family_per_cohort": 64,
        "material_causal_shift": MIN_SHIFT,
        "declared_direct_effect_l2_bound": DIRECT_BOUND,
        "cohorts": summaries,
        "cohort_errors": errors,
        "epistemic_boundary": {
            "hidden_true_beta_recovery_used_for_qualification": False,
            "pareto_membership_used_as_truth_criterion": False,
            "unrestricted_equivalence_set_is_all_real_beta_in_declared_reparameterization_class": True,
            "assumption_conditional_interval_is_causal_truth": False,
            "unconditional_causal_authority": False,
            "semantic_causality": False,
            "real_trace_identification": False,
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
