from __future__ import annotations

import hashlib

import pytest

from cwc.epistemics.lattice import EpistemicMachine, EpistemicState, EvidenceKind, EvidenceRef, EvidenceSource
from cwc.memory.epistemic_store import EpistemicMemoryLedger, MemoryRecord, MemoryStatus


def ev(label: str, kind: EvidenceKind, source: EvidenceSource, scope=("CTX",)) -> EvidenceRef:
    return EvidenceRef(
        ref=f"mem://{label}",
        sha256=hashlib.sha256(label.encode()).hexdigest(),
        kind=kind,
        source=source,
        context_scope=scope,
        provenance="memory-test",
    )


def records(claim="C", assumptions=("A1",), scope=("CTX",)):
    m=EpistemicMachine()
    o=m.observe(claim_id=claim,context_scope=scope,evidence=[ev(claim+"f",EvidenceKind.FACTUAL_OBSERVATION,EvidenceSource.FACTUAL_CHANNEL,scope)])
    p=m.transition(o,m.issue_predictive_capability(o,evidence=[ev(claim+"p",EvidenceKind.PREDICTIVE_VALIDATION,EvidenceSource.HELD_OUT_PREDICTION,scope)]))
    a=m.transition(p,m.issue_assumption_capability(p,assumption_ids=assumptions,evidence=[ev(claim+"a",EvidenceKind.IDENTIFYING_ASSUMPTION,EvidenceSource.ASSUMPTION_CONTRACT,scope)]))
    i=m.transition(a,m.issue_intervention_capability(a,operator_id="do(X)",evidence=[ev(claim+"i",EvidenceKind.DIRECT_INTERVENTION,EvidenceSource.DIRECT_SYSTEM_REEXECUTION,scope)]))
    return m,o,p,a,i


def test_direct_memory_record_construction_blocked():
    with pytest.raises(TypeError):
        MemoryRecord()


def test_observed_and_predictive_store_active_but_noncausal():
    _,o,p,_,_=records()
    l=EpistemicMemoryLedger()
    ro=l.consolidate(memory_id="o",epistemic_record=o)
    rp=l.consolidate(memory_id="p",epistemic_record=p,dependency_ids=("o",))
    assert ro.status is MemoryStatus.ACTIVE and not ro.causal_consolidated
    assert rp.status is MemoryStatus.ACTIVE and not rp.causal_consolidated


def test_assumption_conditional_never_causal_consolidates_even_without_countermodel():
    _,_,_,a,_=records()
    l=EpistemicMemoryLedger()
    r=l.consolidate(memory_id="a",epistemic_record=a)
    assert r.status is MemoryStatus.QUARANTINED
    assert not r.causal_consolidated


def test_intervention_supported_requires_empty_countermodel_set():
    _,_,_,_,i=records()
    l=EpistemicMemoryLedger()
    clean=l.consolidate(memory_id="clean",epistemic_record=i)
    blocked=l.consolidate(memory_id="blocked",epistemic_record=i,countermodel_ids=("M_ALT",))
    assert clean.status is MemoryStatus.ACTIVE and clean.causal_consolidated
    assert blocked.status is MemoryStatus.QUARANTINED and not blocked.causal_consolidated


def test_terminal_state_cannot_be_active_memory():
    m,_,p,_,_=records()
    cap=m.issue_terminal_capability(p,target_state=EpistemicState.UNIDENTIFIED,evidence=[ev("cm",EvidenceKind.COUNTERMODEL,EvidenceSource.COUNTERMODEL_SEARCH)],reason="equiv")
    u=m.transition(p,cap)
    l=EpistemicMemoryLedger()
    r=l.consolidate(memory_id="u",epistemic_record=u)
    assert r.status is MemoryStatus.RETRACTED
    assert not r.causal_consolidated


def test_parent_retraction_propagates_transitively():
    _,_,_,_,i=records()
    l=EpistemicMemoryLedger()
    l.consolidate(memory_id="p",epistemic_record=i)
    l.consolidate(memory_id="c",epistemic_record=i,dependency_ids=("p",))
    l.consolidate(memory_id="g",epistemic_record=i,dependency_ids=("c",))
    changed=set(l.retract("p",reason="parent falsified"))
    assert changed=={"p","c","g"}
    assert all(l.record(mid).status is MemoryStatus.RETRACTED for mid in changed)
    assert all(not l.record(mid).causal_consolidated for mid in changed)
    assert l.event_chain_valid()


def test_assumption_invalidation_retracts_dependents():
    _,_,_,_,i=records(assumptions=("A_SHARED",))
    l=EpistemicMemoryLedger()
    l.consolidate(memory_id="r",epistemic_record=i)
    l.consolidate(memory_id="d1",epistemic_record=i,dependency_ids=("r",))
    l.consolidate(memory_id="d2",epistemic_record=i,dependency_ids=("r",))
    changed=set(l.invalidate_assumption("A_SHARED",reason="negative control"))
    assert changed=={"r","d1","d2"}
    l.assert_invariants()


def test_binding_verification_rejects_different_epistemic_record():
    _,_,p,_,i=records()
    l=EpistemicMemoryLedger()
    l.consolidate(memory_id="m",epistemic_record=i)
    assert l.verify_binding("m",i)
    assert not l.verify_binding("m",p)


def test_legacy_string_injection_rejected():
    l=EpistemicMemoryLedger()
    with pytest.raises(TypeError):
        l.consolidate(memory_id="x",epistemic_record="INTERVENTION_SUPPORTED")  # type: ignore[arg-type]


def test_stronger_record_requires_new_memory_and_does_not_mutate_old():
    _,_,p,_,i=records()
    l=EpistemicMemoryLedger()
    old=l.consolidate(memory_id="old",epistemic_record=p)
    new=l.consolidate(memory_id="new",epistemic_record=i,revision_of="old")
    assert l.record("old").memory_digest==old.memory_digest
    assert not l.record("old").causal_consolidated
    assert new.causal_consolidated
    assert new.revision_of=="old"


def test_event_chain_detects_tampering_semantically():
    _,o,_,_,_=records()
    l=EpistemicMemoryLedger(); l.consolidate(memory_id="o",epistemic_record=o)
    assert l.event_chain_valid()
    e=l._events[0]  # test-only mutation attack against internal storage
    from cwc.memory.epistemic_store import MemoryEvent
    l._events[0]=MemoryEvent(e.sequence,e.event_type,e.memory_id,e.previous_event_hash,"0"*64,e.reason,e.event_hash)
    assert not l.event_chain_valid()
