from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from cwc.causal.regime_identifiability import coordinated_exclusion_counterexample, evaluate_regime_iv

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/csca-08-regime-identifiability"
RESULT = ROOT / "research/results/CSCA-08A"

FAMILIES = {
    "V0_VALID": {},
    "V1_DIRECT_NONPROPORTIONAL": {"eta": (0.5, 0.0)},
    "V2_R_U_CONFOUNDING": {"confound_r": 1.0},
    "V3_ALEATORIC_HIGH": {"sigy": 3.0},
    "V4_SELECTION_BIAS": {"select_strength": 1.0},
    "V5_WEAK_RELEVANCE": {"lamb": (0.015, 0.01)},
    "V6_COORDINATED_EXCLUSION": {"eta": (0.45, 0.25)},
    "V7_LABEL_CORRUPTION": {"label_flip": 0.25},
}

COHORTS = {
    "PRIMARY": range(50000, 50128),
    "REPLICATION": range(60000, 60128),
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def simulate(
    seed: int,
    *,
    n: int = 4096,
    beta: float = 0.8,
    lamb: tuple[float, float] = (0.9, 0.5),
    gamma: float = 0.8,
    delta: float = 1.0,
    eta: tuple[float, float] = (0.0, 0.0),
    sigx: float = 0.6,
    sigy: float = 0.8,
    sigw: float = 0.5,
    confound_r: float = 0.0,
    select_strength: float = 0.0,
    label_flip: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    u = rng.normal(size=n)
    e1 = rng.normal(size=n)
    e2 = rng.normal(size=n)
    r1 = np.where(e1 + confound_r * u >= 0, 1.0, -1.0)
    r2 = np.where(e2 + 0.7 * confound_r * u >= 0, 1.0, -1.0)
    x = lamb[0] * r1 + lamb[1] * r2 + gamma * u + rng.normal(scale=sigx, size=n)
    y = beta * x + delta * u + eta[0] * r1 + eta[1] * r2 + rng.normal(scale=sigy, size=n)
    w = u + rng.normal(scale=sigw, size=n)
    if select_strength:
        keep_p = 1.0 / (1.0 + np.exp(-select_strength * r1 * u))
        keep = rng.random(n) < keep_p
        r1, r2, x, y, w = (a[keep] for a in (r1, r2, x, y, w))
    if label_flip:
        r1 = r1 * np.where(rng.random(len(r1)) < label_flip, -1.0, 1.0)
        r2 = r2 * np.where(rng.random(len(r2)) < label_flip, -1.0, 1.0)
    return np.column_stack((r1, r2)), x, y, w


def run_cohort(name: str, seeds: range) -> tuple[dict, list[dict]]:
    rows: list[dict] = []
    for family, kwargs in FAMILIES.items():
        for seed in seeds:
            r, x, y, w = simulate(seed, **kwargs)
            d = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w, alpha=0.01)
            rows.append(
                {
                    "cohort": name,
                    "family": family,
                    "seed": seed,
                    "n_observed": len(x),
                    "state": d.state,
                    "beta_hat": d.beta_hat,
                    "beta_se": d.beta_se,
                    "relevant_instruments": d.relevant_instruments,
                    "max_overidentification_z": d.max_overidentification_z,
                    "max_negative_control_z": d.max_negative_control_z,
                    "z_critical": d.z_critical,
                    "causal_authority_granted": d.causal_authority_granted,
                    "has_exclusion_debt": "A3_EXCLUSION_NOT_TESTABLE_FROM_FACTUAL_CHANNEL" in d.unresolved_assumption_debt,
                    "has_measurement_debt": "A5_REGIME_MEASUREMENT_RELIABILITY_NOT_PROVEN" in d.unresolved_assumption_debt,
                }
            )
    summary: dict[str, dict] = {}
    for family in FAMILIES:
        f = [r for r in rows if r["family"] == family]
        n = len(f)
        states: dict[str, int] = {}
        for r in f:
            states[r["state"]] = states.get(r["state"], 0) + 1
        errs = [abs(float(r["beta_hat"]) - 0.8) for r in f if r["beta_hat"] is not None]
        summary[family] = {
            "n": n,
            "states": states,
            "candidate_rate": states.get("CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS", 0) / n,
            "assumption_violation_rate": states.get("IDENTIFYING_ASSUMPTION_VIOLATED", 0) / n,
            "insufficient_information_rate": states.get("INSUFFICIENT_INFORMATION_BUDGET", 0) / n,
            "median_abs_beta_error_vs_true_0p8": float(np.median(errs)) if errs else None,
            "causal_authority_count": sum(bool(r["causal_authority_granted"]) for r in f),
            "exclusion_debt_rate": sum(bool(r["has_exclusion_debt"]) for r in f) / n,
            "measurement_debt_rate": sum(bool(r["has_measurement_debt"]) for r in f) / n,
        }
    return summary, rows


def cohort_pass(s: dict) -> tuple[bool, list[str]]:
    e: list[str] = []
    v0=s["V0_VALID"]
    if v0["candidate_rate"] < .95: e.append("V0 candidate rate")
    if v0["assumption_violation_rate"] > .04: e.append("V0 false violation")
    if v0["median_abs_beta_error_vs_true_0p8"] > .05: e.append("V0 beta error")
    if s["V1_DIRECT_NONPROPORTIONAL"]["assumption_violation_rate"] < .95: e.append("V1 direct-effect falsification")
    if s["V2_R_U_CONFOUNDING"]["assumption_violation_rate"] < .95: e.append("V2 confounding falsification")
    v3=s["V3_ALEATORIC_HIGH"]
    if v3["candidate_rate"] < .90: e.append("V3 aleatoric candidate rate")
    if v3["median_abs_beta_error_vs_true_0p8"] > .10: e.append("V3 beta error")
    if s["V4_SELECTION_BIAS"]["assumption_violation_rate"] < .95: e.append("V4 selection falsification")
    if s["V5_WEAK_RELEVANCE"]["insufficient_information_rate"] < .95: e.append("V5 weak-information abstention")
    v6=s["V6_COORDINATED_EXCLUSION"]
    if v6["candidate_rate"] < .90: e.append("V6 candidate-under-assumptions rate")
    if v6["median_abs_beta_error_vs_true_0p8"] < .30: e.append("V6 did not expose wrong causal coefficient")
    if v6["causal_authority_count"] != 0 or v6["exclusion_debt_rate"] != 1.0: e.append("V6 unsafe authority/debt")
    v7=s["V7_LABEL_CORRUPTION"]
    if v7["candidate_rate"] < .90: e.append("V7 candidate-under-assumptions rate")
    if v7["causal_authority_count"] != 0 or v7["measurement_debt_rate"] != 1.0: e.append("V7 unsafe measurement authority")
    for fam,fs in s.items():
        if fs["causal_authority_count"] != 0: e.append(f"{fam} emitted causal authority")
    return not e,e


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    RESULT.mkdir(parents=True, exist_ok=True)
    started=time.perf_counter()
    cohort_summaries={}; all_rows=[]; cohort_errors={}
    for name,seeds in COHORTS.items():
        summary,rows=run_cohort(name,seeds)
        ok,err=cohort_pass(summary)
        cohort_summaries[name]=summary; cohort_errors[name]=err; all_rows.extend(rows)
    exact=coordinated_exclusion_counterexample(seed=88008,n=4096)
    exact_ok=(exact.max_x_path_error < 1e-12 and exact.max_y_path_error < 1e-12 and exact.max_w_path_error < 1e-12 and abs(exact.beta_valid_reparameterized-exact.beta_invalid)>=.49)
    scientific_pass=all(not errs for errs in cohort_errors.values()) and exact_ok
    verdict={
        "experiment_id":"CSCA-08A/B",
        "verdict":"OBSERVATIONAL_IDENTIFYING_CONTRACT_QUALIFIED_SYNTHETIC_NARROWED" if scientific_pass else "OBSERVATIONAL_IDENTIFYING_CONTRACT_NOT_QUALIFIED",
        "scientific_pass":scientific_pass,
        "authority":"CAUSAL_CANDIDATE_UNDER_EXPLICIT_ASSUMPTIONS_ONLY" if scientific_pass else "PASSIVE_PREDICTIVE_FALSIFICATION_ONLY",
        "alpha":.01,
        "rows_per_seed_before_selection":4096,
        "seeds_per_family_per_cohort":128,
        "cohorts":cohort_summaries,
        "cohort_errors":cohort_errors,
        "coordinated_exclusion_exact_counterexample":exact.__dict__ if hasattr(exact,'__dict__') else {
            "beta_invalid":exact.beta_invalid,
            "beta_valid_reparameterized":exact.beta_valid_reparameterized,
            "direct_effect_scale":exact.direct_effect_scale,
            "max_x_path_error":exact.max_x_path_error,
            "max_y_path_error":exact.max_y_path_error,
            "max_w_path_error":exact.max_w_path_error,
        },
        "exact_counterexample_pass":exact_ok,
        "epistemic_boundary":{
            "exclusion_fully_testable_from_factual_channel":False,
            "full_exogeneity_proven_from_negative_control":False,
            "regime_measurement_reliability_proven_from_moments":False,
            "unconditional_causal_truth":False,
            "semantic_causality":False,
            "replay_control":False,
            "active_control":False,
        },
        "wall_seconds":time.perf_counter()-started,
    }
    fields=list(all_rows[0].keys())
    with (OUT/"seed_results.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(all_rows)
    (OUT/"verdict.json").write_text(json.dumps(verdict,indent=2,sort_keys=True)+"\n")
    (RESULT/"verdict.json").write_text(json.dumps(verdict,indent=2,sort_keys=True)+"\n")
    files=[OUT/"seed_results.csv",OUT/"verdict.json"]
    (OUT/"SHA256SUMS").write_text("".join(f"{_sha(p)}  {p.name}\n" for p in files))
    print(json.dumps(verdict,indent=2,sort_keys=True))
    return 0 if scientific_pass else 2

if __name__ == "__main__":
    raise SystemExit(main())
