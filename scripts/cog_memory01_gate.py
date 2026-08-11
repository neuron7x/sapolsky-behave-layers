from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"artifacts/cog-memory-01"
VERDICT=ROOT/"research/results/COG-MEMORY-01/verdict.json"
FAMILIES={f"M{i}" for i in range(12)}
UNSAFE={"M0","M1","M2","M3","M5","M6","M7","M8","M9","M10"}


def _sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()


def _validate(v:dict)->list[str]:
    e=[]
    if v.get("verdict")!="ASSUMPTION_AWARE_MEMORY_CONSOLIDATION_QUALIFIED_SYNTHETIC_NARROWED": e.append("verdict drift")
    if v.get("scientific_pass") is not True: e.append("scientific pass drift")
    if v.get("authority")!="EPISTEMIC_MEMORY_PRIMITIVE_ONLY": e.append("authority drift")
    if v.get("preconfirmatory_preregistration_commit")!="6746ab022fa8cda066ebfe66bcca4634d6881973": e.append("prereg commit drift")
    if v.get("errors")!=[]: e.append("execution errors")
    policy=v.get("memory_policy",{})
    false_keys=("observed_predictive_are_causal","assumption_conditional_causal_consolidation_allowed","terminal_states_can_create_active_causal_memory","legacy_string_authority_allowed","in_place_authority_upgrade_allowed")
    for k in false_keys:
        if policy.get(k) is not False: e.append("unsafe policy "+k)
    true_keys=("intervention_supported_requires_empty_countermodel_set","transitive_dependency_retraction_required","assumption_invalidation_retraction_required")
    for k in true_keys:
        if policy.get(k) is not True: e.append("missing policy "+k)
    for k,val in v.get("non_promotion_boundary",{}).items():
        if val is not False: e.append("unsafe non-promotion "+k)
    expected={"PRIMARY":82001,"REPLICATION":92001}
    for cohort,seed in expected.items():
        c=v.get("cohorts",{}).get(cohort,{})
        if c.get("seed_base")!=seed: e.append(cohort+" seed")
        if set(c.get("families",{}))!=FAMILIES: e.append(cohort+" families")
        for fam,fs in c.get("families",{}).items():
            if fs.get("n")!=128 or fs.get("pass_count")!=128 or fs.get("pass_rate")!=1.0: e.append(f"{cohort} {fam} pass")
            if fam in UNSAFE and fs.get("false_causal_consolidation_count")!=0: e.append(f"{cohort} {fam} false causal")
            if fs.get("event_chain_failure_count")!=0 or fs.get("invariant_failure_count")!=0: e.append(f"{cohort} {fam} integrity")
        if c["families"]["M7"].get("required_transitive_retraction_rate")!=1.0: e.append(cohort+" M7 retraction")
        if c["families"]["M8"].get("required_transitive_retraction_rate")!=1.0: e.append(cohort+" M8 retraction")
        if c["families"]["M9"].get("tampered_binding_acceptance_rate")!=0.0: e.append(cohort+" M9 tamper")
        if c["families"]["M10"].get("legacy_string_injection_acceptance_rate")!=0.0: e.append(cohort+" M10 legacy")
        if c["families"]["M4"].get("false_causal_consolidation_count")!=0: e.append(cohort+" M4 unexpected metric")
    return e


def main()->int:
    e=[]
    for p in (ART/"verdict.json",ART/"memory_matrix.csv",ART/"SHA256SUMS",VERDICT):
        if not p.is_file(): e.append("missing "+str(p.relative_to(ROOT)))
    if e:
        print("COG-MEMORY01-GATE FAIL",*e,sep="\n - "); return 1
    for line in (ART/"SHA256SUMS").read_text().splitlines():
        want,name=line.split("  ",1); p=ART/name
        if not p.is_file() or _sha(p)!=want: e.append("checksum "+name)
    if _sha(ART/"verdict.json")!=_sha(VERDICT): e.append("artifact/research verdict mismatch")
    v=json.loads(VERDICT.read_text()); e.extend(_validate(v))
    if "--self-test" in sys.argv:
        mutants=[]
        m=json.loads(json.dumps(v)); m["memory_policy"]["assumption_conditional_causal_consolidation_allowed"]=True; mutants.append(m)
        m=json.loads(json.dumps(v)); m["cohorts"]["PRIMARY"]["families"]["M5"]["false_causal_consolidation_count"]=1; mutants.append(m)
        m=json.loads(json.dumps(v)); m["cohorts"]["REPLICATION"]["families"]["M7"]["required_transitive_retraction_rate"]=0.99; mutants.append(m)
        m=json.loads(json.dumps(v)); m["cohorts"]["PRIMARY"]["families"]["M10"]["legacy_string_injection_acceptance_rate"]=1/128; mutants.append(m)
        m=json.loads(json.dumps(v)); m["non_promotion_boundary"]["active_control"]=True; mutants.append(m)
        m=json.loads(json.dumps(v)); m["memory_policy"]["in_place_authority_upgrade_allowed"]=True; mutants.append(m)
        killed=sum(bool(_validate(m)) for m in mutants)
        if killed!=len(mutants): e.append(f"self-test killed {killed}/{len(mutants)}")
        else: print(f"COG-MEMORY01-GATE SELF-TEST: {killed}/{len(mutants)} consolidation/retraction mutations killed")
    if e:
        print("COG-MEMORY01-GATE FAIL",*e,sep="\n - "); return 1
    print("COG-MEMORY01-GATE PASS: typed epistemic memory blocks false causal consolidation and propagates parent/assumption retractions transitively in both cohorts.")
    return 0


if __name__=="__main__": raise SystemExit(main())
