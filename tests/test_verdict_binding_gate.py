"""The verdict-binding gate must fail on exactly the forgeries that used to pass.

Each test below reproduces one break-in from the 2026-08-08 independent audit, where
`make pr-fast` reported ALL GATES PASSED with three registry statuses flipped by hand.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.verdict_binding_gate import (
    STATUS_POLARITY,
    VERDICT_POLARITY,
    audit,
    audit_ladder_binding,
    self_test,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads((ROOT / "claim_registry.json").read_text())


def test_the_real_registry_is_coherent(registry: dict) -> None:
    assert audit(registry) == []
    assert audit_ladder_binding(registry) == []


def test_every_claim_carries_a_binding_decision(registry: dict) -> None:
    """Fail-closed: a claim added without a binding must not slip through as 'unchecked'."""
    for claim in registry["claims"]:
        assert "verdict_binding" in claim, claim["claim_id"]
        if claim["verdict_binding"] is None:
            assert claim["status"] == "NOT_TESTED", claim["claim_id"]


def test_flipping_a_negative_verdict_is_detected(registry: dict) -> None:
    forged = copy.deepcopy(registry)
    for claim in forged["claims"]:
        if claim["claim_id"] == "CWC-L3-rcfr":
            claim["status"] = "SUPPORTED"
    errors = audit(forged, check_commit=False)
    assert any("CWC-L3-rcfr" in e and "NEGATIVE" in e for e in errors), errors


def test_promoting_an_untested_claim_is_detected(registry: dict) -> None:
    forged = copy.deepcopy(registry)
    for claim in forged["claims"]:
        if claim["claim_id"] == "CWC-L7-pareto":
            claim["status"] = "SUPPORTED"
    errors = audit(forged, check_commit=False)
    assert any("CWC-L7-pareto" in e for e in errors), errors


def test_unknown_verdict_string_fails_rather_than_defaults(registry: dict) -> None:
    forged = copy.deepcopy(registry)
    for claim in forged["claims"]:
        binding = claim.get("verdict_binding")
        if binding and binding["pointer"]:
            binding["expected"] = "A_VERDICT_NOBODY_DECLARED"
            break
    errors = audit(forged, check_commit=False)
    assert errors, "an undeclared verdict must fail closed, not pass by default"


def test_ladder_desync_from_the_registry_is_detected(registry: dict) -> None:
    forged = copy.deepcopy(registry)
    for claim in forged["claims"]:
        if claim["claim_id"] == "CWC-L2b-route-decision-cost":
            claim["status"] = "NOT_SUPPORTED"
    errors = audit_ladder_binding(forged)
    assert any("surface-matched" in e for e in errors), errors


def test_narrowed_status_must_name_its_limitation(registry: dict) -> None:
    forged = copy.deepcopy(registry)
    for claim in forged["claims"]:
        if claim["status"] == "SUPPORTED_NARROWED":
            claim["limitations"] = []
            break
    errors = audit(forged, check_commit=False)
    assert any("empty limitations" in e for e in errors), errors


def test_polarity_table_is_not_a_substring_classifier() -> None:
    """`NEGATIVE_IS_MECHANISM_SPECIFIC` supports its claim; a naive matcher inverts it."""
    assert VERDICT_POLARITY["NEGATIVE_IS_MECHANISM_SPECIFIC"] == "POSITIVE"
    assert VERDICT_POLARITY["ROUTING_END_TO_END_NOT_SUPPORTED"] == "NEGATIVE"
    assert VERDICT_POLARITY["CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED"] == "NEGATIVE"
    assert VERDICT_POLARITY["NPI_01_FIRST_ORDER_CERTIFICATE_NOT_SUPPORTED"] == "NEGATIVE"
    assert STATUS_POLARITY["SUPPORTED_NARROWED"] == "POSITIVE"


def test_gate_self_test_passes() -> None:
    assert self_test() == []
