from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import asdict
from pathlib import Path

from cwc.epistemics.information_acquisition import (
    InformationAction,
    select_decision_relevant_information_action,
    select_maximin_information_action,
)

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/cog-info-02"
RES = ROOT / "research/results/COG-INFO-02"
ALPHA = 0.01
POWER = 0.95
N = 128
COHORTS = {"PRIMARY": 104201, "REPLICATION": 204201}
FAMILIES = [f"D{i}" for i in range(12)]


def ia(name: str, cost: float, rates: dict[str, float], cert: str = "CERTIFIED_LOWER_BOUND", max_units: int | None = None) -> InformationAction:
    return InformationAction(name, cost, rates, cert, max_units=max_units)


def decide(actions, alt_decisions, budget, candidate="A"):
    return select_decision_relevant_information_action(
        actions=actions,
        candidate_decision=candidate,
        alternative_decisions=alt_decisions,
        alpha=ALPHA,
        target_power=POWER,
        available_budget=budget,
    )


def family_case(fam: str, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    legacy = None
    expected_action = None
    extra: dict[str, object] = {}

    if fam == "D0":
        actions = [ia("q", 1.0, {"s1": rng.uniform(0.0, 0.3), "s2": rng.uniform(0.0, 0.3)})]
        alts = {"s1": "A", "s2": "A"}; budget = 100.0
        expected = "DECISION_ALREADY_IDENTIFIED_NO_ACQUISITION"
    elif fam == "D1":
        flip_rate = rng.uniform(0.16, 0.28)
        actions = [ia("decisive", 1.0, {"same": 0.0, "flip": flip_rate})]
        alts = {"same": "A", "flip": "B"}; budget = 100.0
        expected = "ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"; expected_action="decisive"
        legacy = select_maximin_information_action(actions=actions, unresolved_alternatives=("same","flip"), alpha=ALPHA, target_power=POWER, available_budget=budget)
        extra["legacy_state"] = legacy.state
    elif fam == "D2":
        actions = [ia("q1", 1.0, {"same": rng.uniform(0.2,1.0), "flip": 0.0}), ia("q2", 2.0, {"same": rng.uniform(0.2,1.0), "flip": 0.0})]
        alts = {"same":"A","flip":"B"}; budget=1000.0
        expected="NO_DECISION_IDENTIFYING_INFORMATION_CHANNEL"; expected_action="q1"
    elif fam == "D3":
        r1=rng.uniform(0.08,0.14); c1=rng.uniform(0.8,1.2); r2=rng.uniform(0.24,0.38); c2=rng.uniform(3.0,4.8)
        actions=[ia("q1",c1,{"flip":r1}),ia("q2",c2,{"flip":r2})]
        alts={"flip":"B"}; budget=200.0; expected="ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"
        scores={a.action_id:a.information_rate_lower_bounds["flip"]/a.unit_cost for a in actions}; expected_action=max(scores,key=lambda k:(scores[k],-next(a.unit_cost for a in actions if a.action_id==k),k))
    elif fam == "D4":
        actions=[ia("nuisance",1.0,{"same":rng.uniform(5,12),"flip":rng.uniform(0.008,0.018)}),ia("decision",1.0,{"same":rng.uniform(0.0001,0.003),"flip":rng.uniform(0.10,0.18)})]
        alts={"same":"A","flip":"B"}; budget=100.0; expected="ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"; expected_action="decision"
    elif fam == "D5":
        rate=rng.uniform(0.16,0.24)
        actions=[ia("capacity",1.0,{"flip":rate},max_units=rng.randint(3,8))]
        alts={"flip":"B"}; budget=1000.0; expected="DECISION_ACTION_CAPACITY_BELOW_NECESSARY_BOUND"; expected_action="capacity"
    elif fam == "D6":
        rate=rng.uniform(0.16,0.24); actions=[ia("budget",1.0,{"flip":rate},max_units=1000)]
        alts={"flip":"B"}; budget=rng.uniform(1.0,8.0); expected="INSUFFICIENT_DECISION_INFORMATION_BUDGET"; expected_action="budget"
    elif fam == "D7":
        b1=rng.uniform(0.10,0.14); b2=rng.uniform(0.10,0.14)
        actions=[ia("balanced",1.0,{"f1":b1,"f2":b2}),ia("specialized",1.0,{"f1":rng.uniform(0.35,0.5),"f2":rng.uniform(0.015,0.035)})]
        alts={"f1":"B","f2":"C"}; budget=100.0; expected="ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"; expected_action="balanced"
    elif fam == "D8":
        actions=[ia("uncert",0.1,{"flip":99.0},cert="POINT_ESTIMATE"),ia("cert",1.0,{"flip":rng.uniform(0.12,0.2)})]
        alts={"flip":"B"}; budget=100.0; expected="ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"; expected_action="cert"
    elif fam == "D9":
        actions=[ia("partial",0.1,{"f1":99.0}),ia("complete",1.0,{"f1":rng.uniform(0.12,0.18),"f2":rng.uniform(0.12,0.18)})]
        alts={"f1":"B","f2":"C"}; budget=100.0; expected="ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"; expected_action="complete"
    elif fam == "D10":
        actions=[ia("z",2.0,{"f1":rng.uniform(0.24,0.30),"f2":rng.uniform(0.20,0.24)}),ia("a",1.0,{"f1":rng.uniform(0.10,0.12),"f2":rng.uniform(0.10,0.12)})]
        alts={"f2":"C","same":"A","f1":"B"}; budget=100.0; expected="ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"
        d1=decide(actions,alts,budget); d2=decide(list(reversed(actions)),dict(reversed(list(alts.items()))),budget)
        expected_action=d1.action_id; extra["permutation_equal"]=(d1==d2)
    elif fam == "D11":
        same=rng.uniform(0.015,0.03); flip=rng.uniform(0.18,0.28)
        actions=[ia("q",1.0,{"same":same,"flip":flip})]
        alts={"same":"A","flip":"B"}; budget=400.0; expected="ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"; expected_action="q"
        legacy=select_maximin_information_action(actions=actions, unresolved_alternatives=("same","flip"), alpha=ALPHA,target_power=POWER,available_budget=budget)
        extra["legacy_state"]=legacy.state; extra["legacy_cost"]=legacy.necessary_cost_lower_bound
    else:
        raise KeyError(fam)

    out=decide(actions,alts,budget)
    passed = out.state==expected and (expected_action is None or out.action_id==expected_action)
    if fam=="D1":
        passed = passed and legacy is not None and legacy.state=="NO_IDENTIFYING_INFORMATION_CHANNEL"
    if fam=="D10":
        passed = passed and extra["permutation_equal"] is True
    if fam=="D11":
        passed = passed and legacy is not None and legacy.state=="ACQUIRE_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE" and out.necessary_cost_lower_bound < legacy.necessary_cost_lower_bound
    return {
        "family":fam,"seed":seed,"expected_state":expected,"observed_state":out.state,
        "expected_action":expected_action,"observed_action":out.action_id,"pass":bool(passed),
        "necessary_cost":out.necessary_cost_lower_bound,"cross_count":len(out.cross_decision_alternatives),
        "same_count":len(out.ignored_same_decision_alternatives),**extra,
    }


def run() -> dict[str, object]:
    ART.mkdir(parents=True,exist_ok=True); RES.mkdir(parents=True,exist_ok=True)
    rows=[]; cohorts={}; errors=[]
    for cname,base in COHORTS.items():
        famstats={}
        for fi,fam in enumerate(FAMILIES):
            famrows=[]
            for i in range(N):
                seed=base+fi*1000+i
                try: row=family_case(fam,seed)
                except Exception as exc:
                    errors.append({"cohort":cname,"family":fam,"seed":seed,"error":repr(exc)}); continue
                row["cohort"]=cname; rows.append(row); famrows.append(row)
            famstats[fam]={
                "n":len(famrows),"pass_count":sum(bool(r["pass"]) for r in famrows),
                "pass_rate":sum(bool(r["pass"]) for r in famrows)/len(famrows) if famrows else 0.0,
                "false_spend_count":sum(r["observed_state"].startswith("ACQUIRE_") and fam in {"D0","D2","D5","D6"} for r in famrows),
                "wrong_action_count":sum((r["expected_action"] is not None and r["observed_action"]!=r["expected_action"]) for r in famrows),
                "permutation_disagreement_count":sum(r.get("permutation_equal") is False for r in famrows),
                "legacy_rescue_count":sum((fam=="D1" and r.get("legacy_state")=="NO_IDENTIFYING_INFORMATION_CHANNEL" and r["observed_state"].startswith("ACQUIRE_")) for r in famrows),
                "strict_cost_improvement_count":sum((fam=="D11" and math.isfinite(float(r.get("legacy_cost",math.inf))) and float(r["necessary_cost"])<float(r.get("legacy_cost",math.inf))) for r in famrows),
            }
        cohorts[cname]={"seed_base":base,"families":famstats}
    verdict={
        "experiment_id":"COG-INFO-02",
        "verdict":"DECISION_RELEVANT_INFORMATION_GOVERNOR_QUALIFIED_SYNTHETIC_NARROWED",
        "scientific_pass":not errors and all(s["pass_count"]==N for c in cohorts.values() for s in c["families"].values()),
        "authority":"DECISION_INFORMATION_ALLOCATION_PRIMITIVE_ONLY",
        "alpha":ALPHA,"target_power":POWER,"n_per_family_per_cohort":N,
        "preconfirmatory_preregistration_commit":"87dbd88ae9f8cc72c15db6128d08a9fa25464e59",
        "implementation_commit":"3283c09",
        "cohorts":cohorts,"errors":errors,
        "novelty_status":"UNKNOWN_OVERLAP_CONCEDED",
        "non_promotion_boundary":{
            "semantic_causal_truth":False,"active_control":False,"real_world_planning_value":False,
            "large_model_transfer":False,"pareto_superiority":False,"external_replication":False,
        },
    }
    with (ART/"matrix.csv").open("w",newline="") as f:
        fieldnames=sorted({k for r in rows for k in r}); w=csv.DictWriter(f,fieldnames=fieldnames); w.writeheader(); w.writerows(rows)
    (ART/"verdict.json").write_text(json.dumps(verdict,indent=2,sort_keys=True)+"\n")
    (RES/"verdict.json").write_text(json.dumps(verdict,indent=2,sort_keys=True)+"\n")
    return verdict

if __name__=="__main__":
    v=run(); print(json.dumps(v,indent=2,sort_keys=True)); raise SystemExit(0 if v["scientific_pass"] else 1)
