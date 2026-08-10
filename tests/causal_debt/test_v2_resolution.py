from __future__ import annotations

from cwc.memory.causal_debt import CausalDebtLedger, ReplayEvidence


def test_resolution_aware_debt_discharges_zero_effect_candidate() -> None:
    ledger = CausalDebtLedger()
    ledger.register("S", eligibility=0.9, observational_credit=0.9)
    initial = ledger.resolution_aware_debt("S")
    for context in ("same", "decorrelated", "reversed", "same"):
        ledger.append(ReplayEvidence("S", context, 0.0))
    later = ledger.resolution_aware_debt("S")
    assert later < initial / 2.0
    assert not ledger.consolidation("S").consolidated


def test_resolution_aware_debt_preserves_positive_candidate_priority() -> None:
    ledger = CausalDebtLedger()
    ledger.register("C", eligibility=0.8, observational_credit=0.8)
    ledger.register("S", eligibility=0.9, observational_credit=0.9)
    ledger.append(ReplayEvidence("S", "same", 0.0))
    ledger.append(ReplayEvidence("C", "same", 1.0))
    assert ledger.resolution_aware_debt("C") > ledger.resolution_aware_debt("S")


def test_v1_debt_method_is_retained_for_reproducibility() -> None:
    ledger = CausalDebtLedger()
    ledger.register("S", eligibility=0.9, observational_credit=0.9)
    for context in ("same", "decorrelated", "reversed", "same"):
        ledger.append(ReplayEvidence("S", context, 0.0))
    assert ledger.debt("S") > ledger.resolution_aware_debt("S")
