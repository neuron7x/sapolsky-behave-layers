from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ART=ROOT/"artifacts/cog-info-02"; RES=ROOT/"research/results/COG-INFO-02/verdict.json"
FAMS={f"D{i}" for i in range(12)}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(v):
    e=[]
    if v.get("verdict")!="DECISION_RELEVANT_INFORMATION_GOVERNOR_QUALIFIED_SYNTHETIC_NARROWED": e.append("verdict")
    if v.get("scientific_pass") is not True: e.append("scientific_pass")
    if v.get("authority")!="DECISION_INFORMATION_ALLOCATION_PRIMITIVE_ONLY": e.append("authority")
    if v.get("preconfirmatory_preregistration_commit")!="87dbd88ae9f8cc72c15db6128d08a9fa25464e59": e.append("prereg")
    if v.get("alpha")!=0.01 or v.get("target_power")!=0.95 or v.get("errors")!=[]: e.append("design/errors")
    if v.get("novelty_status")!="UNKNOWN_OVERLAP_CONCEDED": e.append("novelty overclaim")
    for k,val in v.get("non_promotion_boundary",{}).items():
        if val is not False: e.append("unsafe promotion "+k)
    for cohort,base in {"PRIMARY":104201,"REPLICATION":204201}.items():
        c=v.get("cohorts",{}).get(cohort,{})
        if c.get("seed_base")!=base or set(c.get("families",{}))!=FAMS: e.append(cohort+" shape")
        for fam,s in c.get("families",{}).items():
            if s.get("n")!=128 or s.get("pass_count")!=128 or s.get("pass_rate")!=1.0: e.append(cohort+" "+fam+" pass")
            if fam in {"D0","D2","D5","D6"} and s.get("false_spend_count")!=0: e.append(cohort+" "+fam+" false spend")
            if fam in {"D3","D4","D7","D8","D9","D10","D11"} and s.get("wrong_action_count")!=0: e.append(cohort+" "+fam+" wrong action")
        if c["families"]["D1"].get("legacy_rescue_count")!=128: e.append(cohort+" D1 rescue")
        if c["families"]["D10"].get("permutation_disagreement_count")!=0: e.append(cohort+" D10 permutation")
        if c["families"]["D11"].get("strict_cost_improvement_count")!=128: e.append(cohort+" D11 cost")
    return e

def main():
    e=[]
    for p in (ART/"verdict.json",ART/"matrix.csv",ART/"SHA256SUMS",RES):
        if not p.is_file(): e.append("missing "+str(p.relative_to(ROOT)))
    if e: print("COG-INFO02-GATE FAIL",*e,sep="\n - "); return 1
    for line in (ART/"SHA256SUMS").read_text().splitlines():
        want,name=line.split("  ",1); p=ART/name
        if not p.is_file() or sha(p)!=want: e.append("checksum "+name)
    if sha(ART/"verdict.json")!=sha(RES): e.append("verdict mismatch")
    v=json.loads(RES.read_text()); e.extend(validate(v))
    if "--self-test" in sys.argv:
        muts=[]
        m=json.loads(json.dumps(v)); m["scientific_pass"]=False; muts.append(m)
        m=json.loads(json.dumps(v)); m["cohorts"]["PRIMARY"]["families"]["D0"]["false_spend_count"]=1; muts.append(m)
        m=json.loads(json.dumps(v)); m["cohorts"]["REPLICATION"]["families"]["D1"]["legacy_rescue_count"]=127; muts.append(m)
        m=json.loads(json.dumps(v)); m["cohorts"]["PRIMARY"]["families"]["D11"]["strict_cost_improvement_count"]=127; muts.append(m)
        m=json.loads(json.dumps(v)); m["novelty_status"]="NOVEL"; muts.append(m)
        m=json.loads(json.dumps(v)); m["non_promotion_boundary"]["active_control"]=True; muts.append(m)
        killed=sum(bool(validate(m)) for m in muts)
        if killed!=len(muts): e.append(f"self-test killed {killed}/{len(muts)}")
        else: print(f"COG-INFO02-GATE SELF-TEST: {killed}/{len(muts)} authority/novelty mutations killed")
    if e: print("COG-INFO02-GATE FAIL",*e,sep="\n - "); return 1
    print("COG-INFO02-GATE PASS: same-decision ambiguity cannot waste/veto decision information, cross-decision zero-rate remains fail-closed.")
    return 0
if __name__=="__main__": raise SystemExit(main())
