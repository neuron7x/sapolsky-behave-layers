from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import random
import time

from cwc.epistemics.information_acquisition import InformationAction
from cwc.epistemics.lattice import EpistemicMachine, EpistemicRecord, EvidenceKind, EvidenceRef, EvidenceSource
from cwc.memory.epistemic_store import EpistemicMemoryLedger
from cwc.planning.proof_carrying import PlanState, WorldBranch, plan_counterfactual, verify_plan_certificate

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/cog-plan-01"
RESULT = ROOT / "research/results/COG-PLAN-01"
COHORTS = {"PRIMARY": 83001, "REPLICATION": 93001}
N = 128
FAMILIES = tuple(f"P{i}" for i in range(12))
PREREG_COMMIT = "4c1489a1a7102827a7f3de701af04aaee08de396"
MARGIN = 0.05


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _ev(label: str, kind: EvidenceKind, source: EvidenceSource, scope: tuple[str, ...]) -> EvidenceRef:
    return EvidenceRef(
        ref=f"plan://{label}", sha256=_sha(label), kind=kind, source=source,
        context_scope=scope, provenance="COG-PLAN-01 confirmatory harness",
    )


def _records(claim: str, scope: tuple[str, ...]) -> tuple[EpistemicRecord, EpistemicRecord, EpistemicRecord]:
    m = EpistemicMachine()
    o = m.observe(claim_id=claim, context_scope=scope, evidence=[_ev(claim+":o", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL, scope)])
    p = m.transition(o, m.issue_predictive_capability(o, evidence=[_ev(claim+":p", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, scope)]))
    a = m.transition(p, m.issue_assumption_capability(p, assumption_ids=("A_PLAN",), evidence=[_ev(claim+":a", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)]))
    inter = m.transition(a, m.issue_intervention_capability(a, operator_id="do(plan-probe)", evidence=[_ev(claim+":i", EvidenceKind.DIRECT_INTERVENTION, EvidenceSource.DIRECT_SYSTEM_REEXECUTION, scope)]))
    return p, a, inter


def _robust_worlds(rng: random.Random, ids=("BASE", "CM1", "CM2")) -> list[WorldBranch]:
    out=[]
    for j,wid in enumerate(ids):
        a=1.0 + rng.uniform(-0.04,0.04)
        b=0.65 + rng.uniform(-0.04,0.04)
        c=0.25 + rng.uniform(-0.03,0.03)
        out.append(WorldBranch(wid,{"A":a,"B":b,"C":c},f"synthetic:{j}"))
    return out


def _reversal_worlds(rng: random.Random) -> list[WorldBranch]:
    return [
        WorldBranch("BASE",{"A":1.0+rng.uniform(0,.02),"B":.2,"C":.1},"synthetic:base"),
        WorldBranch("CM1",{"A":.2,"B":1.0+rng.uniform(0,.02),"C":.1},"synthetic:cm1"),
    ]


def _averaging_trap(rng: random.Random) -> list[WorldBranch]:
    # Arithmetic mean favors A, yet CM2 reverses the action ranking.
    return [
        WorldBranch("BASE",{"A":1.4+rng.uniform(0,.02),"B":.4,"C":.1},"synthetic:base"),
        WorldBranch("CM1",{"A":1.3+rng.uniform(0,.02),"B":.5,"C":.1},"synthetic:cm1"),
        WorldBranch("CM2",{"A":.2,"B":1.0+rng.uniform(0,.02),"C":.1},"synthetic:cm2"),
    ]


def _mutate_worlds(worlds: list[WorldBranch]) -> list[WorldBranch]:
    out=[]
    for j,w in enumerate(worlds):
        u=dict(w.utilities)
        if j==0: u[sorted(u)[0]] += 1e-6
        out.append(WorldBranch(w.world_id,u,w.provenance))
    return out


def _case(cohort: str, base: int, family: str, i: int) -> dict[str, object]:
    seed=base+i
    rng=random.Random((seed*1009)+int(family[1:]))
    scope=(f"PLANCTX:{cohort}:{family}:{i:03d}",)
    claim=f"COG-PLAN-01:{cohort}:{family}:{seed}"
    p,a,inter=_records(claim,scope)
    ledger=EpistemicMemoryLedger()
    info_actions=[]
    budget=0.0
    expected=None
    selected_expected=None
    stale_reject=None
    dropped_reject=None

    if family=="P0":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p); worlds=_robust_worlds(rng); expected=PlanState.ROBUST_ACTION; selected_expected="A"
    elif family=="P1":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p); worlds=_reversal_worlds(rng); expected=PlanState.ABSTAIN_WORLD_DISAGREEMENT
    elif family=="P2":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p); worlds=_averaging_trap(rng); expected=PlanState.ABSTAIN_WORLD_DISAGREEMENT
    elif family=="P3":
        mem=ledger.consolidate(memory_id="m",epistemic_record=inter,countermodel_ids=("CM1","CM2")); worlds=_robust_worlds(rng); expected=PlanState.ROBUST_ACTION; selected_expected="A"
    elif family=="P4":
        mem=ledger.consolidate(memory_id="m",epistemic_record=a); worlds=_robust_worlds(rng); expected=PlanState.ASSUMPTION_CONDITIONAL_PLAN; selected_expected="A"
    elif family=="P5":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p); worlds=_reversal_worlds(rng); expected=PlanState.ACQUIRE_INFORMATION
        info_actions=[InformationAction("probe",1.0,{w.world_id:0.20 for w in worlds},"CERTIFIED_LOWER_BOUND")]; budget=30.0
    elif family=="P6":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p); worlds=_reversal_worlds(rng); expected=PlanState.ABSTAIN_WORLD_DISAGREEMENT
        info_actions=[InformationAction("probe",1.0,{w.world_id:0.20 for w in worlds},"CERTIFIED_LOWER_BOUND")]; budget=10.0
    elif family=="P7":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p); worlds=_reversal_worlds(rng); expected=PlanState.ABSTAIN_WORLD_DISAGREEMENT
        rates={w.world_id:0.20 for w in worlds}; rates[worlds[-1].world_id]=0.0
        info_actions=[InformationAction("probe",1.0,rates,"CERTIFIED_LOWER_BOUND")]; budget=100.0
    elif family=="P8":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p)
        worlds=[WorldBranch("BASE",{"A":1.0,"B":.97,"C":.2},"synthetic:base"),WorldBranch("CM1",{"A":1.0,"B":.7,"C":.2},"synthetic:cm1")]
        expected=PlanState.ABSTAIN_NO_UNIQUE_ROBUST_ACTION
    elif family=="P9":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p); worlds=_robust_worlds(rng); expected=PlanState.ROBUST_ACTION; selected_expected="A"
    elif family=="P10":
        mem=ledger.consolidate(memory_id="m",epistemic_record=p); worlds=_robust_worlds(rng); expected=PlanState.ROBUST_ACTION; selected_expected="A"
    elif family=="P11":
        worlds=_robust_worlds(rng); expected=PlanState.BLOCKED_MEMORY_AUTHORITY
        if i%2==0:
            mem="INTERVENTION_SUPPORTED"
        else:
            old=ledger.consolidate(memory_id="m",epistemic_record=p); ledger.retract("m",reason="pre-plan invalidation"); mem=old
    else: raise AssertionError(family)

    memories=[mem]
    result=plan_counterfactual(
        ledger=ledger,plan_id=f"plan:{cohort}:{family}:{i}",context_scope=scope,
        required_memories=memories,worlds=worlds,robust_margin=MARGIN,
        information_actions=info_actions,available_information_budget=budget,
    )
    cert_valid_before=verify_plan_certificate(result.certificate,ledger=ledger,context_scope=scope,worlds=worlds)
    # Determinism is tested before any P9 retraction.
    result2=plan_counterfactual(
        ledger=ledger,plan_id=f"plan:{cohort}:{family}:{i}",context_scope=scope,
        required_memories=memories,worlds=worlds,robust_margin=MARGIN,
        information_actions=info_actions,available_information_budget=budget,
    )
    digest_deterministic=result.certificate.certificate_digest==result2.certificate.certificate_digest
    mutation_rejected=not verify_plan_certificate(result.certificate,ledger=ledger,context_scope=scope,worlds=_mutate_worlds(worlds))

    if family=="P9":
        ledger.retract("m",reason="post-plan falsification")
        stale_reject=not verify_plan_certificate(result.certificate,ledger=ledger,context_scope=scope,worlds=worlds)
    if family=="P10":
        dropped_reject=not verify_plan_certificate(result.certificate,ledger=ledger,context_scope=scope,worlds=worlds[:-1])

    no_truth_field=all("truth" not in str(k).lower() and "true_causal" not in str(k).lower() for k in result.certificate.payload())
    selected_ok=selected_expected is None or result.selected_action==selected_expected
    special_ok=(stale_reject is not False and dropped_reject is not False)
    ok=(result.state is expected and selected_ok and cert_valid_before and digest_deterministic and mutation_rejected and special_ok and no_truth_field)
    return {
        "cohort":cohort,"family":family,"case":i,"pass":int(ok),
        "state":result.state.value,"selected_action":result.selected_action or "",
        "certificate_valid_before":int(cert_valid_before),"digest_deterministic":int(digest_deterministic),
        "mutated_world_certificate_accepted":int(not mutation_rejected),
        "stale_certificate_accepted":"" if stale_reject is None else int(not stale_reject),
        "dropped_world_certificate_accepted":"" if dropped_reject is None else int(not dropped_reject),
        "no_causal_truth_field":int(no_truth_field),
        "information_state":result.certificate.information_state or "",
        "necessary_information_cost":"" if result.certificate.necessary_information_cost is None else result.certificate.necessary_information_cost,
    }


def run() -> dict[str, object]:
    started=time.perf_counter(); rows=[]; cohorts={}; errors=[]
    expected_states={
        "P0":"ROBUST_ACTION","P1":"ABSTAIN_WORLD_DISAGREEMENT","P2":"ABSTAIN_WORLD_DISAGREEMENT",
        "P3":"ROBUST_ACTION","P4":"ASSUMPTION_CONDITIONAL_PLAN","P5":"ACQUIRE_INFORMATION",
        "P6":"ABSTAIN_WORLD_DISAGREEMENT","P7":"ABSTAIN_WORLD_DISAGREEMENT",
        "P8":"ABSTAIN_NO_UNIQUE_ROBUST_ACTION","P9":"ROBUST_ACTION","P10":"ROBUST_ACTION","P11":"BLOCKED_MEMORY_AUTHORITY",
    }
    for cohort,base in COHORTS.items():
        fams={}
        for family in FAMILIES:
            rr=[_case(cohort,base,family,i) for i in range(N)]; rows.extend(rr)
            pass_count=sum(int(r["pass"]) for r in rr)
            false_robust=sum(1 for r in rr if family in {"P1","P2","P4","P6","P7","P8","P11"} and r["state"]=="ROBUST_ACTION")
            fs={
                "n":N,"pass_count":pass_count,"pass_rate":pass_count/N,
                "expected_state":expected_states[family],"false_robust_action_count":false_robust,
                "certificate_binding_failure_count":sum(1-int(r["certificate_valid_before"]) for r in rr),
                "digest_nondeterminism_count":sum(1-int(r["digest_deterministic"]) for r in rr),
                "mutated_world_certificate_acceptance_count":sum(int(r["mutated_world_certificate_accepted"]) for r in rr),
                "causal_truth_field_count":sum(1-int(r["no_causal_truth_field"]) for r in rr),
            }
            stale=[int(r["stale_certificate_accepted"]) for r in rr if r["stale_certificate_accepted"]!=""]
            dropped=[int(r["dropped_world_certificate_accepted"]) for r in rr if r["dropped_world_certificate_accepted"]!=""]
            fs["stale_certificate_acceptance_rate"]=None if not stale else sum(stale)/len(stale)
            fs["dropped_world_certificate_acceptance_rate"]=None if not dropped else sum(dropped)/len(dropped)
            fams[family]=fs
            if pass_count!=N: errors.append(f"{cohort}:{family}: pass {pass_count}/{N}")
            if false_robust: errors.append(f"{cohort}:{family}: false robust {false_robust}")
        cohorts[cohort]={"seed_base":base,"families":fams}
    scientific_pass=not errors
    return {
        "experiment_id":"COG-PLAN-01","preconfirmatory_preregistration_commit":PREREG_COMMIT,
        "verdict":"PROOF_CARRYING_COUNTERFACTUAL_PLANNER_QUALIFIED_SYNTHETIC_NARROWED" if scientific_pass else "PROOF_CARRYING_COUNTERFACTUAL_PLANNER_NOT_QUALIFIED",
        "scientific_pass":scientific_pass,"authority":"PLANNING_SAFETY_PRIMITIVE_ONLY" if scientific_pass else "NO_PROMOTION",
        "cases_per_family_per_cohort":N,"robust_margin":MARGIN,"cohorts":cohorts,"errors":errors,
        "planner_policy":{
            "world_averaging_can_create_robust_action":False,
            "all_admitted_worlds_required":True,
            "surviving_countermodel_must_be_represented":True,
            "assumption_conditional_can_be_unconditional_action":False,
            "stale_memory_certificate_valid":False,
            "information_spend_requires_certified_converse_budget":True,
        },
        "non_promotion_boundary":{
            "semantic_causality":False,"real_world_planning_utility":False,"replay_control":False,
            "active_control":False,"autonomous_self_modification":False,"architecture_promotion":False,
        },
        "wall_seconds":time.perf_counter()-started,"rows":rows,
    }


def main() -> int:
    ART.mkdir(parents=True,exist_ok=True); RESULT.mkdir(parents=True,exist_ok=True)
    payload=run(); rows=payload.pop("rows"); data=(json.dumps(payload,indent=2,sort_keys=True)+"\n").encode()
    (ART/"verdict.json").write_bytes(data); (RESULT/"verdict.json").write_bytes(data)
    fields=("cohort","family","case","pass","state","selected_action","certificate_valid_before","digest_deterministic","mutated_world_certificate_accepted","stale_certificate_accepted","dropped_world_certificate_accepted","no_causal_truth_field","information_state","necessary_information_cost")
    with (ART/"planning_matrix.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    sums=[]
    for name in ("verdict.json","planning_matrix.csv"):
        p=ART/name; sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {name}")
    (ART/"SHA256SUMS").write_text("\n".join(sums)+"\n")
    print(json.dumps(payload,indent=2,sort_keys=True))
    return 0 if payload["scientific_pass"] else 2

if __name__=="__main__": raise SystemExit(main())
