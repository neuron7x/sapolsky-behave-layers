from __future__ import annotations

from cwc.memory.causal_debt import CausalDebtLedger, ReplayEvidence


def _ledger() -> CausalDebtLedger:
    ledger = CausalDebtLedger(min_replays=3, min_contexts=2, min_abs_credit=0.10, z_value=1.0)
    ledger.register("C", eligibility=0.8, observational_credit=0.8)
    ledger.register("S", eligibility=0.7, observational_credit=0.7)
    return ledger


def test_observational_credit_never_consolidates_without_interventions() -> None:
    ledger = _ledger()
    decision = ledger.consolidation("C")
    assert not decision.consolidated
    assert decision.reason == "insufficient_replays"
    assert ledger.causal_credit("C") == 0.0


def test_single_context_is_fail_closed() -> None:
    ledger = _ledger()
    for _ in range(8):
        ledger.append(ReplayEvidence("C", "same", 1.0))
    decision = ledger.consolidation("C")
    assert not decision.consolidated
    assert decision.reason == "insufficient_contexts"
    assert ledger.invariance("C") == 0.0


def test_cross_context_coherent_effect_can_consolidate() -> None:
    ledger = _ledger()
    for context in ("same", "decorrelated", "reversed"):
        for _ in range(4):
            ledger.append(ReplayEvidence("C", context, 1.0))
    decision = ledger.consolidation("C")
    assert decision.consolidated
    assert decision.credit > 0.5
    assert ledger.invariance("C") == 1.0


def test_zero_counterfactual_effect_fails_precision_gate() -> None:
    ledger = _ledger()
    for context in ("same", "reversed"):
        for _ in range(10):
            ledger.append(ReplayEvidence("S", context, 0.0))
    decision = ledger.consolidation("S")
    assert not decision.consolidated
    assert decision.reason == "insufficient_causal_precision"
    assert ledger.lower_confidence("S") == 0.0


def test_context_sign_flip_is_rejected() -> None:
    ledger = _ledger()
    for _ in range(8):
        ledger.append(ReplayEvidence("C", "same", 1.0))
        ledger.append(ReplayEvidence("C", "reversed", -1.0))
    decision = ledger.consolidation("C")
    assert not decision.consolidated
    assert ledger.invariance("C") == 0.0
