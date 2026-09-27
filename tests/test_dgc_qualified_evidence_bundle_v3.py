from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import cwc.governance.qualified_evidence_bundle as qeb


def _write(root: Path, rel: str, data: bytes | str = b"x\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def test_verification_graph_includes_plan_v4_activation_runtime_regression_and_raw_subjects(tmp_path: Path, monkeypatch):
    report_rel = "artifacts/dgc-product-v1/generated/swe/report.json"
    plan_rel = "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V4.json"
    activation_rel = "artifacts/dgc-product-v1/verifier-regression/activation-authority.json"
    activation_policy = "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json"
    allowed = "artifacts/dgc-product-v1/trust/allowed_signers"
    activation_attestations = [
        "artifacts/dgc-product-v1/verifier-regression/verifier-a.json",
        "artifacts/dgc-product-v1/verifier-regression/verifier-b.json",
    ]
    activation_signatures = [
        "artifacts/dgc-product-v1/verifier-regression/verifier-a.sig",
        "artifacts/dgc-product-v1/verifier-regression/verifier-b.sig",
    ]
    regression_rel = "artifacts/dgc-product-v1/verifier-regression/receipt.json"
    regression_stdout = "artifacts/dgc-product-v1/verifier-regression/stdout.bin"
    regression_stderr = "artifacts/dgc-product-v1/verifier-regression/stderr.bin"
    regression_test = "tests/test_dgc_p19_external_replay.py"
    dependencies = (
        "cwc/governance/p19_external_verification_contract.py",
        "cwc/governance/p19_external_replay.py",
    )
    check_paths = {
        "receipt": "artifacts/dgc-product-v1/generated/swe/check.json",
        "stdout": "artifacts/dgc-product-v1/generated/swe/check.stdout",
        "stderr": "artifacts/dgc-product-v1/generated/swe/check.stderr",
        "evidence": "artifacts/dgc-product-v1/generated/swe/check.evidence.json",
    }

    nonempty = (
        report_rel, plan_rel, activation_rel, activation_policy, allowed,
        *activation_attestations, *activation_signatures,
        regression_rel, regression_stdout, regression_test,
        "scripts/dgc_external_p19_verifier.py", *dependencies,
        check_paths["receipt"], check_paths["stdout"], check_paths["evidence"],
    )
    for rel in nonempty:
        _write(tmp_path, rel, "x\n")
    for rel in (regression_stderr, check_paths["stderr"]):
        _write(tmp_path, rel, b"")

    monkeypatch.setattr(
        qeb,
        "load_p19_verification_report",
        lambda path, repository_root: {
            "verification_plan_path": plan_rel,
            "verifier_entrypoint_path": "scripts/dgc_external_p19_verifier.py",
            "checks": [{
                "check_id": "PRIMARY_P9_RAW_REPLAY",
                **{f"{role}_path": value for role, value in check_paths.items()},
            }],
        },
    )
    monkeypatch.setattr(
        qeb,
        "load_p19_external_verification_plan",
        lambda *args, **kwargs: SimpleNamespace(
            verifier_dependencies=tuple({"path": rel} for rel in dependencies),
            activation_authority_path=activation_rel,
            activation_authority_digest="a" * 64,
            activation_regression_receipt_path=regression_rel,
            activation_regression_receipt_digest="d" * 64,
        ),
    )
    monkeypatch.setattr(
        qeb,
        "verify_p19_external_verifier_activation_authority_document",
        lambda *args, **kwargs: {
            "authority_digest": "a" * 64,
            "activation_authorized": True,
            "all_signatures_verified": True,
            "trust_policy_path": activation_policy,
            "regression_receipt_path": regression_rel,
            "attestation_paths": activation_attestations,
            "signature_paths": activation_signatures,
            "verifier_principals": ["verifier-a", "verifier-b"],
            "signer_key_digests": ["b" * 64, "c" * 64],
        },
    )
    monkeypatch.setattr(qeb, "load_p19_verifier_trust_policy", lambda path: object())
    monkeypatch.setattr(qeb, "resolve_allowed_signers", lambda policy, repository_root: tmp_path / allowed)
    monkeypatch.setattr(
        qeb,
        "verify_p19_external_verifier_regression_receipt",
        lambda *args, **kwargs: {
            "receipt_digest": "d" * 64,
            "runtime_manifest": [
                {"path": "scripts/dgc_external_p19_verifier.py"},
                *({"path": rel} for rel in dependencies),
            ],
            "test_manifest": [{"path": regression_test}],
            "stdout_path": regression_stdout,
            "stderr_path": regression_stderr,
        },
    )

    paths, zero_ok = qeb._collect_verification_transcript_paths(tmp_path, report_rel)
    expected = {
        report_rel, plan_rel, activation_rel, activation_policy, allowed,
        *activation_attestations, *activation_signatures,
        regression_rel, regression_stdout, regression_stderr, regression_test,
        "scripts/dgc_external_p19_verifier.py", *dependencies,
        *check_paths.values(),
    }
    assert paths == expected
    assert zero_ok == {regression_stderr, check_paths["stdout"], check_paths["stderr"]}


def test_bundle_v7_declares_dual_activation_portable_replay_and_verifier_dependency_closure():
    assert qeb.SCHEMA == "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V7"
    fields = qeb.QualifiedEvidenceBundleAuthority.__dataclass_fields__
    for field in (
        "raw_p19_verification_transcripts_included",
        "frozen_verification_plan_and_entrypoint_included",
        "frozen_verifier_dependency_closure_included",
        "dual_signed_verifier_activation_authority_included",
        "activation_regression_evidence_included",
        "portable_p19_replay_inputs_included",
        "portable_global_v5_authority_included",
    ):
        assert field in fields
