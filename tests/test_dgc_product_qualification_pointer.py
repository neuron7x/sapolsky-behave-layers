from __future__ import annotations

from pathlib import Path

import pytest

import cwc.governance.product_qualification_pointer as pqp
from cwc.governance.evidence_closure import STAGES
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.product_qualification_pointer import (
    SCHEMA,
    ProductQualificationPointerError,
    verify_product_qualification_pointer,
)


def _pointer_doc(
    *,
    ledger_path: str,
    global_path: str,
    ledger_sha: str,
    global_sha: str,
    global_digest: str,
    active: bool = True,
    claimed: bool = True,
    commit: str = "a" * 40,
    tree: str = "b" * 40,
) -> dict[str, object]:
    payload = {
        "pointer_generation": "TEST_POINTER_V1",
        "activation_authorized": active,
        "ledger_path": ledger_path,
        "global_v4_authority_path": global_path,
        "generation_id": "generation-1" if active else "UNCONFIGURED",
        "repo_commit": commit,
        "repo_tree": tree,
        "ledger_sha256": ledger_sha,
        "global_v4_authority_sha256": global_sha,
        "global_v4_authority_digest": global_digest,
        "product_qualified_claimed": claimed,
        "production_control_authorized": False,
    }
    return {"schema": SCHEMA, **payload, "pointer_digest": sha256_bytes(canonical_json_bytes(payload))}


def _write_pointer(path: Path, doc: dict[str, object]) -> None:
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def _terminal_state(global_rel: str, global_sha: str, global_bytes: int):
    receipts = []
    prior = None
    for stage in STAGES:
        evidence = [{
            "path": global_rel if stage == "PRODUCT_QUALIFIED" else f"artifacts/{stage}.json",
            "sha256": global_sha if stage == "PRODUCT_QUALIFIED" else "1" * 64,
            "bytes": global_bytes if stage == "PRODUCT_QUALIFIED" else 1,
        }]
        payload = {
            "schema": "DGC_EVIDENCE_CLOSURE_RECEIPT_V3",
            "generation_id": "generation-1",
            "repo_commit": "a" * 40,
            "repo_tree": "b" * 40,
            "stage": stage,
            "prior_receipt_digest": prior,
            "commands": [],
            "evidence": evidence,
        }
        digest = sha256_bytes(canonical_json_bytes(payload))
        receipts.append({**payload, "receipt_digest": digest})
        prior = digest
    return {
        "schema": "DGC_EVIDENCE_CLOSURE_LEDGER_V3",
        "generation_id": "generation-1",
        "repo_commit": "a" * 40,
        "repo_tree": "b" * 40,
        "completed_stages": list(STAGES),
        "receipts": receipts,
        "product_qualified": True,
    }


class _FakeLedger:
    state = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def load(self):
        return self.state


def _fixture(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "artifacts/ledger.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("ledger-bytes\n", encoding="utf-8")
    global_v4 = tmp_path / "artifacts/global-v4.json"
    global_v4.write_text("global-v4-bytes\n", encoding="utf-8")
    global_sha = sha256_file(global_v4)
    global_digest = "c" * 64
    _FakeLedger.state = _terminal_state("artifacts/global-v4.json", global_sha, global_v4.stat().st_size)
    monkeypatch.setattr(pqp, "EvidenceClosureLedger", _FakeLedger)
    monkeypatch.setattr(
        pqp,
        "verify_global_product_qualification_authority_v4_document",
        lambda path: {
            "authority_digest": global_digest,
            "repository_commit": "a" * 40,
            "repository_tree": "b" * 40,
            "product_qualified": True,
        },
    )
    pointer = tmp_path / "pointer.json"
    _write_pointer(
        pointer,
        _pointer_doc(
            ledger_path="artifacts/ledger.json",
            global_path="artifacts/global-v4.json",
            ledger_sha=sha256_file(ledger),
            global_sha=global_sha,
            global_digest=global_digest,
        ),
    )
    return ledger, global_v4, pointer


def test_pointer_replays_terminal_ledger_and_global_v4_binding(tmp_path: Path, monkeypatch):
    _, _, pointer = _fixture(tmp_path, monkeypatch)
    verified = verify_product_qualification_pointer(
        repository_root=tmp_path,
        pointer_path=pointer,
        expected_repo_commit="a" * 40,
        expected_repo_tree="b" * 40,
    )
    assert verified.global_v4_authority_digest == "c" * 64
    assert verified.ledger_tip_receipt_digest == _FakeLedger.state["receipts"][-1]["receipt_digest"]


def test_unconfigured_pointer_cannot_authorize_product_claim(tmp_path: Path):
    pointer = tmp_path / "pointer.json"
    _write_pointer(
        pointer,
        _pointer_doc(
            ledger_path="UNCONFIGURED",
            global_path="UNCONFIGURED",
            ledger_sha="0" * 64,
            global_sha="0" * 64,
            global_digest="0" * 64,
            active=False,
            claimed=False,
            commit="0" * 40,
            tree="0" * 40,
        ),
    )
    with pytest.raises(ProductQualificationPointerError, match="not activated"):
        verify_product_qualification_pointer(repository_root=tmp_path, pointer_path=pointer)


def test_release_head_mismatch_fails_before_evidence_acceptance(tmp_path: Path, monkeypatch):
    _, _, pointer = _fixture(tmp_path, monkeypatch)
    with pytest.raises(ProductQualificationPointerError, match="commit differs"):
        verify_product_qualification_pointer(
            repository_root=tmp_path,
            pointer_path=pointer,
            expected_repo_commit="d" * 40,
            expected_repo_tree="b" * 40,
        )


def test_global_v4_byte_substitution_fails_closed(tmp_path: Path, monkeypatch):
    _, global_v4, pointer = _fixture(tmp_path, monkeypatch)
    global_v4.write_text("mutated\n", encoding="utf-8")
    with pytest.raises(ProductQualificationPointerError, match="bytes differ"):
        verify_product_qualification_pointer(repository_root=tmp_path, pointer_path=pointer)


def test_terminal_receipt_cannot_reference_different_global_authority(tmp_path: Path, monkeypatch):
    _, global_v4, pointer = _fixture(tmp_path, monkeypatch)
    global_sha = sha256_file(global_v4)
    _FakeLedger.state = _terminal_state("artifacts/other-global.json", global_sha, global_v4.stat().st_size)
    with pytest.raises(ProductQualificationPointerError, match="different global authority"):
        verify_product_qualification_pointer(repository_root=tmp_path, pointer_path=pointer)


def test_pointer_digest_tamper_fails_closed(tmp_path: Path):
    path = tmp_path / "pointer.json"
    doc = _pointer_doc(
        ledger_path="x",
        global_path="y",
        ledger_sha="1" * 64,
        global_sha="2" * 64,
        global_digest="3" * 64,
    )
    doc["pointer_digest"] = "f" * 64
    _write_pointer(path, doc)
    with pytest.raises(ProductQualificationPointerError, match="digest mismatch"):
        pqp.load_product_qualification_pointer(path)
