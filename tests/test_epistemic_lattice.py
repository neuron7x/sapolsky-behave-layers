from __future__ import annotations

import hashlib

import pytest

from cwc.epistemics.lattice import (
    CapabilityBindingError,
    EpistemicCapability,
    EpistemicMachine,
    EpistemicRecord,
    EpistemicState,
    EvidenceClassError,
    EvidenceKind,
    EvidenceRef,
    EvidenceSource,
    IllegalTransition,
    positive_state_dominates,
)


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def ev(label: str, kind: EvidenceKind, source: EvidenceSource, scope=("CTX",)) -> EvidenceRef:
    return EvidenceRef(
        ref=f"mem://{label}",
        sha256=_hash(label),
        kind=kind,
        source=source,
        context_scope=scope,
        provenance="unit-test",
    )


def chain(machine: EpistemicMachine | None = None):
    m = machine or EpistemicMachine()
    o = m.observe(
        claim_id="C1",
        context_scope=("CTX",),
        evidence=[ev("fact", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL)],
    )
    pc = m.issue_predictive_capability(
        o, evidence=[ev("pred", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION)]
    )
    p = m.transition(o, pc)
    ac = m.issue_assumption_capability(
        p,
        assumption_ids=("A1", "A2"),
        evidence=[ev("assump", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT)],
    )
    a = m.transition(p, ac)
    return m, o, p, a


def test_direct_record_and_capability_construction_blocked():
    with pytest.raises(TypeError):
        EpistemicRecord()
    with pytest.raises(TypeError):
        EpistemicCapability()


def test_legal_chain_requires_exact_capabilities():
    m, o, p, a = chain()
    ic = m.issue_intervention_capability(
        a,
        operator_id="do(span=SPACE)",
        evidence=[ev("do", EvidenceKind.DIRECT_INTERVENTION, EvidenceSource.DIRECT_SYSTEM_REEXECUTION)],
    )
    i = m.transition(a, ic)
    assert [o.state, p.state, a.state, i.state] == [
        EpistemicState.OBSERVED,
        EpistemicState.PREDICTIVE,
        EpistemicState.ASSUMPTION_CONDITIONAL,
        EpistemicState.INTERVENTION_SUPPORTED,
    ]
    assert i.operator_id == "do(span=SPACE)"
    assert i.assumption_ids == ("A1", "A2")
    assert i.unconditional_causal_authority is False


def test_surrogate_or_replay_cannot_mint_direct_intervention():
    m, _, _, a = chain()
    for source in (EvidenceSource.SURROGATE_MODEL, EvidenceSource.REPLAY_GENERATED):
        with pytest.raises(EvidenceClassError):
            m.issue_intervention_capability(
                a,
                operator_id="do(X)",
                evidence=[ev(source.value, EvidenceKind.DIRECT_INTERVENTION, source)],
            )


def test_assumption_evidence_cannot_substitute_for_intervention():
    m, _, _, a = chain()
    with pytest.raises(EvidenceClassError):
        m.issue_intervention_capability(
            a,
            operator_id="do(X)",
            evidence=[ev("assump2", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT)],
        )


def test_terminal_states_are_absorbing():
    m, _, p, _ = chain()
    cap = m.issue_terminal_capability(
        p,
        target_state=EpistemicState.UNIDENTIFIED,
        evidence=[ev("counter", EvidenceKind.COUNTERMODEL, EvidenceSource.COUNTERMODEL_SEARCH)],
        reason="equivalent countermodel",
    )
    u = m.transition(p, cap)
    assert u.state is EpistemicState.UNIDENTIFIED
    with pytest.raises(IllegalTransition):
        m.issue_assumption_capability(
            u,
            assumption_ids=("A1",),
            evidence=[ev("a", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT)],
        )
    with pytest.raises(IllegalTransition):
        m.transition(u, cap)


def test_falsified_cannot_resurrect():
    m, _, p, _ = chain()
    fc = m.issue_terminal_capability(
        p,
        target_state=EpistemicState.FALSIFIED,
        evidence=[ev("fals", EvidenceKind.FALSIFICATION, EvidenceSource.DIAGNOSTIC)],
        reason="predictive contradiction",
    )
    f = m.transition(p, fc)
    assert f.state is EpistemicState.FALSIFIED
    with pytest.raises(IllegalTransition):
        m.issue_assumption_capability(
            f,
            assumption_ids=("A1",),
            evidence=[ev("a3", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT)],
        )


def test_capability_is_bound_to_exact_parent_and_claim():
    m = EpistemicMachine()
    fact = ev("fact-shared", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL)
    o1 = m.observe(claim_id="C1", context_scope=("CTX",), evidence=[fact])
    o2 = m.observe(claim_id="C2", context_scope=("CTX",), evidence=[fact])
    cap = m.issue_predictive_capability(
        o1, evidence=[ev("pred-bind", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION)]
    )
    with pytest.raises(CapabilityBindingError):
        m.transition(o2, cap)
    p1 = m.transition(o1, cap)
    with pytest.raises(CapabilityBindingError):
        m.transition(p1, cap)


def test_scope_escalation_is_blocked():
    m = EpistemicMachine()
    o = m.observe(
        claim_id="C1",
        context_scope=("CTX",),
        evidence=[ev("fact-scope", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL)],
    )
    with pytest.raises(CapabilityBindingError):
        m.issue_predictive_capability(
            o,
            context_scope=("CTX", "GLOBAL"),
            evidence=[ev("pred-scope", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, scope=("CTX", "GLOBAL"))],
        )


def test_bad_sha_is_rejected():
    with pytest.raises(ValueError):
        EvidenceRef(
            ref="bad",
            sha256="0" * 63,
            kind=EvidenceKind.FACTUAL_OBSERVATION,
            source=EvidenceSource.FACTUAL_CHANNEL,
            context_scope=("CTX",),
            provenance="test",
        )


def test_record_digest_is_deterministic_and_payload_sensitive():
    m = EpistemicMachine()
    e1 = ev("f1", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL)
    e2 = ev("f2", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL)
    a = m.observe(claim_id="C", context_scope=("CTX",), evidence=[e1, e2])
    b = m.observe(claim_id="C", context_scope=("CTX",), evidence=[e2, e1])
    c = m.observe(claim_id="C2", context_scope=("CTX",), evidence=[e1, e2])
    assert a.record_digest == b.record_digest
    assert a.record_digest != c.record_digest


def test_positive_dominance_excludes_terminal_dispositions():
    assert positive_state_dominates(EpistemicState.INTERVENTION_SUPPORTED, EpistemicState.PREDICTIVE)
    assert not positive_state_dominates(EpistemicState.OBSERVED, EpistemicState.PREDICTIVE)
    with pytest.raises(ValueError):
        positive_state_dominates(EpistemicState.FALSIFIED, EpistemicState.OBSERVED)
