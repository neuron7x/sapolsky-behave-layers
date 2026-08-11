from __future__ import annotations

import hashlib
import pytest

from cwc.epistemics.information_acquisition import InformationAction
from cwc.epistemics.lattice import EpistemicMachine, EvidenceKind, EvidenceRef, EvidenceSource
from cwc.memory.epistemic_store import EpistemicMemoryLedger
from cwc.planning.proof_carrying import PlanCertificate, PlanState, WorldBranch, plan_counterfactual, verify_plan_certificate


def ev(label, kind, source, scope=("CTX",)):
    return EvidenceRef(ref="plan://"+label,sha256=hashlib.sha256(label.encode()).hexdigest(),kind=kind,source=source,context_scope=scope,provenance="plan-test")


def memory(state="predictive", counters=()):
    scope=("CTX",); m=EpistemicMachine()
    o=m.observe(claim_id="C",context_scope=scope,evidence=[ev("o",EvidenceKind.FACTUAL_OBSERVATION,EvidenceSource.FACTUAL_CHANNEL)])
    p=m.transition(o,m.issue_predictive_capability(o,evidence=[ev("p",EvidenceKind.PREDICTIVE_VALIDATION,EvidenceSource.HELD_OUT_PREDICTION)]))
    rec=p
    if state in {"assumption","intervention"}:
        a=m.transition(p,m.issue_assumption_capability(p,assumption_ids=("A1",),evidence=[ev("a",EvidenceKind.IDENTIFYING_ASSUMPTION,EvidenceSource.ASSUMPTION_CONTRACT)])); rec=a
        if state=="intervention":
            rec=m.transition(a,m.issue_intervention_capability(a,operator_id="do(X)",evidence=[ev("i",EvidenceKind.DIRECT_INTERVENTION,EvidenceSource.DIRECT_SYSTEM_REEXECUTION)]))
    l=EpistemicMemoryLedger(); mr=l.consolidate(memory_id="m",epistemic_record=rec,countermodel_ids=counters)
    return l,mr


def worlds_same():
    return [WorldBranch("BASE",{"A":1.0,"B":0.5},"test"),WorldBranch("CM",{"A":0.9,"B":0.6},"test")]


def worlds_reverse():
    return [WorldBranch("BASE",{"A":1.0,"B":0.0},"test"),WorldBranch("CM",{"A":0.0,"B":1.0},"test")]


def test_direct_certificate_construction_blocked():
    with pytest.raises(TypeError): PlanCertificate()


def test_robust_action_requires_all_worlds():
    l,m=memory()
    r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=[m],worlds=worlds_same())
    assert r.state is PlanState.ROBUST_ACTION and r.selected_action=="A"
    assert verify_plan_certificate(r.certificate,ledger=l,context_scope=("CTX",),worlds=worlds_same())


def test_world_reversal_never_averages_to_action():
    l,m=memory()
    r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=[m],worlds=worlds_reverse())
    assert r.state is PlanState.ABSTAIN_WORLD_DISAGREEMENT and r.selected_action is None


def test_countermodel_quarantine_can_support_decision_robustness_only_if_world_is_represented():
    l,m=memory("intervention",counters=("CM",))
    r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=[m],worlds=worlds_same())
    assert r.state is PlanState.ROBUST_ACTION
    bad=[WorldBranch("BASE",{"A":1.0,"B":0.5},"test"),WorldBranch("OTHER",{"A":0.9,"B":0.6},"test")]
    r2=plan_counterfactual(ledger=l,plan_id="q",context_scope=("CTX",),required_memories=[m],worlds=bad)
    assert r2.state is PlanState.BLOCKED_MEMORY_AUTHORITY


def test_assumption_memory_is_conditional_not_unconditional():
    l,m=memory("assumption")
    r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=[m],worlds=worlds_same())
    assert r.state is PlanState.ASSUMPTION_CONDITIONAL_PLAN and r.selected_action=="A"


def test_information_acquisition_only_when_converse_budget_not_ruled_out():
    l,m=memory(); w=worlds_reverse()
    info=InformationAction("probe",1.0,{"BASE":0.2,"CM":0.2},"CERTIFIED_LOWER_BOUND")
    go=plan_counterfactual(ledger=l,plan_id="go",context_scope=("CTX",),required_memories=[m],worlds=w,information_actions=[info],available_information_budget=30)
    stop=plan_counterfactual(ledger=l,plan_id="stop",context_scope=("CTX",),required_memories=[m],worlds=w,information_actions=[info],available_information_budget=10)
    assert go.state is PlanState.ACQUIRE_INFORMATION
    assert stop.state is PlanState.ABSTAIN_WORLD_DISAGREEMENT


def test_zero_information_channel_abstains():
    l,m=memory(); w=worlds_reverse()
    info=InformationAction("probe",1.0,{"BASE":0.2,"CM":0.0},"CERTIFIED_LOWER_BOUND")
    r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=[m],worlds=w,information_actions=[info],available_information_budget=100)
    assert r.state is PlanState.ABSTAIN_WORLD_DISAGREEMENT


def test_margin_failure_abstains():
    l,m=memory(); w=[WorldBranch("BASE",{"A":1,"B":0.97},"test"),WorldBranch("CM",{"A":1,"B":0.8},"test")]
    r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=[m],worlds=w)
    assert r.state is PlanState.ABSTAIN_NO_UNIQUE_ROBUST_ACTION


def test_memory_retraction_invalidates_certificate():
    l,m=memory(); w=worlds_same(); r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=[m],worlds=w)
    assert verify_plan_certificate(r.certificate,ledger=l,context_scope=("CTX",),worlds=w)
    l.retract("m",reason="falsified")
    assert not verify_plan_certificate(r.certificate,ledger=l,context_scope=("CTX",),worlds=w)


def test_world_drop_invalidates_certificate():
    l,m=memory(); w=worlds_same(); r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=[m],worlds=w)
    assert not verify_plan_certificate(r.certificate,ledger=l,context_scope=("CTX",),worlds=w[:1])


def test_legacy_memory_blocks():
    l,_=memory(); r=plan_counterfactual(ledger=l,plan_id="p",context_scope=("CTX",),required_memories=["INTERVENTION_SUPPORTED"],worlds=worlds_same())
    assert r.state is PlanState.BLOCKED_MEMORY_AUTHORITY
