from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from cwc.governance.evidence_closure import ClosureError, EvidenceClosureLedger
from cwc.governance.materialization_closure import close_materialized_verified
from cwc.governance.materialization_transaction import AtomicEvidenceGeneration

COMMIT = "a" * 40
TREE = "b" * 40
SOURCE_SWE = "1" * 64
SOURCE_TB = "2" * 64
MAT_SWE = "3" * 64
MAT_TB = "4" * 64


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_repo(repo: Path) -> tuple[str, str]:
    registry = repo / "artifacts/dgc-product-v1/external_source_authority.json"
    materializer = repo / "scripts/dgc_materialize_external_sources.py"
    registry.parent.mkdir(parents=True, exist_ok=True)
    materializer.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("canonical-registry")
    materializer.write_text("canonical-materializer")
    return _sha(registry), _sha(materializer)


def _generation(tmp_path: Path, *, registry_sha: str, materializer_sha: str) -> Path:
    root = tmp_path / "external-generation"
    with AtomicEvidenceGeneration(root) as tx:
        assert tx.staging_root is not None
        (tx.staging_root / "SWE_BENCH_VERIFIED").mkdir()
        (tx.staging_root / "SWE_BENCH_VERIFIED" / "x").write_text("swe")
        (tx.staging_root / "TERMINAL_BENCH_2_1").mkdir()
        (tx.staging_root / "TERMINAL_BENCH_2_1" / "x").write_text("tb")
        tx.publish(
            receipt={
                "schema": "DGC_EXTERNAL_MATERIALIZATION_RECEIPT_V2",
                "families": [
                    {"family_id": "SWE_BENCH_VERIFIED", "stage": "MATERIALIZED_VERIFIED", "source_authority_digest": SOURCE_SWE, "authority_digest": MAT_SWE},
                    {"family_id": "TERMINAL_BENCH_2_1", "stage": "MATERIALIZED_VERIFIED", "source_authority_digest": SOURCE_TB, "authority_digest": MAT_TB},
                ],
                "source_registry_sha256": registry_sha,
                "repository_commit": COMMIT,
                "repository_tree": TREE,
                "materializer_sha256": materializer_sha,
                "execution_authorized": False,
                "product_promotion_authorized": False,
            },
            provenance={
                "schema": "DGC_MATERIALIZATION_PROVENANCE_V1",
                "claim": "VERIFIED_MATERIALIZATION_ONLY",
                "repository": {"git_commit": COMMIT, "git_tree": TREE},
                "materials": {
                    "external_source_registry_sha256": registry_sha,
                    "materializer_sha256": materializer_sha,
                    "source_authority_digests": [SOURCE_SWE, SOURCE_TB],
                },
                "slsa_conformance_claim": False,
                "execution_authorized": False,
                "product_promotion_authorized": False,
            },
        )
    return root


def _ledger(repo: Path) -> EvidenceClosureLedger:
    ledger = EvidenceClosureLedger(
        repository_root=repo,
        ledger_path=repo / "eval_bundle" / "ledger.json",
        generation_id="g1",
        repo_commit=COMMIT,
        repo_tree=TREE,
    )
    # Seed a valid SOURCE_VERIFIED receipt using the public advance contract.
    source = repo / "source.json"
    source.write_text("source")
    from cwc.governance.evidence_closure import EvidenceArtifact, StageExecution, sha256_file
    ledger.advance(StageExecution(stage="SOURCE_VERIFIED", commands=(), evidence=(EvidenceArtifact(path="source.json", sha256=sha256_file(source)),)))
    return ledger


def test_materialized_closure_verifies_external_subject_and_binds_small_reference(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    registry_sha, materializer_sha = _prepare_repo(repo)
    generation = _generation(tmp_path, registry_sha=registry_sha, materializer_sha=materializer_sha)
    ledger = _ledger(repo)
    receipt = close_materialized_verified(
        ledger,
        generation_root=generation,
        reference_path=repo / "eval_bundle" / "materialization-reference.json",
        identity_checker=lambda _: None,
    )
    assert receipt["stage"] == "MATERIALIZED_VERIFIED"
    assert ledger.next_stage() == "HARNESS_FROZEN"
    reference = repo / "eval_bundle" / "materialization-reference.json"
    payload = json.loads(reference.read_text())
    assert payload["schema"] == "DGC_EXTERNAL_EVIDENCE_REFERENCE_V1"
    assert payload["repository_commit"] == COMMIT
    assert payload["reference_digest"]
    assert receipt["evidence"][0]["path"] == "eval_bundle/materialization-reference.json"


def test_materialized_closure_rejects_external_tamper_without_promotion(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    registry_sha, materializer_sha = _prepare_repo(repo)
    generation = _generation(tmp_path, registry_sha=registry_sha, materializer_sha=materializer_sha)
    (generation / "SWE_BENCH_VERIFIED" / "x").write_text("tampered")
    ledger = _ledger(repo)
    with pytest.raises(RuntimeError, match="manifest mismatch"):
        close_materialized_verified(
            ledger,
            generation_root=generation,
            reference_path=repo / "eval_bundle" / "materialization-reference.json",
            identity_checker=lambda _: None,
        )
    assert ledger.next_stage() == "MATERIALIZED_VERIFIED"
    assert not (repo / "eval_bundle" / "materialization-reference.json").exists()


def test_materialized_closure_rejects_reference_outside_runtime_root(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    registry_sha, materializer_sha = _prepare_repo(repo)
    ledger = _ledger(repo)
    with pytest.raises(ClosureError, match="eval_bundle"):
        close_materialized_verified(
            ledger,
            generation_root=_generation(tmp_path, registry_sha=registry_sha, materializer_sha=materializer_sha),
            reference_path=repo / "artifacts" / "reference.json",
            identity_checker=lambda _: None,
        )


def test_conflicting_preexisting_reference_cannot_be_substituted(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    registry_sha, materializer_sha = _prepare_repo(repo)
    ledger = _ledger(repo)
    target = repo / "eval_bundle" / "materialization-reference.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("forged")
    with pytest.raises(ClosureError, match="conflicts"):
        close_materialized_verified(ledger, generation_root=_generation(tmp_path, registry_sha=registry_sha, materializer_sha=materializer_sha), reference_path=target, identity_checker=lambda _: None)
    assert ledger.next_stage() == "MATERIALIZED_VERIFIED"


def test_self_consistent_generation_with_wrong_registry_is_rejected_by_closure(tmp_path: Path):
    repo = tmp_path / "repo-registry"
    repo.mkdir()
    registry_sha, materializer_sha = _prepare_repo(repo)
    ledger = _ledger(repo)
    generation = _generation(tmp_path / "g-registry", registry_sha="9" * 64, materializer_sha=materializer_sha)
    with pytest.raises(ClosureError, match="source registry"):
        close_materialized_verified(
            ledger, generation_root=generation, reference_path=repo / "eval_bundle" / "reference.json", identity_checker=lambda _: None
        )
    assert ledger.next_stage() == "MATERIALIZED_VERIFIED"


def test_self_consistent_generation_with_wrong_materializer_is_rejected_by_closure(tmp_path: Path):
    repo = tmp_path / "repo-materializer"
    repo.mkdir()
    registry_sha, materializer_sha = _prepare_repo(repo)
    ledger = _ledger(repo)
    generation = _generation(tmp_path / "g-materializer", registry_sha=registry_sha, materializer_sha="8" * 64)
    with pytest.raises(ClosureError, match="materializer"):
        close_materialized_verified(
            ledger, generation_root=generation, reference_path=repo / "eval_bundle" / "reference.json", identity_checker=lambda _: None
        )
    assert ledger.next_stage() == "MATERIALIZED_VERIFIED"
