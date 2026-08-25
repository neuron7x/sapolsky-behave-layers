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
    build_qualified_evidence_bundle_authority,
)

PLAN_REL = "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V3.json"
REGRESSION_RECEIPT_REL = "artifacts/dgc-product-v1/verifier-regression/receipt.json"
REGRESSION_STDOUT_REL = "artifacts/dgc-product-v1/verifier-regression/stdout.bin"
REGRESSION_STDERR_REL = "artifacts/dgc-product-v1/verifier-regression/stderr.bin"
REGRESSION_TESTS = (
    "tests/test_dgc_p19_external_verification_plan.py",
    "tests/test_dgc_p19_external_replay.py",
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", message], check=True, stdout=subprocess.PIPE)
    return _git(root, "rev-parse", "HEAD")


def _write(root: Path, rel: str, data: str = "x\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return path


def _fixture(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.org"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "DGC Test"], check=True)

    _write(root, "cwc/governance/method.py", "METHOD = 'frozen'\n")
    _write(root, "cwc/governance/p19_external_verification_contract.py", "CONTRACT = 'frozen'\n")
    _write(root, "cwc/governance/p19_external_replay.py", "ENGINE = 'frozen'\n")
    _write(root, "scripts/dgc_external_p19_verifier.py", "print('verify')\n")
    for rel in REGRESSION_TESTS:
        _write(root, rel, f"# frozen regression test {rel}\n")
    _write(root, PLAN_REL, "{}\n")
    _write(root, REGRESSION_RECEIPT_REL, "{}\n")
    _write(root, REGRESSION_STDOUT_REL, "regression passed\n")
    stderr = root / REGRESSION_STDERR_REL
    stderr.parent.mkdir(parents=True, exist_ok=True)
    stderr.write_bytes(b"")
    _write(root, "artifacts/dgc-product-v1/replay/source-registry.json", "{}\n")
    _write(root, "artifacts/dgc-product-v1/external_source_authority.json", "{}\n")
    _write(root, "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json", "{}\n")
    allowed = _write(
        root,
        "artifacts/dgc-product-v1/trust/allowed_signers",
        "verifier-a ssh-ed25519 AAAAKEYA\nverifier-b ssh-ed25519 AAAAKEYB\n",
    )
    _write(root, "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json", "{}\n")
    execution_commit = _commit(root, "execution source")
    execution_tree = _git(root, "rev-parse", "HEAD^{tree}")

    _write(root, "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json", '{"active":true}\n')
    for family in ("swe", "terminal"):
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/p19.json", "{}\n")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/attestation.json", "{}\n")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/report.json", "{}\n")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/signature", "sig\n")
        _write(root, f"artifacts/dgc-product-v1/generated/raw/{family}/result.json", "{}\n")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/verify/receipt.json", "{}\n")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/verify/stdout.bin", "PASS\n")
        stderr = root / f"artifacts/dgc-product-v1/generated/{family}/verify/stderr.bin"
        stderr.parent.mkdir(parents=True, exist_ok=True)
        stderr.write_bytes(b"")
        _write(root, f"artifacts/dgc-product-v1/generated/{family}/verify/evidence.json", "{}\n")
    _write(root, "artifacts/dgc-product-v1/generated/ledger.json", "{}\n")
    _write(root, "artifacts/dgc-product-v1/generated/global-v5.json", "{}\n")
    packaging_commit = _commit(root, "package evidence")
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
        p19_verifier_policy_path="artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json",
        ledger_tip_receipt_digest="5" * 64,
    )
    packaging = SimpleNamespace(packaging_commit=packaging_commit, packaging_tree=packaging_tree, authority_digest="6" * 64)

    monkeypatch.setattr(qeb, "load_product_qualification_pointer", lambda path: pointer_doc)
    monkeypatch.setattr(qeb, "verify_product_qualification_pointer", lambda **kwargs: qualification)
    monkeypatch.setattr(qeb, "build_evidence_packaging_authority", lambda **kwargs: packaging)
    monkeypatch.setattr(qeb, "load_p19_verifier_trust_policy", lambda path: object())
    monkeypatch.setattr(qeb, "resolve_allowed_signers", lambda policy, repository_root: allowed.resolve())
    monkeypatch.setattr(
        qeb,
        "load_p19_external_verification_plan",
        lambda *args, **kwargs: SimpleNamespace(
            verifier_dependencies=(
                {"path": "cwc/governance/p19_external_verification_contract.py"},
                {"path": "cwc/governance/p19_external_replay.py"},
            ),
            activation_regression_receipt_path=REGRESSION_RECEIPT_REL,
            activation_regression_receipt_digest="d" * 64,
        ),
    )
    monkeypatch.setattr(
        qeb,
        "verify_p19_external_verifier_regression_receipt",
        lambda *args, **kwargs: {
            "receipt_digest": "d" * 64,
            "runtime_manifest": [
                {"path": "scripts/dgc_external_p19_verifier.py"},
                {"path": "cwc/governance/p19_external_verification_contract.py"},
                {"path": "cwc/governance/p19_external_replay.py"},
            ],
            "test_manifest": [{"path": rel} for rel in REGRESSION_TESTS],
            "stdout_path": REGRESSION_STDOUT_REL,
            "stderr_path": REGRESSION_STDERR_REL,
        },
    )

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
    return root, execution_commit, packaging_commit, pointer_doc, qualification, packaging


def test_qualified_bundle_derives_source_packaging_portable_replay_and_verifier_roles(tmp_path: Path, monkeypatch):
    root, _, _, _, _, _ = _fixture(tmp_path, monkeypatch)
    qualification, packaging, authority = build_qualified_evidence_bundle_authority(repository_root=root)
    assert authority.evidence_graph_complete is True
    assert authority.raw_p19_verification_transcripts_included is True
    assert authority.frozen_verification_plan_and_entrypoint_included is True
    assert authority.frozen_verifier_dependency_closure_included is True
    assert authority.activation_regression_evidence_included is True
    assert authority.portable_p19_replay_inputs_included is True
    assert authority.portable_global_v5_authority_included is True
    assert authority.all_required_subjects_git_bound is True
    assert authority.qualified_execution_commit == qualification.repo_commit
    assert authority.packaging_commit == packaging.packaging_commit
    roles = {row.path: row for row in authority.required_files}
    assert roles["cwc/governance/method.py"].role == ROLE_EXECUTION_SOURCE
    assert roles["cwc/governance/p19_external_verification_contract.py"].role == ROLE_EXECUTION_SOURCE
    assert roles["cwc/governance/p19_external_replay.py"].role == ROLE_EXECUTION_SOURCE
    assert roles["scripts/dgc_external_p19_verifier.py"].role == ROLE_EXECUTION_SOURCE
    assert roles[PLAN_REL].role == ROLE_EXECUTION_SOURCE
    assert roles[REGRESSION_RECEIPT_REL].role == ROLE_EXECUTION_SOURCE
    assert roles[REGRESSION_STDOUT_REL].role == ROLE_EXECUTION_SOURCE
    assert roles[REGRESSION_STDERR_REL].bytes == 0
    for rel in REGRESSION_TESTS:
        assert roles[rel].role == ROLE_EXECUTION_SOURCE
    assert roles["artifacts/dgc-product-v1/replay/source-registry.json"].role == ROLE_EXECUTION_SOURCE
    assert roles["artifacts/dgc-product-v1/generated/swe/p19.json"].role == ROLE_PACKAGING_EVIDENCE
    assert roles["artifacts/dgc-product-v1/generated/swe/verify/stderr.bin"].bytes == 0


def test_untracked_raw_subject_cannot_be_hidden_behind_valid_p19_json(tmp_path: Path, monkeypatch):
    root, _, _, _, _, _ = _fixture(tmp_path, monkeypatch)
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


def test_untracked_verifier_transcript_cannot_be_hidden_behind_signed_report(tmp_path: Path, monkeypatch):
    root, _, _, _, _, _ = _fixture(tmp_path, monkeypatch)
    untracked = _write(root, "artifacts/dgc-product-v1/generated/swe/verify/untracked-evidence.json", "{}\n")

    def fake_report(path: Path, *, repository_root: Path):
        family = "swe" if "swe" in path.as_posix() else "terminal"
        base = f"artifacts/dgc-product-v1/generated/{family}/verify"
        evidence = f"{base}/untracked-evidence.json" if family == "swe" else f"{base}/evidence.json"
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


def test_untracked_verifier_dependency_cannot_be_hidden_behind_frozen_plan(tmp_path: Path, monkeypatch):
    root, _, _, _, _, _ = _fixture(tmp_path, monkeypatch)
    dependency = _write(root, "artifacts/dgc-product-v1/generated/untracked-engine.py", "ENGINE=True\n")
    monkeypatch.setattr(
        qeb,
        "load_p19_external_verification_plan",
        lambda *args, **kwargs: SimpleNamespace(
            verifier_dependencies=({"path": "artifacts/dgc-product-v1/generated/untracked-engine.py"},),
            activation_regression_receipt_path=REGRESSION_RECEIPT_REL,
            activation_regression_receipt_digest="d" * 64,
        ),
    )
    assert dependency.is_file()
    with pytest.raises(QualifiedEvidenceBundleError, match="not tracked in T_pkg"):
        build_qualified_evidence_bundle_authority(repository_root=root)


def test_untracked_regression_subject_cannot_be_hidden_behind_active_plan(tmp_path: Path, monkeypatch):
    root, _, _, _, _, _ = _fixture(tmp_path, monkeypatch)
    untracked = _write(root, "artifacts/dgc-product-v1/generated/untracked-regression-test.py", "assert True\n")
    monkeypatch.setattr(
        qeb,
        "verify_p19_external_verifier_regression_receipt",
        lambda *args, **kwargs: {
            "receipt_digest": "d" * 64,
            "runtime_manifest": [{"path": "scripts/dgc_external_p19_verifier.py"}],
            "test_manifest": [{"path": "artifacts/dgc-product-v1/generated/untracked-regression-test.py"}],
            "stdout_path": REGRESSION_STDOUT_REL,
            "stderr_path": REGRESSION_STDERR_REL,
        },
    )
    assert untracked.is_file()
    with pytest.raises(QualifiedEvidenceBundleError, match="not tracked in T_pkg"):
        build_qualified_evidence_bundle_authority(repository_root=root)


def test_execution_source_anchor_mutation_is_detected_even_if_packaging_layer_is_mocked_green(tmp_path: Path, monkeypatch):
    root, _, _, _, _, packaging = _fixture(tmp_path, monkeypatch)
    _write(root, "cwc/governance/method.py", "METHOD = 'posthoc'\n")
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
def test_pointer_graph_path_must_be_canonical_and_unambiguous(tmp_path: Path, monkeypatch, bad_path: str):
    root, _, _, pointer_doc, _, _ = _fixture(tmp_path, monkeypatch)
    pointer_doc["family_p19_paths"] = [bad_path, "artifacts/dgc-product-v1/generated/terminal/p19.json"]
    with pytest.raises(QualifiedEvidenceBundleError):
        build_qualified_evidence_bundle_authority(repository_root=root)
