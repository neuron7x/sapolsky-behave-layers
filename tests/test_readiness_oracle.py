from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from cwc.assurance.readiness import ReadinessFacts, assess_readiness, collect_facts

ROOT = Path(__file__).resolve().parents[1]


def _facts() -> ReadinessFacts:
    return ReadinessFacts(
        architecture_contract=True,
        inference_integrity=True,
        hermetic_reproduction=True,
        supply_chain_inventory=True,
        adversarial_gate=True,
        claim_artifacts_complete=True,
        negative_results_preserved=True,
        documentation_traceable=True,
        supported_claims=3,
        independently_replicated_supported_claims=0,
        real_workload_supported_claims=0,
        restricted_data_present=True,
    )


def test_perfect_technical_score_cannot_override_blocking_facts() -> None:
    result = assess_readiness(_facts())
    assert result["technical_score"] == 100
    assert result["status"] == "LOCALLY_VERIFIED_RESEARCH_ENGINEERING"
    assert len(result["blocking_facts"]) == 3


def test_external_status_requires_every_blocker_closed() -> None:
    facts = replace(
        _facts(),
        independently_replicated_supported_claims=3,
        real_workload_supported_claims=1,
        restricted_data_present=False,
    )
    result = assess_readiness(facts)
    assert result["status"] == "EXTERNALLY_VALIDATED_RESEARCH_SYSTEM"
    assert result["blocking_facts"] == []


def test_missing_core_contract_forces_not_ready_below_threshold() -> None:
    facts = replace(
        _facts(),
        architecture_contract=False,
        inference_integrity=False,
        hermetic_reproduction=False,
    )
    result = assess_readiness(facts)
    assert result["technical_score"] < 70
    assert result["status"] == "NOT_READY"


@pytest.mark.parametrize(
    "field",
    [
        "architecture_contract",
        "inference_integrity",
        "hermetic_reproduction",
        "supply_chain_inventory",
        "adversarial_gate",
        "claim_artifacts_complete",
        "negative_results_preserved",
        "documentation_traceable",
    ],
)
def test_every_missing_control_blocks_external_status(field: str) -> None:
    externally_ready = replace(
        _facts(),
        independently_replicated_supported_claims=3,
        real_workload_supported_claims=1,
        restricted_data_present=False,
    )
    result = assess_readiness(
        replace(externally_ready, **cast(Any, {field: False}))
    )
    assert result["status"] != "EXTERNALLY_VALIDATED_RESEARCH_SYSTEM"
    assert result["blocking_facts"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("supported_claims", -1),
        ("independently_replicated_supported_claims", -1),
        ("real_workload_supported_claims", -1),
        ("independently_replicated_supported_claims", 4),
        ("real_workload_supported_claims", 4),
    ],
)
def test_impossible_claim_counts_are_rejected(field: str, value: int) -> None:
    with pytest.raises(ValueError):
        assess_readiness(replace(_facts(), **cast(Any, {field: value})))


def test_repository_facts_are_machine_derived() -> None:
    facts = collect_facts(ROOT)
    assert facts.supported_claims > 0
    assert facts.independently_replicated_supported_claims <= facts.supported_claims
    result = assess_readiness(facts)
    assert result["blocking_facts"]
