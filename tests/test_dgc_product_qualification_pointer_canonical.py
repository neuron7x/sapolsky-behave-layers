from __future__ import annotations

from pathlib import Path

import pytest

import cwc.governance.product_qualification_pointer as pqp
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes


def _active_doc() -> dict[str, object]:
    payload = {
        "pointer_generation": "TEST_POINTER_V3",
        "activation_authorized": True,
        "ledger_path": "artifacts/ledger.json",
        "global_v5_authority_path": "artifacts/global-v5.json",
        "source_registry_path": "artifacts/source-registry.json",
        "family_p19_paths": ["artifacts/a-p19.json", "artifacts/b-p19.json"],
        "family_attestation_paths": ["artifacts/a-attestation.json", "artifacts/b-attestation.json"],
        "family_verification_report_paths": ["artifacts/a-report.json", "artifacts/b-report.json"],
        "family_signature_paths": ["artifacts/a.sig", "artifacts/b.sig"],
        "p19_verifier_policy_path": "artifacts/policy.json",
        "generation_id": "generation-1",
        "repo_commit": "a" * 40,
        "repo_tree": "b" * 40,
        "ledger_sha256": "1" * 64,
        "global_v5_authority_sha256": "2" * 64,
        "global_v5_authority_digest": "3" * 64,
        "product_qualified_claimed": True,
        "production_control_authorized": False,
    }
    return {"schema": pqp.SCHEMA, **payload, "pointer_digest": sha256_bytes(canonical_json_bytes(payload))}


def _rehash(doc: dict[str, object]) -> None:
    keys = (
        "pointer_generation", "activation_authorized", "ledger_path", "global_v5_authority_path",
        "source_registry_path", "family_p19_paths", "family_attestation_paths",
        "family_verification_report_paths", "family_signature_paths", "p19_verifier_policy_path",
        "generation_id", "repo_commit", "repo_tree", "ledger_sha256", "global_v5_authority_sha256",
        "global_v5_authority_digest", "product_qualified_claimed", "production_control_authorized",
    )
    doc["pointer_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in keys}))


def _write(path: Path, doc: dict[str, object]) -> None:
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


@pytest.mark.parametrize("bad", [
    " artifacts/a-p19.json",
    "artifacts/a-p19.json ",
    "artifacts//a-p19.json",
    "artifacts\\a-p19.json",
    "artifacts/a\tp19.json",
    "../artifacts/a-p19.json",
])
def test_pointer_v3_rejects_path_normalization_ambiguity_even_with_rehashed_pointer(tmp_path: Path, bad: str):
    doc = _active_doc()
    doc["family_p19_paths"][0] = bad
    _rehash(doc)
    path = tmp_path / "pointer.json"
    _write(path, doc)
    with pytest.raises(pqp.ProductQualificationPointerError, match="canonical repository-relative POSIX path"):
        pqp.load_product_qualification_pointer(path)


@pytest.mark.parametrize(("field", "bad"), [
    ("repo_commit", "A" * 40),
    ("repo_tree", " B" * 20),
    ("ledger_sha256", "A" * 64),
    ("global_v5_authority_digest", "3" * 63 + "F"),
])
def test_pointer_v3_rejects_noncanonical_object_identity_text_at_semantic_verification(tmp_path: Path, field: str, bad: str):
    doc = _active_doc()
    doc[field] = bad
    _rehash(doc)
    path = tmp_path / "pointer.json"
    _write(path, doc)
    if field in {"ledger_sha256", "global_v5_authority_digest"}:
        # Pointer digest parsing itself is canonical, but these fields are consumed only after activation.
        # Create referenced paths so execution reaches identity parsing rather than file-not-found when possible.
        for rel in ("artifacts/ledger.json", "artifacts/global-v5.json", "artifacts/source-registry.json", "artifacts/policy.json"):
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
        for rel in doc["family_p19_paths"] + doc["family_attestation_paths"] + doc["family_verification_report_paths"] + doc["family_signature_paths"]:
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
    with pytest.raises(pqp.ProductQualificationPointerError):
        pqp.verify_product_qualification_pointer(repository_root=tmp_path, pointer_path=path)
