from __future__ import annotations

import random

from cwc.memory.causal_debt import CausalDebtLedger, ReplayEvidence
from cwc.replay.scheduler import choose_candidate, choose_least_covered_context


def test_causal_debt_scheduler_uses_ledger_debt() -> None:
    ledger = CausalDebtLedger()
    ledger.register("A", eligibility=0.9, observational_credit=0.9)
    ledger.register("B", eligibility=0.1, observational_credit=0.1)
    chosen = choose_candidate(
        "causal_debt_cf",
        ledger=ledger,
        observational_strength={"A": 0.9, "B": 0.1},
        replay_counts={"A": 0, "B": 0},
        rng=random.Random(1),
    )
    assert chosen == "A"


def test_least_covered_context_is_deterministic() -> None:
    ledger = CausalDebtLedger()
    ledger.register("A", eligibility=0.8, observational_credit=0.8)
    ledger.append(ReplayEvidence("A", "same", 1.0))
    ledger.append(ReplayEvidence("A", "same", 1.0))
    ledger.append(ReplayEvidence("A", "decorrelated", 1.0))
    chosen = choose_least_covered_context(
        "A",
        contexts=("same", "decorrelated", "reversed"),
        ledger=ledger,
        rng=random.Random(1),
        randomize=False,
    )
    assert chosen == "reversed"
