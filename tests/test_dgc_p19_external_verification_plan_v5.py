from __future__ import annotations

from pathlib import Path

import pytest

import cwc.governance.p19_external_verification_plan_v5 as v5
from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_verification_contract import CHECK_METHOD_IDS
from cwc.governance.p19_external_verifier_activation_v2 import SIGNATURE_SEMANTICS


def _core():
    return {
        "schema": "DGC_P19_EXTERNAL_VERIFICATION_PLAN_V4",
        "verifier_entrypoint_path": v5.ENTRYPOINT,
        "verifier_entrypoint_sha256": "1" * 64,
        "verifier_dependency_manifest_digest": "2" * 64,
        "verifier_dependencies": [{"path": "cwc/governance/x.py", "sha256": "3" * 64, "bytes": 1}],
        "check_contracts": [
            {
                "check_id": check_id,
                "method_id": CHECK_METHOD_IDS[check_id],
                "command_template": [
                    "python", v5.ENTRYPOINT, "--check-id", check_id,
                    "--p19", "{P19_PATH}", "--evidence-output", "{EVIDENCE_PATH}",
                ],
                "implementation_status": "IMPLEMENTED",
            }
            for check_id in sorted(CHECK_METHOD_IDS)
        ],
        "all_check_implementations_complete": True,
    }


def _activation(root: Path, *, tool_authoritative: bool = False):
    authority = root / "artifacts/dgc-product-v1/generated/verifier-activation/activation-v2.json"
    authority.parent.mkdir(parents=True, exist_ok=True)
    authority.write_text("{}\n", encoding="utf-8")
    doc = {
        "activation_authorized": True,
        "all_signatures_verified": True,
        "signature_semantics": SIGNATURE_SEMANTICS,
        "signature_tool_execution_provenance_authoritative": tool_authoritative,
        "authority_digest": "4" * 64,
        "trust_policy_path": "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json",
        "trust_policy_digest": "5" * 64,
        "allowed_signers_sha256": "6" * 64,
        "verifier_principals": ["verifier-a", "verifier-b"],
        "signer_key_digests": ["7" * 64, "8" * 64],
        "regression_receipt_path": "artifacts/dgc-product-v1/generated/verifier-regression/receipt.json",
        "regression_receipt_sha256": "9" * 64,
        "regression_receipt_digest": "a" * 64,
        "source_commit": "b" * 40,
        "source_tree": "c" * 40,
        "test_manifest_digest": "d" * 64,
    }
    return authority, doc


def test_inactive_v5_has_no_activation_evidence(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(v5, "build_v4_inactive_plan", lambda **kwargs: _core())
    doc = v5.build_inactive_p19_external_verification_plan_v5_document(repository_root=tmp_path)
    assert doc["schema"] == v5.SCHEMA
    assert doc["activation_authorized"] is False
    assert doc["activation_authority_path"] is None
    assert doc["activation_signature_semantics"] is None
    assert doc["activation_signature_tool_execution_provenance_authoritative"] is False
    assert doc["product_qualification_authorized"] is False


def test_active_v5_binds_portable_v2_not_machine_local_signature_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(v5, "build_v4_inactive_plan", lambda **kwargs: _core())
    authority, activation = _activation(tmp_path)
    monkeypatch.setattr(
        v5,
        "verify_p19_external_verifier_activation_authority_v2_document",
        lambda *args, **kwargs: activation,
    )
    doc = v5.build_activated_p19_external_verification_plan_v5_document(
        repository_root=tmp_path,
        activation_authority_path=authority,
    )
    assert doc["activation_authorized"] is True
    assert doc["activation_signature_semantics"] == SIGNATURE_SEMANTICS
    assert doc["activation_signature_tool_execution_provenance_authoritative"] is False
    assert doc["activation_authority_digest"] == "4" * 64
    assert "ssh_keygen_path" not in doc
    assert "signature_receipt_digests" not in doc


def test_active_v5_rejects_machine_local_signature_provenance_as_authority(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(v5, "build_v4_inactive_plan", lambda **kwargs: _core())
    authority, activation = _activation(tmp_path, tool_authoritative=True)
    monkeypatch.setattr(
        v5,
        "verify_p19_external_verifier_activation_authority_v2_document",
        lambda *args, **kwargs: activation,
    )
    with pytest.raises(v5.P19ExternalVerificationPlanV5Error, match="machine-local signature-tool"):
        v5.build_activated_p19_external_verification_plan_v5_document(
            repository_root=tmp_path,
            activation_authority_path=authority,
        )


def test_v5_loader_fails_if_runtime_core_changes_after_freeze(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(v5, "build_v4_inactive_plan", lambda **kwargs: _core())
    doc = v5.build_inactive_p19_external_verification_plan_v5_document(repository_root=tmp_path)
    plan = tmp_path / "plan-v5.json"
    plan.write_bytes(canonical_json_bytes(doc) + b"\n")
    mutated = _core()
    mutated["verifier_entrypoint_sha256"] = "f" * 64
    monkeypatch.setattr(v5, "build_v4_inactive_plan", lambda **kwargs: mutated)
    with pytest.raises(v5.P19ExternalVerificationPlanV5Error, match="differs from current portable composition replay"):
        v5.load_p19_external_verification_plan_v5(
            plan,
            repository_root=tmp_path,
            require_active=False,
        )


def test_v5_command_contract_is_exact(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(v5, "build_v4_inactive_plan", lambda **kwargs: _core())
    doc = v5.build_inactive_p19_external_verification_plan_v5_document(repository_root=tmp_path)
    plan_path = tmp_path / "plan-v5.json"
    plan_path.write_bytes(canonical_json_bytes(doc) + b"\n")
    plan = v5.load_p19_external_verification_plan_v5(
        plan_path,
        repository_root=tmp_path,
        require_active=False,
    )
    check = "REPOSITORY_IDENTITY"
    expected = (
        "python", v5.ENTRYPOINT, "--check-id", check,
        "--p19", "artifacts/p19.json", "--evidence-output", "artifacts/evidence.json",
    )
    v5.verify_command_against_plan_v5(
        plan,
        check_id=check,
        command_argv=expected,
        p19_path="artifacts/p19.json",
        evidence_path="artifacts/evidence.json",
    )
    with pytest.raises(v5.P19ExternalVerificationPlanV5Error, match="differs from Plan V5"):
        v5.verify_command_against_plan_v5(
            plan,
            check_id=check,
            command_argv=("echo", "PASS"),
            p19_path="artifacts/p19.json",
            evidence_path="artifacts/evidence.json",
        )
