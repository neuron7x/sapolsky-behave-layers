from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.evidence_closure import RECEIPT_SCHEMA, SCHEMA as LEDGER_SCHEMA, STAGES
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_evidence_root import (
    REQUIRED_EXTERNAL_REPLAY_INPUTS,
    REQUIRED_SUBJECT_ROOTS,
    SCHEMA,
    P19EvidenceError,
    _theorem_identity_digest,
    verify_family_p19_evidence_root_document,
)

COMMIT = "1" * 40
TREE = "2" * 40
GENERATION = "family-run"


def _snapshot_and_stage_rows():
    completed = list(STAGES[: STAGES.index("P19_SEALED")])
    receipts = []
    stage_rows = []
    prior = None
    for index, stage in enumerate(completed):
        evidence = {"path": f"evidence/{index}.json", "sha256": f"{index + 1:064x}"[-64:], "bytes": 2}
        payload = {
            "schema": RECEIPT_SCHEMA,
            "generation_id": GENERATION,
            "repo_commit": COMMIT,
            "repo_tree": TREE,
            "stage": stage,
            "prior_receipt_digest": prior,
            "commands": [],
            "evidence": [evidence],
        }
        digest = sha256_bytes(canonical_json_bytes(payload))
        receipt = {**payload, "receipt_digest": digest}
        receipts.append(receipt)
        stage_rows.append({"stage": stage, "receipt_digest": digest, "evidence": evidence})
        prior = digest
    snapshot = {
        "schema": LEDGER_SCHEMA,
        "generation_id": GENERATION,
        "repo_commit": COMMIT,
        "repo_tree": TREE,
        "completed_stages": completed,
        "receipts": receipts,
        "product_qualified": False,
    }
    return snapshot, stage_rows


def _doc() -> dict[str, object]:
    snapshot, stage_rows = _snapshot_and_stage_rows()
    roots = [{"label": label} for label in sorted(REQUIRED_SUBJECT_ROOTS)]
    replay = [
        {
            "label": label,
            "path": f"replay/{index:02d}-{label.lower()}.json",
            "sha256": f"{index + 100:064x}"[-64:],
            "bytes": index + 1,
        }
        for index, label in enumerate(sorted(REQUIRED_EXTERNAL_REPLAY_INPUTS))
    ]
    payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "generation_id": GENERATION,
        "repository_commit": COMMIT,
        "repository_tree": TREE,
        "ledger_schema": LEDGER_SCHEMA,
        "ledger_snapshot_digest": sha256_bytes(canonical_json_bytes(snapshot)),
        "ledger_snapshot": snapshot,
        "receipt_chain_tip_digest": snapshot["receipts"][-1]["receipt_digest"],
        "stage_evidence_manifest_digest": sha256_bytes(canonical_json_bytes(stage_rows)),
        "stage_evidence": stage_rows,
        "primary_p9_scientific_authority_digest": "a" * 64,
        "primary_anytime_p9_authority_digest": "b" * 64,
        "primary_ccf_oracle_audit_authority_digest": "c" * 64,
        "generalization_authority_digest": "d" * 64,
        "fault_tolerance_authority_digest": "e" * 64,
        "independent_replication_authority_digest": "f" * 64,
        "statistical_plan_digest": "1" * 64,
        "theorem_identity_digest": _theorem_identity_digest(),
        "methodology_anchor_digest": "2" * 64,
        "methodology_anchors": [],
        "subject_root_manifest_digest": sha256_bytes(canonical_json_bytes(roots)),
        "subject_roots": roots,
        "external_replay_input_manifest_digest": sha256_bytes(canonical_json_bytes(replay)),
        "external_replay_inputs": replay,
        "family_p9_supported": True,
        "family_generalization_supported": True,
        "family_fault_tolerance_supported": True,
        "family_replication_supported": True,
        "family_evidence_complete": True,
    }
    return {
        "schema": SCHEMA,
        **payload,
        "p19_digest": sha256_bytes(canonical_json_bytes(payload)),
        "p19_sealed": True,
        "portable_external_replay_inputs_sealed": True,
        "family_qualification_ready": True,
        "global_product_qualification_authorized": False,
        "peer_family_p19_required": True,
    }


def _write(tmp_path: Path, doc: dict[str, object]) -> Path:
    path = tmp_path / "p19.json"
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return path


def _redigest(doc: dict[str, object]) -> None:
    keys = (
        "family_id", "generation_id", "repository_commit", "repository_tree", "ledger_schema",
        "ledger_snapshot_digest", "ledger_snapshot", "receipt_chain_tip_digest",
        "stage_evidence_manifest_digest", "stage_evidence", "primary_p9_scientific_authority_digest",
        "primary_anytime_p9_authority_digest", "primary_ccf_oracle_audit_authority_digest",
        "generalization_authority_digest", "fault_tolerance_authority_digest",
        "independent_replication_authority_digest", "statistical_plan_digest", "theorem_identity_digest",
        "methodology_anchor_digest", "methodology_anchors", "subject_root_manifest_digest", "subject_roots",
        "external_replay_input_manifest_digest", "external_replay_inputs",
        "family_p9_supported", "family_generalization_supported", "family_fault_tolerance_supported",
        "family_replication_supported", "family_evidence_complete",
    )
    doc["p19_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in keys}))


def test_valid_structural_p19_v3_verifies(tmp_path: Path):
    doc = verify_family_p19_evidence_root_document(_write(tmp_path, _doc()))
    assert doc["p19_sealed"] is True
    assert doc["portable_external_replay_inputs_sealed"] is True
    assert len(doc["external_replay_inputs"]) == len(REQUIRED_EXTERNAL_REPLAY_INPUTS)


def test_self_consistent_receipt_chain_tamper_is_rejected(tmp_path: Path):
    doc = _doc()
    snapshot = doc["ledger_snapshot"]
    snapshot["receipts"][2]["prior_receipt_digest"] = "0" * 64
    doc["ledger_snapshot_digest"] = sha256_bytes(canonical_json_bytes(snapshot))
    _redigest(doc)
    with pytest.raises(P19EvidenceError, match="receipt chain"):
        verify_family_p19_evidence_root_document(_write(tmp_path, doc))


def test_stage_manifest_cannot_point_to_different_evidence_than_embedded_ledger(tmp_path: Path):
    doc = _doc()
    doc["stage_evidence"][0]["evidence"] = {
        "path": "other.json", "sha256": "9" * 64, "bytes": 2
    }
    doc["stage_evidence_manifest_digest"] = sha256_bytes(canonical_json_bytes(doc["stage_evidence"]))
    _redigest(doc)
    with pytest.raises(P19EvidenceError, match="differs from embedded receipt evidence"):
        verify_family_p19_evidence_root_document(_write(tmp_path, doc))


def test_v5_theorem_identity_cannot_be_substituted_even_with_recomputed_p19_digest(tmp_path: Path):
    doc = _doc()
    doc["theorem_identity_digest"] = "9" * 64
    _redigest(doc)
    with pytest.raises(P19EvidenceError, match="current V5"):
        verify_family_p19_evidence_root_document(_write(tmp_path, doc))


def test_missing_replay_locator_fails_even_with_recomputed_manifest_and_p19_digest(tmp_path: Path):
    doc = _doc()
    doc["external_replay_inputs"].pop()
    doc["external_replay_input_manifest_digest"] = sha256_bytes(canonical_json_bytes(doc["external_replay_inputs"]))
    _redigest(doc)
    with pytest.raises(P19EvidenceError, match="replay input population"):
        verify_family_p19_evidence_root_document(_write(tmp_path, doc))


def test_duplicate_replay_path_fails_even_with_recomputed_manifest_and_p19_digest(tmp_path: Path):
    doc = _doc()
    doc["external_replay_inputs"][1]["path"] = doc["external_replay_inputs"][0]["path"]
    doc["external_replay_input_manifest_digest"] = sha256_bytes(canonical_json_bytes(doc["external_replay_inputs"]))
    _redigest(doc)
    with pytest.raises(P19EvidenceError, match="paths must be distinct"):
        verify_family_p19_evidence_root_document(_write(tmp_path, doc))


def test_noncanonical_replay_path_fails_closed(tmp_path: Path):
    doc = _doc()
    doc["external_replay_inputs"][0]["path"] = "../escape.json"
    doc["external_replay_input_manifest_digest"] = sha256_bytes(canonical_json_bytes(doc["external_replay_inputs"]))
    _redigest(doc)
    with pytest.raises(P19EvidenceError, match="repository-relative"):
        verify_family_p19_evidence_root_document(_write(tmp_path, doc))


def test_one_family_p19_cannot_claim_global_qualification(tmp_path: Path):
    doc = _doc()
    doc["global_product_qualification_authorized"] = True
    with pytest.raises(P19EvidenceError, match="global claim boundary"):
        verify_family_p19_evidence_root_document(_write(tmp_path, doc))
