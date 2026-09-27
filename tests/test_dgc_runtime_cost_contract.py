from __future__ import annotations

import pytest

from cwc.governance.runtime_cost_contract import (
    RuntimeCostContractError,
    parse_runtime_cost_contract,
    runtime_physical_cost_evidence,
)


def _contract():
    return {
        "schema": "DGC_RUNTIME_COST_CONTRACT_V1",
        "allocation_policy": "ALL_LOCAL_COMPUTE_TO_INFRA_V1",
        "host_profile_id": "host-a",
        "infra_usd_per_second": 0.001,
        "infra_rate_source_uri": "https://example.invalid/host-rate",
        "infra_rate_captured_at": "2026-09-27T00:00:00Z",
        "billable_external_tools_allowed": False,
        "paid_retrieval_allowed": False,
        "human_review_allowed": False,
        "automatic_retries_allowed": False,
        "zero_by_contract": {
            "router_usd": "ROUTER_INCLUDED_IN_INFRA_V1",
            "countermodel_usd": "NO_COUNTERMODEL_V1",
            "retrieval_usd": "NO_PAID_RETRIEVAL_V1",
            "tools_usd": "NO_PAID_EXTERNAL_TOOLS_V1",
            "verification_usd": "VERIFIER_INCLUDED_IN_INFRA_V1",
            "human_review_usd": "NO_HUMAN_REVIEW_V1",
            "retry_usd": "NO_AUTOMATIC_RETRIES_V1",
            "failure_loss_usd": "NO_EXTERNAL_FAILURE_LOSS_V1",
        },
    }


def test_runtime_cost_contract_mints_complete_non_model_evidence():
    contract = parse_runtime_cost_contract(_contract())
    evidence, measurement, infra_usd = runtime_physical_cost_evidence(
        contract=contract,
        budget_manifest_sha256="a" * 64,
        elapsed_ns=2_000_000_000,
    )
    assert set(evidence) == {
        "router_usd",
        "countermodel_usd",
        "retrieval_usd",
        "tools_usd",
        "verification_usd",
        "human_review_usd",
        "infra_usd",
        "retry_usd",
        "failure_loss_usd",
    }
    assert infra_usd == pytest.approx(0.002)
    assert evidence["infra_usd"]["authority"] == "INFRA_METER"
    assert evidence["router_usd"]["authority"] == "ZERO_BY_CONTRACT"
    assert len(evidence["infra_usd"]["source_digest"]) == 64
    assert measurement["budget_manifest_sha256"] == "a" * 64


@pytest.mark.parametrize(
    "field",
    [
        "billable_external_tools_allowed",
        "paid_retrieval_allowed",
        "human_review_allowed",
        "automatic_retries_allowed",
    ],
)
def test_runtime_cost_contract_rejects_unbounded_paid_side_channel(field: str):
    doc = _contract()
    doc[field] = True
    with pytest.raises(RuntimeCostContractError, match=field):
        parse_runtime_cost_contract(doc)


def test_runtime_cost_contract_rejects_missing_component_clause():
    doc = _contract()
    del doc["zero_by_contract"]["failure_loss_usd"]
    with pytest.raises(RuntimeCostContractError, match="component population"):
        parse_runtime_cost_contract(doc)


def test_runtime_cost_contract_requires_positive_infra_rate():
    doc = _contract()
    doc["infra_usd_per_second"] = 0.0
    with pytest.raises(RuntimeCostContractError, match="infra_usd_per_second"):
        parse_runtime_cost_contract(doc)


def test_runtime_measurement_rejects_nonpositive_elapsed_time():
    contract = parse_runtime_cost_contract(_contract())
    with pytest.raises(RuntimeCostContractError, match="elapsed_ns"):
        runtime_physical_cost_evidence(
            contract=contract,
            budget_manifest_sha256="a" * 64,
            elapsed_ns=0,
        )
