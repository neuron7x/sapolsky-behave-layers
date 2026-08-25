from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import cwc.governance.materialization_closure as closure_module
from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.external_evidence_reference import (
    ExternalEvidenceError,
    ExternalEvidenceReference,
    FamilyMaterializationBinding,
)
from cwc.governance.materialization_closure import close_materialized_verified

COMMIT = "a" * 40
TREE = "b" * 40


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_repo(repo: Path) -> tuple[str, str]:
    registry = repo / "artifacts/dgc-product-v1/external_source_authority.json"
    materializer = repo / "scripts/dgc_materialize_external_sources.py"
    registry.parent.mkdir(parents=True, exist_ok=True)
    materializer.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("canonical-registry", encoding="utf-8")
    materializer.write_text("canonical-materializer", encoding="utf-8")
    return _sha(registry), _sha(materializer)


def _reference(*, registry_sha: str, materializer_sha: str) -> ExternalEvidenceReference:
    bindings = tuple(
        FamilyMaterializationBinding(
            family_id=family,
            source_authority_digest=hashlib.sha256((family + ":source").encode()).hexdigest(),
            materialized_authority_digest=hashlib.sha256((family + ":materialized").encode()).hexdigest(),
            materialized_tree_sha256=hashlib.sha256((family + ":tree").encode()).hexdigest(),
            materialized_task_manifest_sha256=hashlib.sha256((family + ":tasks").encode()).hexdigest(),
            expected_task_count=1,
            semantic_verification_digest=hashlib.sha256((family + ":semantic").encode()).hexdigest(),
        )
        for family in ("SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1")
    )
    return ExternalEvidenceReference(
        subject_type="DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2",
        publication_manifest_sha256="1" * 64,
        payload_manifest_sha256="2" * 64,
        materialization_receipt_sha256="3" * 64,
        materialization_provenance_sha256="4" * 64,
        source_registry_sha256=registry_sha,
        materializer_sha256=materializer_sha,
        repository_commit=COMMIT,
        repository_tree=TREE,
        family_bindings=bindings,
        file_count=4,
    )


def _ledger(repo: Path) -> EvidenceClosureLedger:
    ledger = EvidenceClosureLedger(
        repository_root=repo,
        ledger_path=repo / "eval_bundle" / "ledger.json",
        generation_id="g1",
        repo_commit=COMMIT,
        repo_tree=TREE,
    )
    source = repo / "source.json"
    source.write_text("source", encoding="utf-8")
    ledger.advance(
        StageExecution(
            stage="SOURCE_VERIFIED",
            commands=(),
            evidence=(EvidenceArtifact(path="source.json", sha256=sha256_file(source)),),
        )
    )
    return ledger


def test_materialized_closure_binds_verified_external_subject_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    registry_sha, materializer_sha = _prepare_repo(repo)
    ledger = _ledger(repo)
    reference = _reference(registry_sha=registry_sha, materializer_sha=materializer_sha)
    monkeypatch.setattr(closure_module, "verify_materialization_generation", lambda *args, **kwargs: reference)

    receipt = close_materialized_verified(
        ledger,
        generation_root=tmp_path / "external-generation",
        reference_path=repo / "eval_bundle" / "materialization-reference.json",
        identity_checker=lambda _: None,
    )
    assert receipt["stage"] == "MATERIALIZED_VERIFIED"
    assert ledger.next_stage() == "EXECUTION_MANIFESTS_FROZEN"
    payload = json.loads((repo / "eval_bundle" / "materialization-reference.json").read_text())
    assert payload["schema"] == "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2"
    assert payload["repository_commit"] == COMMIT
    assert len(payload["family_bindings"]) == 2
    assert receipt["evidence"][0]["path"] == "eval_bundle/materialization-reference.json"


def test_verifier_failure_cannot_promote_materialized_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _prepare_repo(repo)
    ledger = _ledger(repo)

    def fail(*args, **kwargs):
        raise ExternalEvidenceError("payload authority reconstruction failed")

    monkeypatch.setattr(closure_module, "verify_materialization_generation", fail)
    with pytest.raises(ExternalEvidenceError, match="reconstruction failed"):
        close_materialized_verified(
            ledger,
            generation_root=tmp_path / "external-generation",
            reference_path=repo / "eval_bundle" / "materialization-reference.json",
            identity_checker=lambda _: None,
        )
    assert ledger.next_stage() == "MATERIALIZED_VERIFIED"
    assert not (repo / "eval_bundle" / "materialization-reference.json").exists()


def test_materialized_closure_rejects_reference_outside_runtime_root(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _prepare_repo(repo)
    ledger = _ledger(repo)
    with pytest.raises(ClosureError, match="eval_bundle"):
        close_materialized_verified(
            ledger,
            generation_root=tmp_path / "external-generation",
            reference_path=repo / "artifacts" / "reference.json",
            identity_checker=lambda _: None,
        )


def test_conflicting_preexisting_reference_cannot_be_substituted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    registry_sha, materializer_sha = _prepare_repo(repo)
    ledger = _ledger(repo)
    monkeypatch.setattr(
        closure_module,
        "verify_materialization_generation",
        lambda *args, **kwargs: _reference(registry_sha=registry_sha, materializer_sha=materializer_sha),
    )
    target = repo / "eval_bundle" / "materialization-reference.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("forged", encoding="utf-8")
    with pytest.raises(ClosureError, match="conflicts"):
        close_materialized_verified(
            ledger,
            generation_root=tmp_path / "external-generation",
            reference_path=target,
            identity_checker=lambda _: None,
        )
    assert ledger.next_stage() == "MATERIALIZED_VERIFIED"


def test_verified_reference_with_wrong_registry_digest_is_rejected_by_closure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo-registry"
    repo.mkdir()
    _, materializer_sha = _prepare_repo(repo)
    ledger = _ledger(repo)
    monkeypatch.setattr(
        closure_module,
        "verify_materialization_generation",
        lambda *args, **kwargs: _reference(registry_sha="9" * 64, materializer_sha=materializer_sha),
    )
    with pytest.raises(ClosureError, match="source registry"):
        close_materialized_verified(
            ledger, generation_root=tmp_path / "external-generation",
            reference_path=repo / "eval_bundle" / "reference.json", identity_checker=lambda _: None
        )
    assert ledger.next_stage() == "MATERIALIZED_VERIFIED"


def test_verified_reference_with_wrong_materializer_digest_is_rejected_by_closure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo-materializer"
    repo.mkdir()
    registry_sha, _ = _prepare_repo(repo)
    ledger = _ledger(repo)
    monkeypatch.setattr(
        closure_module,
        "verify_materialization_generation",
        lambda *args, **kwargs: _reference(registry_sha=registry_sha, materializer_sha="8" * 64),
    )
    with pytest.raises(ClosureError, match="materializer"):
        close_materialized_verified(
            ledger, generation_root=tmp_path / "external-generation",
            reference_path=repo / "eval_bundle" / "reference.json", identity_checker=lambda _: None
        )
    assert ledger.next_stage() == "MATERIALIZED_VERIFIED"
