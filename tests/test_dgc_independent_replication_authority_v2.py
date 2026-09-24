from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.independent_replication_authority_v2 import (
    IndependentReplicationAuthorityError,
    verify_independent_replication_authority_v2_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes


def h(char: str) -> str:
    return char * 64


def document(*, fresh: bool = True, machine_proven: bool = False, supported: bool = True) -> dict:
    payload = {
        "replication_scope": "PRIMARY_P9_CORE_FRESH_EXTERNAL_REPLAY_WITH_G1_G5_CONTEXT_V1",
        "replication_package_digest": h("1"),
        "primary_p9_scientific_authority_digest": h("2"),
        "primary_generalization_scientific_authority_digest": h("3"),
        "replica_p9_scientific_authority_digest": h("4"),
        "primary_execution_population_digest": h("5"),
        "replica_execution_population_digest": h("6") if fresh else h("5"),
        "primary_execution_bundle_digest": h("7"),
        "replica_execution_bundle_digest": h("8") if fresh else h("7"),
        "primary_physical_cost_population_digest": h("9"),
        "replica_physical_cost_population_digest": h("a"),
        "primary_ccf_evidence_population_digest": h("b"),
        "replica_ccf_evidence_population_digest": h("c"),
        "harness_freeze_digest": h("d"),
        "confirmatory_task_manifest_digest": h("e"),
        "statistical_plan_digest": h("f"),
        "frozen_dgc_policy_digest": h("0"),
        "methodology_identity_matched": True,
        "fresh_execution_verified": fresh,
        "replica_p9_supported_under_frozen_assumptions": True,
        "replication_signature_receipt_digest": h("1"),
        "replicator_principal": "external-lab",
        "signed_independence_attested": True,
        "social_independence_machine_proven": machine_proven,
        "independent_replication_supported": supported,
    }
    return {
        "schema": "DGC_INDEPENDENT_REPLICATION_AUTHORITY_V2",
        **payload,
        "authority_digest": sha256_bytes(canonical_json_bytes(payload)),
        "product_promotion_authorized": False,
    }


def write(path: Path, doc: dict) -> Path:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_valid_replication_authority_is_fresh_but_does_not_claim_social_proof(tmp_path: Path):
    doc = verify_independent_replication_authority_v2_document(
        write(tmp_path / "replication.json", document())
    )
    assert doc["independent_replication_supported"] is True
    assert doc["social_independence_machine_proven"] is False


def test_reused_primary_execution_is_rejected(tmp_path: Path):
    with pytest.raises(IndependentReplicationAuthorityError, match="reused primary execution population"):
        verify_independent_replication_authority_v2_document(
            write(tmp_path / "replication.json", document(fresh=False, supported=False))
        )


def test_machine_cannot_claim_social_independence_proof(tmp_path: Path):
    with pytest.raises(IndependentReplicationAuthorityError, match="must not claim proof"):
        verify_independent_replication_authority_v2_document(
            write(tmp_path / "replication.json", document(machine_proven=True))
        )


def test_support_flag_must_be_derived_from_evidence_and_attestation(tmp_path: Path):
    with pytest.raises(IndependentReplicationAuthorityError, match="not derived"):
        verify_independent_replication_authority_v2_document(
            write(tmp_path / "replication.json", document(supported=False))
        )
