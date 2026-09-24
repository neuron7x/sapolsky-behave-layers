from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import cwc.governance.qualified_evidence_bundle as qeb
from cwc.governance.qualified_evidence_bundle import (
    QualifiedEvidenceBundleError,
    ROLE_EXECUTION_SOURCE,
    ROLE_PACKAGING_EVIDENCE,
    SCHEMA,
    build_qualified_evidence_bundle_authority,
)

PLAN_REL = "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V4.json"
ACTIVATION_REL = "artifacts/dgc-product-v1/verifier-regression/activation-authority.json"
REGRESSION_RECEIPT_REL = "artifacts/dgc-product-v1/verifier-regression/receipt.json"
REGRESSION_STDOUT_REL = "artifacts/dgc-product-v1/verifier-regression/stdout.bin"
REGRESSION_STDERR_REL = "artifacts/dgc-product-v1/verifier-regression/stderr.bin"
ACTIVATION_POLICY_REL = "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json"
ALLOWED_REL = "artifacts/dgc-product-v1/trust/allowed_signers"
RUNTIME_DEPS = (
    "cwc/governance/p19_external_verification_contract.py",
    "cwc/governance/p19_external_replay.py",
)
REGRESSION_TESTS = (
    "tests/test_dgc_p19_external_verification_plan.py",
    "tests/test_dgc_p19_external_verifier_activation.py",
    "tests/test_dgc_p19_external_replay.py",
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", message], check=True)
    return _git(root, "rev-parse", "HEAD")


def _write(root: Path, rel: str, data: bytes | str = b"x\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)
    return path


def _fixture(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.org"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "DGC Test"], check=True)

    _write(root, "cwc/governance/method.py", "METHOD='frozen'\n")
    _write(root, "scripts/dgc_external_p19_verifier.py", "print('verify')\n")
    for rel in RUNTIME_DEPS:
        _write(root, rel, f"# runtime {rel}\n")
    for rel in REGRESSION_TESTS:
        _write(root, rel, f"# regression {rel}\n")
    _write(root, PLAN_REL, "{}\n")
    _write(root, ACTIVATION_REL, "{}\n")
    _write(root, REGRESSION_RECEIPT_REL, "{}\n")
    _write(root, REGRESSION_STDOUT_REL, "regression PASS\n")
    _write(root, REGRESSION_STDERR_REL, b"")
    _write(root, ACTIVATION_POLICY_REL, "{}\n")
    allowed = _write(
        root,
        ALLOWED_REL,
        "verifier-a ssh-ed25519 QUFB\nverifier-b ssh-ed25519 QkJC\n",
    )
    activation_attestations = []
    activation_signatures = []
    for principal in ("verifier-a", "verifier-b"):
        activation_attestations.append(
            _write(root, f"artifacts/dgc-product-v1/verifier-regression/{principal}.json", "{}\n")
        )
        activation_signatures.append(
            _write(root, f"artifacts/dgc-product-v1/verifier-regression/{principal}.sig", "signature\n")
        )
    _write(root, "artifacts/dgc-product-v1/replay/source-registry.json", "{}\n")
    _write(root, "artifacts/dgc-product-v1/external_source_authority.json", "{}\n")
    _write(root, "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json", "{}\n")
    execution_commit = _commit(root, "freeze execution and verifier activation surface")
    execution_tree = _git(root, "rev-parse", "HEAD^{tree}")

    _write(root, "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json", '{"active":true}\n')
    for family in ("swe", "terminal"):
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/p19.json", "{}\n")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/attestation.json", "{}\n")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/report.json", "{}\n")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/signature", "sig\n")
        _write(root, f"artifacts/dgc-product-v1/generated/raw/{family}/result.json", "{}\n")
        base = f"artifacts/dgc-product-v1/generated/{family}/verify"
        _write(root, f"{base}/receipt.json", "{}\n")
        _write(root, f"{base}/stdout.bin", "PASS\n")
        _write(root, f"{base}/stderr.bin", b"")
        _write(root, f"{base}/evidence.json", "{}\n")
    _write(root, "artifacts/dgc-product-v1/generated/ledger.json", "{}\n")
    _write(root, "artifacts/dgc-product-v1/generated/global-v5.json", "{}\n")
    packaging_commit = _commit(root, "append evidence package")
    packaging_tree = _git(root, "rev-parse", "HEAD^{tree}")

    pointer_doc = {
        "family_p19_paths": [
            "artifacts/dgc-product-v1/generated/swe/p19.json",
            "artifacts/dgc-product-v1/generated/terminal/p19.json",
        ],
        "family_attestation_paths": [
            "artifacts/dgc-product-v1/generated/swe/attestation.json",
            "artifacts/dgc-product-v1/generated/terminal/attestation.json",
        ],
        "family_verification_report_paths": [
            "artifacts/dgc-product-v1/generated/swe/report.json",
            "artifacts/dgc-product-v1/generated/terminal/report.json",
        ],
        "family_signature_paths": [
            "artifacts/dgc-product-v1/generated/swe/signature",
            "artifacts/dgc-product-v1/generated/terminal/signature",
        ],
    }
    qualification = SimpleNamespace(
        generation_id="generation-1",
        repo_commit=execution_commit,
        repo_tree=execution_tree,
        pointer_digest="1" * 64,
        ledger_path="artifacts/dgc-product-v1/generated/ledger.json",
        ledger_sha256="2" * 64,
        global_v5_authority_path="artifacts/dgc-product-v1/generated/global-v5.json",
        global_v5_authority_sha256="3" * 64,
        global_v5_authority_digest="4" * 64,
        source_registry_path="artifacts/dgc-product-v1/external_source_authority.json",
        family_p19_paths=tuple(pointer_doc["family_p19_paths"]),
        p19_verifier_policy_path=ACTIVATION_POLICY_REL,
        ledger_tip_receipt_digest="5" * 64,
    )
    packaging = SimpleNamespace(
        packaging_commit=packaging_commit,
        packaging_tree=packaging_tree,
        authority_digest="6" * 64,
    )
    activation_doc = {
        "authority_digest": "a" * 64,
        "activation_authorized": True,
        "all_signatures_verified": True,
        "trust_policy_path": ACTIVATION_POLICY_REL,
        "trust_policy_digest": "b" * 64,
        "regression_receipt_path": REGRESSION_RECEIPT_REL,
        "attestation_paths": [path.relative_to(root).as_posix() for path in activation_attestations],
        "signature_paths": [path.relative_to(root).as_posix() for path in activation_signatures],
        "verifier_principals": ["verifier-a", "verifier-b"],
        "signer_key_digests": ["c" * 64, "d" * 64],
    }
    plan = SimpleNamespace(
        verifier_dependencies=tuple({"path": rel} for rel in RUNTIME_DEPS),
        activation_authority_path=ACTIVATION_REL,
        activation_authority_digest="a" * 64,
        activation_regression_receipt_path=REGRESSION_RECEIPT_REL,
        activation_regression_receipt_digest="e" * 64,
    )
    regression = {
        "receipt_digest": "e" * 64,
        "runtime_manifest": [
            {"path": "scripts/dgc_external_p19_verifier.py"},
            *({"path": rel} for rel in RUNTIME_DEPS),
        ],
        "test_manifest": [{"path": rel} for rel in REGRESSION_TESTS],
        "stdout_path": REGRESSION_STDOUT_REL,
        "stderr_path": REGRESSION_STDERR_REL,
    }

    monkeypatch.setattr(qeb, "load_product_qualification_pointer", lambda path: pointer_doc)
    monkeypatch.setattr(qeb, "verify_product_qualification_pointer", lambda **kwargs: qualification)
    monkeypatch.setattr(qeb, "build_evidence_packaging_authority", lambda **kwargs: packaging)
    monkeypatch.setattr(qeb, "load_p19_verifier_trust_policy", lambda path: object())
    monkeypatch.setattr(qeb, "resolve_allowed_signers", lambda policy, repository_root: allowed.resolve())
    monkeypatch.setattr(qeb, "load_p19_external_verification_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        qeb,
        "verify_p19_external_verifier_activation_authority_document",
        lambda *args, **kwargs: activation_doc,
    )
    monkeypatch.setattr(qeb, "verify_p19_external_verifier_regression_receipt", lambda *args, **kwargs: regression)

    def fake_p19(path: Path):
        family = "swe" if "swe" in path.as_posix() else "terminal"
        return {
            "stage_evidence": [{"stage": "SOURCE_VERIFIED", "evidence": {"path": "artifacts/dgc-product-v1/external_source_authority.json"}}],
            "methodology_anchors": [{"path": "cwc/governance/method.py"}],
            "external_replay_inputs": [{"label": "SOURCE_REGISTRY", "path": "artifacts/dgc-product-v1/replay/source-registry.json"}],
            "subject_roots": [{"path": f"artifacts/dgc-product-v1/generated/raw/{family}", "files": [{"path": "result.json"}]}],
        }

    def fake_report(path: Path, *, repository_root: Path):
        family = "swe" if "swe" in path.as_posix() else "terminal"
        base = f"artifacts/dgc-product-v1/generated/{family}/verify"
        return {
            "verification_plan_path": PLAN_REL,
            "verifier_entrypoint_path": "scripts/dgc_external_p19_verifier.py",
            "checks": [{
                "check_id": "REPOSITORY_IDENTITY",
                "receipt_path": f"{base}/receipt.json",
                "stdout_path": f"{base}/stdout.bin",
                "stderr_path": f"{base}/stderr.bin",
                "evidence_path": f"{base}/evidence.json",
            }],
        }

    monkeypatch.setattr(qeb, "verify_family_p19_evidence_root_document", fake_p19)
    monkeypatch.setattr(qeb, "load_p19_verification_report", fake_report)
    return root, qualification, packaging, activation_doc


def test_bundle_v7_contains_dual_signed_activation_and_portable_replay_graph(tmp_path: Path, monkeypatch):
    root, qualification, packaging, _ = _fixture(tmp_path, monkeypatch)
    _, _, authority = build_qualified_evidence_bundle_authority(repository_root=root)
    assert SCHEMA == "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V7"
    assert authority.evidence_graph_complete is True
    assert authority.raw_p19_verification_transcripts_included is True
    assert authority.frozen_verification_plan_and_entrypoint_included is True
    assert authority.frozen_verifier_dependency_closure_included is True
    assert authority.dual_signed_verifier_activation_authority_included is True
    assert authority.activation_regression_evidence_included is True
    assert authority.portable_p19_replay_inputs_included is True
    assert authority.portable_global_v5_authority_included is True
    assert authority.qualified_execution_commit == qualification.repo_commit
    assert authority.packaging_commit == packaging.packaging_commit
    roles = {row.path: row for row in authority.required_files}
    for rel in (
        PLAN_REL,
        ACTIVATION_REL,
        REGRESSION_RECEIPT_REL,
        REGRESSION_STDOUT_REL,
        ACTIVATION_POLICY_REL,
        ALLOWED_REL,
        "cwc/governance/p19_external_verification_contract.py",
        "cwc/governance/p19_external_replay.py",
        "scripts/dgc_external_p19_verifier.py",
    ):
        assert roles[rel].role == ROLE_EXECUTION_SOURCE
    assert roles[REGRESSION_STDERR_REL].bytes == 0
    for principal in ("verifier-a", "verifier-b"):
        assert roles[f"artifacts/dgc-product-v1/verifier-regression/{principal}.json"].role == ROLE_EXECUTION_SOURCE
        assert roles[f"artifacts/dgc-product-v1/verifier-regression/{principal}.sig"].role == ROLE_EXECUTION_SOURCE
    assert roles["artifacts/dgc-product-v1/generated/swe/p19.json"].role == ROLE_PACKAGING_EVIDENCE


def test_untracked_activation_signature_blocks_bundle(tmp_path: Path, monkeypatch):
    root, _, _, activation = _fixture(tmp_path, monkeypatch)
    signature_rel = str(activation["signature_paths"][0])
    subprocess.run(["git", "-C", str(root), "rm", "--cached", "--quiet", signature_rel], check=True)
    assert (root / signature_rel).is_file()
    with pytest.raises(QualifiedEvidenceBundleError, match="not tracked in T_pkg"):
        build_qualified_evidence_bundle_authority(repository_root=root)


def test_untracked_raw_subject_cannot_hide_behind_p19(tmp_path: Path, monkeypatch):
    root, _, _, _ = _fixture(tmp_path, monkeypatch)
    untracked = _write(root, "artifacts/dgc-product-v1/generated/raw/swe/untracked.json", "{}\n")

    def fake_p19(path: Path):
        family = "swe" if "swe" in path.as_posix() else "terminal"
        child = "untracked.json" if family == "swe" else "result.json"
        return {
            "stage_evidence": [],
            "methodology_anchors": [{"path": "cwc/governance/method.py"}],
            "external_replay_inputs": [{"label": "SOURCE_REGISTRY", "path": "artifacts/dgc-product-v1/replay/source-registry.json"}],
            "subject_roots": [{"path": f"artifacts/dgc-product-v1/generated/raw/{family}", "files": [{"path": child}]}],
        }

    monkeypatch.setattr(qeb, "verify_family_p19_evidence_root_document", fake_p19)
    assert untracked.is_file()
    with pytest.raises(QualifiedEvidenceBundleError, match="not tracked in T_pkg"):
        build_qualified_evidence_bundle_authority(repository_root=root)


def test_untracked_verifier_transcript_blocks_bundle(tmp_path: Path, monkeypatch):
    root, _, _, _ = _fixture(tmp_path, monkeypatch)
    untracked = _write(root, "artifacts/dgc-product-v1/generated/swe/verify/untracked.json", "{}\n")

    def fake_report(path: Path, *, repository_root: Path):
        family = "swe" if "swe" in path.as_posix() else "terminal"
        base = f"artifacts/dgc-product-v1/generated/{family}/verify"
        evidence = f"{base}/untracked.json" if family == "swe" else f"{base}/evidence.json"
        return {
            "verification_plan_path": PLAN_REL,
            "verifier_entrypoint_path": "scripts/dgc_external_p19_verifier.py",
            "checks": [{
                "check_id": "REPOSITORY_IDENTITY",
                "receipt_path": f"{base}/receipt.json",
                "stdout_path": f"{base}/stdout.bin",
                "stderr_path": f"{base}/stderr.bin",
                "evidence_path": evidence,
            }],
        }

    monkeypatch.setattr(qeb, "load_p19_verification_report", fake_report)
    assert untracked.is_file()
    with pytest.raises(QualifiedEvidenceBundleError, match="not tracked in T_pkg"):
        build_qualified_evidence_bundle_authority(repository_root=root)


def test_execution_source_anchor_mutation_is_detected(tmp_path: Path, monkeypatch):
    root, _, packaging, _ = _fixture(tmp_path, monkeypatch)
    _write(root, "cwc/governance/method.py", "METHOD='posthoc'\n")
    packaging.packaging_commit = _commit(root, "illegal method mutation")
    packaging.packaging_tree = _git(root, "rev-parse", "HEAD^{tree}")
    with pytest.raises(QualifiedEvidenceBundleError, match="execution-source subject changed"):
        build_qualified_evidence_bundle_authority(repository_root=root)


@pytest.mark.parametrize("bad_path", [
    "artifacts/dgc-product-v1/generated/swe/p19.json\n",
    "artifacts/dgc-product-v1/generated/swe/p19\t.json",
    " artifacts/dgc-product-v1/generated/swe/p19.json",
    "artifacts//dgc-product-v1/generated/swe/p19.json",
    "artifacts\\dgc-product-v1\\generated\\swe\\p19.json",
])
def test_pointer_graph_path_must_be_canonical(tmp_path: Path, monkeypatch, bad_path: str):
    root, _, _, _ = _fixture(tmp_path, monkeypatch)
    original = qeb.load_product_qualification_pointer(Path("unused"))
    pointer_doc = dict(original)
    pointer_doc["family_p19_paths"] = [bad_path, "artifacts/dgc-product-v1/generated/terminal/p19.json"]
    monkeypatch.setattr(qeb, "load_product_qualification_pointer", lambda path: pointer_doc)
    with pytest.raises(QualifiedEvidenceBundleError):
        build_qualified_evidence_bundle_authority(repository_root=root)
