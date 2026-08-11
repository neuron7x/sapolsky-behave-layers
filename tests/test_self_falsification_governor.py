from __future__ import annotations

import hashlib

import pytest

from cwc.epistemics.lattice import (
    EpistemicMachine,
    EvidenceKind,
    EvidenceRef,
    EvidenceSource,
)
from cwc.epistemics.self_falsification import (
    FalsificationAttack,
    FalsificationBindingError,
    FalsificationOutcome,
    SelfFalsificationDecision,
    SelfFalsificationState,
    apply_self_falsification_outcome,
    select_self_falsification_attack,
    verify_self_falsification_decision,
)
from cwc.memory.epistemic_store import EpistemicMemoryLedger, MemoryStatus
from cwc.planning.proof_carrying import WorldBranch, plan_counterfactual


SCOPE = ("CTX",)


def _ev(label: str, kind: EvidenceKind, source: EvidenceSource) -> EvidenceRef:
    return EvidenceRef(
        ref=f"self://{label}",
        sha256=hashlib.sha256(label.encode()).hexdigest(),
        kind=kind,
        source=source,
        context_scope=SCOPE,
        provenance="self-falsification-test",
    )


def _intervention_record(assumptions=("A1",)):
    m = EpistemicMachine()
    o = m.observe(
        claim_id="CLAIM",
        context_scope=SCOPE,
        evidence=[_ev("obs", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL)],
    )
    p = m.transition(
        o,
        m.issue_predictive_capability(
            o,
            evidence=[_ev("pred", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION)],
        ),
    )
    a = m.transition(
        p,
        m.issue_assumption_capability(
            p,
            assumption_ids=assumptions,
            evidence=[_ev("assumption", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT)],
        ),
    )
    return m.transition(
        a,
        m.issue_intervention_capability(
            a,
            operator_id="do(X)",
            evidence=[_ev("intervention", EvidenceKind.DIRECT_INTERVENTION, EvidenceSource.DIRECT_SYSTEM_REEXECUTION)],
        ),
    )


def _ledger(with_outsider: bool = False):
    rec = _intervention_record()
    ledger = EpistemicMemoryLedger()
    parent = ledger.consolidate(memory_id="parent", epistemic_record=rec)
    child = ledger.consolidate(memory_id="child", epistemic_record=rec, dependency_ids=("parent",))
    outsider = None
    if with_outsider:
        outsider = ledger.consolidate(memory_id="outsider", epistemic_record=rec)
    return ledger, parent, child, outsider


def _worlds_reverse():
    return [
        WorldBranch("BASE", {"A": 1.0, "B": 0.0}, "self-test"),
        WorldBranch("CM", {"A": 0.0, "B": 1.0}, "self-test"),
    ]


def _worlds_same():
    return [
        WorldBranch("BASE", {"A": 1.0, "B": 0.0}, "self-test"),
        WorldBranch("CM", {"A": 0.9, "B": 0.1}, "self-test"),
    ]


def _worlds_three():
    return [
        WorldBranch("BASE", {"A": 1.0, "B": 0.0}, "self-test"),
        WorldBranch("SAME", {"A": 0.9, "B": 0.1}, "self-test"),
        WorldBranch("CROSS", {"A": 0.0, "B": 1.0}, "self-test"),
    ]


def _plan(ledger, child, worlds):
    return plan_counterfactual(
        ledger=ledger,
        plan_id="SELF-PLAN",
        context_scope=SCOPE,
        required_memories=[child],
        worlds=worlds,
    ).certificate


def _attack(
    attack_id: str,
    rates: dict[str, float],
    *,
    cost: float = 1.0,
    worlds=("CM",),
    memories=("parent",),
    assumptions=(),
    certificate="CERTIFIED_LOWER_BOUND",
    max_units=None,
):
    return FalsificationAttack(
        attack_id=attack_id,
        unit_cost=cost,
        information_rate_lower_bounds=rates,
        rate_certificate=certificate,
        target_world_ids=tuple(worlds),
        target_memory_ids=tuple(memories),
        target_assumption_ids=tuple(assumptions),
        max_units=max_units,
    )


def test_direct_decision_construction_is_blocked():
    with pytest.raises(TypeError):
        SelfFalsificationDecision()


def test_s0_robust_decision_preserves_model_ambiguity_without_spend():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_same()
    cert = _plan(ledger, child, worlds)
    attack = _attack("tempting", {"CM": 10.0})
    decision = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[attack], available_budget=100.0,
    )
    assert decision.state is SelfFalsificationState.NO_DECISION_RELEVANT_ATTACK
    assert decision.attack_id is None


def test_s1_selects_lowest_necessary_cost_certified_attack():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    slow = _attack("slow", {"CM": 0.4}, cost=2.0)
    fast = _attack("fast", {"CM": 0.5}, cost=1.0)
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[slow, fast], available_budget=100.0,
    )
    assert d.state is SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION
    assert d.attack_id == "fast"


def test_s2_same_decision_information_does_not_control_selection():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_three(); cert = _plan(ledger, child, worlds)
    nuisance = _attack(
        "nuisance", {"SAME": 20.0, "CROSS": 0.1}, worlds=("CROSS",),
    )
    decisive = _attack(
        "decisive", {"SAME": 0.01, "CROSS": 0.6}, worlds=("CROSS",),
    )
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[nuisance, decisive], available_budget=100.0,
    )
    assert d.attack_id == "decisive"
    assert d.ignored_same_decision_world_ids == ("SAME",)
    assert d.cross_decision_world_ids == ("CROSS",)


def test_s3_zero_cross_decision_information_vetoes_spend():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    zero = _attack("zero", {"CM": 0.0})
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[zero], available_budget=100.0,
    )
    assert d.state is SelfFalsificationState.NO_DECISION_IDENTIFYING_ATTACK


def test_s4_stale_plan_is_rejected():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    ledger.retract("parent", reason="pre-selection falsifier")
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[_attack("a", {"CM": 1.0})], available_budget=100.0,
    )
    assert d.state is SelfFalsificationState.REJECT_INVALID_PLAN_CERTIFICATE


def test_s5_irrelevant_memory_target_is_ineligible():
    ledger, _, child, _ = _ledger(with_outsider=True)
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    irrelevant = _attack("irrelevant", {"CM": 100.0}, memories=("outsider",))
    bound = _attack("bound", {"CM": 0.5}, memories=("parent",))
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[irrelevant, bound], available_budget=100.0,
    )
    assert d.attack_id == "bound"


def test_s6_parent_target_is_load_bearing_and_retracts_transitively():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[_attack("parent-test", {"CM": 1.0})], available_budget=100.0,
    )
    assert d.attack_id == "parent-test"
    assert verify_self_falsification_decision(d, ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds)
    update = apply_self_falsification_outcome(
        decision=d, ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        outcome=FalsificationOutcome.FALSIFIED_MEMORY, target_id="parent", reason="negative control",
    )
    assert set(update.changed_memory_ids) == {"parent", "child"}
    assert not update.authority_promoted
    assert ledger.record("parent").status is MemoryStatus.RETRACTED
    assert ledger.record("child").status is MemoryStatus.RETRACTED


def test_s7_uncertified_nominally_better_attack_cannot_authorize_spend():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    fake = _attack("fake", {"CM": 1000.0}, certificate="POINT_ESTIMATE_ONLY")
    certified = _attack("certified", {"CM": 0.5})
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[fake, certified], available_budget=100.0,
    )
    assert d.attack_id == "certified"


def test_s8_capacity_and_budget_vetoes_are_distinct():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    cap = _attack("cap", {"CM": 0.5}, max_units=1)
    dc = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[cap], available_budget=100.0,
    )
    assert dc.state is SelfFalsificationState.ATTACK_CAPACITY_BELOW_NECESSARY_BOUND
    budget = _attack("budget", {"CM": 0.5})
    db = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[budget], available_budget=0.01,
    )
    assert db.state is SelfFalsificationState.INSUFFICIENT_ATTACK_BUDGET


def test_s9_order_invariance_includes_digest():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    a = _attack("a", {"CM": 0.5})
    b = _attack("b", {"CM": 0.2})
    d1 = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[a, b], available_budget=100.0,
    )
    d2 = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=list(reversed(worlds)),
        candidate_world_id="BASE", attacks=[b, a], available_budget=100.0,
    )
    assert d1.state == d2.state
    assert d1.attack_id == d2.attack_id
    assert d1.necessary_cost_lower_bound == d2.necessary_cost_lower_bound
    assert d1.decision_digest == d2.decision_digest


def test_s10_survival_never_promotes_and_assumption_invalidation_is_monotone():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    attack = _attack("assumption-test", {"CM": 1.0}, memories=(), assumptions=("A1",))
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[attack], available_budget=100.0,
    )
    before = tuple((mid, ledger.record(mid).memory_digest) for mid in ledger.memory_ids)
    survived = apply_self_falsification_outcome(
        decision=d, ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        outcome=FalsificationOutcome.SURVIVED,
    )
    after = tuple((mid, ledger.record(mid).memory_digest) for mid in ledger.memory_ids)
    assert before == after
    assert survived.authority_promoted is False

    invalidated = apply_self_falsification_outcome(
        decision=d, ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        outcome=FalsificationOutcome.INVALIDATED_ASSUMPTION, target_id="A1", reason="assumption falsifier",
    )
    assert invalidated.authority_promoted is False
    assert set(invalidated.changed_memory_ids) == {"parent", "child"}
    assert invalidated.invalidated_assumption_ids == ("A1",)


def test_s11_stale_or_unbound_outcome_fails_closed_without_extra_mutation():
    ledger, _, child, _ = _ledger()
    worlds = _worlds_reverse(); cert = _plan(ledger, child, worlds)
    d = select_self_falsification_attack(
        ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[_attack("a", {"CM": 1.0})], available_budget=100.0,
    )
    ledger.retract("parent", reason="external change")
    events_before = len(ledger.events)
    with pytest.raises(FalsificationBindingError):
        apply_self_falsification_outcome(
            decision=d, ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
            outcome=FalsificationOutcome.FALSIFIED_MEMORY, target_id="parent",
        )
    assert len(ledger.events) == events_before

    ledger2, _, child2, _ = _ledger()
    cert2 = _plan(ledger2, child2, worlds)
    d2 = select_self_falsification_attack(
        ledger=ledger2, plan_certificate=cert2, context_scope=SCOPE, worlds=worlds,
        candidate_world_id="BASE", attacks=[_attack("a", {"CM": 1.0})], available_budget=100.0,
    )
    events_before = len(ledger2.events)
    with pytest.raises(FalsificationBindingError):
        apply_self_falsification_outcome(
            decision=d2, ledger=ledger2, plan_certificate=cert2, context_scope=SCOPE, worlds=worlds,
            outcome=FalsificationOutcome.FALSIFIED_MEMORY, target_id="child",
        )
    assert len(ledger2.events) == events_before
