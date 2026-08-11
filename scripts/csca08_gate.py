#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/csca-08-regime-identifiability"
VERDICT = ROOT / "research/results/CSCA-08A/verdict.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _validate(v: dict) -> list[str]:
    e: list[str] = []
    if v.get("verdict") != "OBSERVATIONAL_IDENTIFYING_CONTRACT_QUALIFIED_SYNTHETIC_NARROWED":
        e.append("verdict drift")
    if v.get("scientific_pass") is not True:
        e.append("scientific_pass drift")
    if v.get("authority") != "CAUSAL_CANDIDATE_UNDER_EXPLICIT_ASSUMPTIONS_ONLY":
        e.append("authority drift")
    b=v.get("epistemic_boundary",{})
    for key in (
        "exclusion_fully_testable_from_factual_channel",
        "full_exogeneity_proven_from_negative_control",
        "regime_measurement_reliability_proven_from_moments",
        "unconditional_causal_truth",
        "semantic_causality",
        "replay_control",
        "active_control",
    ):
        if b.get(key) is not False:
            e.append("unsafe epistemic boundary "+key)
    if v.get("exact_counterexample_pass") is not True:
        e.append("exact counterexample pass drift")
    x=v.get("coordinated_exclusion_exact_counterexample",{})
    if abs(float(x.get("beta_valid_reparameterized",0))-float(x.get("beta_invalid",0))) < .49:
        e.append("coordinated-exclusion beta ambiguity erased")
    for k in ("max_x_path_error","max_y_path_error","max_w_path_error"):
        if float(x.get(k,1.0)) >= 1e-12:
            e.append("observational equivalence broken "+k)

    for cohort in ("PRIMARY","REPLICATION"):
        s=v["cohorts"][cohort]
        v0=s["V0_VALID"]
        if v0["candidate_rate"] < .95 or v0["assumption_violation_rate"] > .04 or v0["median_abs_beta_error_vs_true_0p8"] > .05:
            e.append(cohort+" V0")
        if s["V1_DIRECT_NONPROPORTIONAL"]["assumption_violation_rate"] < .95:
            e.append(cohort+" V1")
        if s["V2_R_U_CONFOUNDING"]["assumption_violation_rate"] < .95:
            e.append(cohort+" V2")
        v3=s["V3_ALEATORIC_HIGH"]
        if v3["candidate_rate"] < .90 or v3["median_abs_beta_error_vs_true_0p8"] > .10:
            e.append(cohort+" V3")
        if s["V4_SELECTION_BIAS"]["assumption_violation_rate"] < .95:
            e.append(cohort+" V4")
        if s["V5_WEAK_RELEVANCE"]["insufficient_information_rate"] < .95:
            e.append(cohort+" V5")
        v6=s["V6_COORDINATED_EXCLUSION"]
        if v6["candidate_rate"] < .90 or v6["median_abs_beta_error_vs_true_0p8"] < .30:
            e.append(cohort+" V6 ambiguity")
        if v6["causal_authority_count"] != 0 or v6["exclusion_debt_rate"] != 1.0:
            e.append(cohort+" V6 unsafe authority")
        v7=s["V7_LABEL_CORRUPTION"]
        if v7["candidate_rate"] < .90 or v7["causal_authority_count"] != 0 or v7["measurement_debt_rate"] != 1.0:
            e.append(cohort+" V7")
        for fam,fs in s.items():
            if int(fs["causal_authority_count"]) != 0:
                e.append(cohort+" "+fam+" emitted unconditional causal authority")
    return e


def main() -> int:
    errors: list[str] = []
    for p in (ART/"seed_results.csv", ART/"verdict.json", ART/"SHA256SUMS", VERDICT):
        if not p.is_file():
            errors.append("missing "+str(p.relative_to(ROOT)))
    if errors:
        print("CSCA08-GATE FAIL", *errors, sep="\n - ")
        return 1
    for line in (ART/"SHA256SUMS").read_text().splitlines():
        expected,name=line.split("  ",1); p=ART/name
        if not p.is_file() or _sha(p)!=expected:
            errors.append("checksum "+name)
    if _sha(ART/"verdict.json") != _sha(VERDICT):
        errors.append("artifact/research verdict mismatch")
    v=json.loads(VERDICT.read_text())
    errors.extend(_validate(v))
    if "--self-test" in sys.argv:
        mutants=[]
        m=json.loads(json.dumps(v)); m["epistemic_boundary"]["unconditional_causal_truth"]=True; mutants.append(m)
        m=json.loads(json.dumps(v)); m["cohorts"]["PRIMARY"]["V6_COORDINATED_EXCLUSION"]["causal_authority_count"]=1; mutants.append(m)
        m=json.loads(json.dumps(v)); m["coordinated_exclusion_exact_counterexample"]["max_y_path_error"]=.01; mutants.append(m)
        m=json.loads(json.dumps(v)); m["cohorts"]["REPLICATION"]["V5_WEAK_RELEVANCE"]["insufficient_information_rate"]=0.0; mutants.append(m)
        m=json.loads(json.dumps(v)); m["epistemic_boundary"]["exclusion_fully_testable_from_factual_channel"]=True; mutants.append(m)
        killed=sum(bool(_validate(m)) for m in mutants)
        if killed != len(mutants):
            errors.append(f"self-test killed {killed}/{len(mutants)}")
        else:
            print(f"CSCA08-GATE SELF-TEST: {killed}/{len(mutants)} authority/identifiability mutations killed")
    if errors:
        print("CSCA08-GATE FAIL", *errors, sep="\n - ")
        return 1
    print("CSCA08-GATE PASS: synthetic regime identifying contract qualified narrowly; coordinated-exclusion equivalence keeps unconditional causal authority blocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
