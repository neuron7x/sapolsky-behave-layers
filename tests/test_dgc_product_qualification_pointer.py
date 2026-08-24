from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
    source_registry_path: str = "artifacts/source-registry.json",
    p19_paths: tuple[str, str] = ("artifacts/swe-p19.json", "artifacts/terminal-p19.json"),
    attestation_paths: tuple[str, str] = ("artifacts/swe.attestation.json", "artifacts/terminal.attestation.json"),
    report_paths: tuple[str, str] = ("artifacts/swe.report.json", "artifacts/terminal.report.json"),
    signature_paths: tuple[str, str] = ("artifacts/swe.sig", "artifacts/terminal.sig"),
    policy_path: str = "artifacts/policy.json",
    active: bool = True,
    claimed: bool = True,
    commit: str = "a" * 40,
    tree: str = "b" * 40,
) -> dict[str, object]:
    payload = {
        "pointer_generation": "TEST_POINTER_V2",
        "activation_authorized": active,
        "ledger_path": ledger_path,
        "global_v4_authority_path": global_path,
        "source_registry_path": source_registry_path,
        "family_p19_paths": list(p19_paths),
        "family_attestation_paths": list(attestation_paths),
        "family_verification_report_paths": list(report_paths),
        "family_signature_paths": list(signature_paths),
        "p19_verifier_policy_path": policy_path,
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


def _write_subject(path: Path, data: bytes = b"subject\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _fixture(tmp_path: Path, monkeypatch, *, rebuilt_digest: str = "c" * 64):
    ledger = tmp_path / "artifacts/ledger.json"
    _write_subject(ledger, b"ledger-bytes\n")
    global_v4 = tmp_path / "artifacts/global-v4.json"
    _write_subject(global_v4, b"global-v4-bytes\n")
    for rel in (
        "artifacts/source-registry.json",
        "artifacts/swe-p19.json",
        "artifacts/terminal-p19.json",
        "artifacts/swe.attestation.json",
        "artifacts/terminal.attestation.json",
        "artifacts/swe.report.json",
        "artifacts/terminal.report.json",
        "artifacts/swe.sig",
        "artifacts/terminal.sig",
        "artifacts/policy.json",
    ):
        _write_subject(tmp_path / rel)

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
            "production_control_authorized": False,
        },
    )
    monkeypatch.setattr(
        pqp,
        "build_global_product_qualification_authority_v4",
        lambda **kwargs: SimpleNamespace(
            authority_digest=rebuilt_digest,
            product_qualified=True,
            production_control_authorized=False,
            repository_commit="a" * 40,
            repository_tree="b" * 40,
        ),
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


def test_pointer_v2_rebuilds_global_v4_then_replays_terminal_ledger(tmp_path: Path, monkeypatch):
    _, _, pointer = _fixture(tmp_path, monkeypatch)
    verified = verify_product_qualification_pointer(
        repository_root=tmp_path,
        pointer_path=pointer,
        expected_repo_commit="a" * 40,
        expected_repo_tree="b" * 40,
    )
    assert verified.global_v4_authority_digest == "c" * 64
    assert verified.source_registry_path == "artifacts/source-registry.json"
    assert verified.family_p19_paths == ("artifacts/swe-p19.json", "artifacts/terminal-p19.json")
    assert verified.ledger_tip_receipt_digest == _FakeLedger.state["receipts"][-1]["receipt_digest"]


def test_self_consistent_declared_global_v4_cannot_substitute_for_failed_semantic_rebuild(tmp_path: Path, monkeypatch):
    _, _, pointer = _fixture(tmp_path, monkeypatch, rebuilt_digest="d" * 64)
    with pytest.raises(ProductQualificationPointerError, match="differs from semantic replay"):
        verify_product_qualification_pointer(repository_root=tmp_path, pointer_path=pointer)


def test_unconfigured_pointer_cannot_authorize_product_claim(tmp_path: Path):
    pointer = tmp_path / "pointer.json"
    _write_pointer(
        pointer,
        _pointer_doc(
            ledger_path="UNCONFIGURED",
            global_path="UNCONFIGURED",
            source_registry_path="UNCONFIGURED",
            p19_paths=("UNCONFIGURED", "UNCONFIGURED"),
            attestation_paths=("UNCONFIGURED", "UNCONFIGURED"),
            report_paths=("UNCONFIGURED", "UNCONFIGURED"),
            signature_paths=("UNCONFIGURED", "UNCONFIGURED"),
            policy_path="artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json",
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


def test_malformed_two_family_replay_population_is_rejected_at_pointer_parse(tmp_path: Path):
    path = tmp_path / "pointer.json"
    doc = _pointer_doc(
        ledger_path="x",
        global_path="y",
        ledger_sha="1" * 64,
        global_sha="2" * 64,
        global_digest="3" * 64,
    )
    doc["family_p19_paths"] = ["only-one"]
    payload_keys = (
        "pointer_generation", "activation_authorized", "ledger_path", "global_v4_authority_path",
        "source_registry_path", "family_p19_paths", "family_attestation_paths",
        "family_verification_report_paths", "family_signature_paths", "p19_verifier_policy_path",
        "generation_id", "repo_commit", "repo_tree", "ledger_sha256", "global_v4_authority_sha256",
        "global_v4_authority_digest", "product_qualified_claimed", "production_control_authorized",
    )
    doc["pointer_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in payload_keys}))
    _write_pointer(path, doc)
    with pytest.raises(ProductQualificationPointerError, match="exactly two"):
        pqp.load_product_qualification_pointer(path)


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
