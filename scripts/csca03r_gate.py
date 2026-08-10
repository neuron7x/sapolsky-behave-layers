from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "research/results/CSCA-03R/verdict.json"
ROBUST = ROOT / "research/results/CSCA-03R/postconfirmatory_robustness.json"
THEORY = ROOT / "research/results/CSCA-03R/theory_verification.json"
INVALID = ROOT / "research/results/CSCA-03-INVALID/verdict.json"
SUMS = ROOT / "research/results/CSCA-03R/SHA256SUMS"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def gunzip_sha(path: Path) -> str:
    h = hashlib.sha256()
    with gzip.open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def hash_seed_outputs() -> list[str]:
    code = r'''
import json, random
from cwc.credit.budgeted_shapley import legacy_independent_mc
from experiments.csca_03_budgeted_credit.environment import PLAYERS, generate_cases, make_evaluator, stable_seed
case=generate_cases(family="E0_SINGLE_CAUSE",seed=62000,n=1)[0]
est=legacy_independent_mc(case.factual,PLAYERS,make_evaluator(case),permutations=8,rng=random.Random(stable_seed(62000,"E0_SINGLE_CAUSE",0,32,"LEGACY_INDEPENDENT_MC")))
print(json.dumps(est.credits,sort_keys=True,separators=(",",":")))
'''
    out=[]
    for value in ("1","2","3","4","5"):
        env=dict(os.environ);env["PYTHONHASHSEED"]=value
        p=subprocess.run([sys.executable,"-c",code],cwd=ROOT,env=env,text=True,capture_output=True,check=True)
        out.append(p.stdout.strip())
    return out


def validate(*, result_override=None, robust_override=None, theory_override=None) -> list[str]:
    errors=[]
    required=[
        ROOT/"experiments/csca_03r_budgeted_credit/PREREGISTRATION.md",
        ROOT/"research/governance/H4-CSCA-03R-AUTHOR-DIRECTIVE.json",
        INVALID, RESULT, ROBUST, THEORY,
        ROOT/"research/reports/CSCA_03R_EXECUTION_REPORT.md",
        ROOT/"research/ruins/CSCA-03-LEGACY-HASH-NONDETERMINISM.md",
        SUMS,
    ]
    for cohort in ("calibration","primary","replication"):
        required += [ROOT/f"artifacts/csca-03r/{cohort}/{name}" for name in ("case_results.csv.gz","aggregate.csv","context_authority.csv","summary.json")]
    for p in required:
        if not p.is_file(): errors.append(f"missing {p.relative_to(ROOT)}")
    if errors:return errors

    invalid=load(INVALID)
    if invalid.get("scientific_pass") is not False or invalid.get("instrument_valid") is not False:
        errors.append("invalid CSCA-03 comparator result was silently rehabilitated")

    result=result_override if result_override is not None else load(RESULT)
    robust=robust_override if robust_override is not None else load(ROBUST)
    theory=theory_override if theory_override is not None else load(THEORY)
    if result.get("verdict") != "CSCA_03R_COUPLED_ESTIMATOR_QUALIFIED" or result.get("scientific_pass") is not True:
        errors.append("CSCA-03R qualification verdict drift")
    for k in ("architecture_promotion_authority","shadow_inference_authority","variance_only_authority"):
        if result.get(k) is not False:errors.append(f"unauthorized {k}")
    if result.get("human_h5_required") is not True:errors.append("H5 requirement removed")
    if not result.get("predicates") or not all(v is True for v in result["predicates"].values()):
        errors.append("one or more confirmatory predicates failed/drifted")

    if robust.get("status") != "POST_CONFIRMATORY_ROBUSTNESS_NO_CLAIM_UPGRADE_AUTHORITY":
        errors.append("robustness authority boundary drift")
    for cohort in ("primary","replication"):
        c=robust.get(cohort,{})
        if c.get("context_authority_states") != {"CONTEXT_CONDITIONAL_ONLY":3072}:
            errors.append(f"{cohort} context authority drift")
        for b in ("8","16","32","64","128","256"):
            n=c.get("variance_ceiling_nonnecessity",{}).get(b,{})
            if n.get("max_false_credit_mass") != 0.0 or n.get("exceeds_diagnostic_ceiling") is not True:
                errors.append(f"{cohort} variance nonnecessity drift {b}")
        for b in ("64","128","256"):
            n=c.get("precisely_wrong_model",{}).get(b,{})
            if not (n.get("mean_false_credit_mass_true")==0.9 and n.get("mean_estimator_variance",1)>0 and n.get("mean_estimator_variance",1)<1e-30 and n.get("rmse_to_wrong_model_teacher",1)<1e-12):
                errors.append(f"{cohort} precisely-wrong counterexample drift {b}")

    if theory.get("crn_unbiased_exact") is not True or theory.get("structural_null_C_D_exact_per_draw") is not True:
        errors.append("exact rational mechanism check failed")
    if theory.get("matched_budget_antithetic_over_crn_mse_ratio_fraction") != "192/373":
        errors.append("exact MSE-ratio derivation drift")

    try:
        outs=hash_seed_outputs()
        if len(set(outs)) != 1: errors.append("corrected legacy comparator still depends on PYTHONHASHSEED")
    except Exception as exc:
        errors.append(f"determinism probe failed: {exc}")

    expected={"calibration":(32,5512448),"primary":(128,22049792),"replication":(128,22049792)}
    for cohort,(nseeds,nevals) in expected.items():
        base=ROOT/f"artifacts/csca-03r/{cohort}";s=load(base/"summary.json")
        if s.get("seed_count")!=nseeds or s.get("total_structural_evaluations")!=nevals:errors.append(f"{cohort} compute ledger drift")
        if gunzip_sha(base/"case_results.csv.gz") != s["artifacts"]["case_results_sha256"]:errors.append(f"{cohort} raw decompressed hash mismatch")
        if sha(base/"aggregate.csv") != s["artifacts"]["aggregate_sha256"]:errors.append(f"{cohort} aggregate hash mismatch")
        if sha(base/"context_authority.csv") != s["artifacts"]["context_authority_sha256"]:errors.append(f"{cohort} context hash mismatch")

    for line in SUMS.read_text().splitlines():
        if not line.strip():continue
        digest,rel=line.split(None,1);p=ROOT/rel.strip()
        if not p.is_file():errors.append(f"bound artifact missing {rel.strip()}")
        elif sha(p)!=digest:errors.append(f"checksum drift {rel.strip()}")
    return errors


def self_test()->list[str]:
    v=load(RESULT);r=load(ROBUST);t=load(THEORY);mut=[]
    x=json.loads(json.dumps(v));x["shadow_inference_authority"]=True;mut.append((x,r,t,"shadow promotion"))
    x=json.loads(json.dumps(v));x["variance_only_authority"]=True;mut.append((x,r,t,"variance promotion"))
    x=json.loads(json.dumps(v));x["predicates"]["primary_e0_crn_zero_false"]=False;mut.append((x,r,t,"predicate erasure"))
    y=json.loads(json.dumps(r));y["primary"]["precisely_wrong_model"]["64"]["mean_false_credit_mass_true"]=0.0;mut.append((v,y,t,"wrong-model attack erasure"))
    z=json.loads(json.dumps(t));z["matched_budget_antithetic_over_crn_mse_ratio_fraction"]="1/1";mut.append((v,r,z,"theory rewrite"))
    failures=[]
    for a,b,c,label in mut:
        if not validate(result_override=a,robust_override=b,theory_override=c):failures.append(label)
    return failures


def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");a=p.parse_args();errs=self_test() if a.self_test else validate()
    if errs:
        print("CSCA03R-GATE: FAIL");[print(" -",e) for e in errs];return 1
    if a.self_test:print("CSCA03R-GATE SELF-TEST: PASS 5/5 semantic corruptions detected")
    else:print("CSCA03R-GATE: PASS fresh_primary=128 fresh_replication=128 valid_evals=49612032 shadow_authority=false")
    return 0
if __name__=="__main__":raise SystemExit(main())
