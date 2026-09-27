from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

import cwc.governance.external_evidence_reference as reference_module
from cwc.governance.external_evidence_reference import ExternalEvidenceError, verify_materialization_generation
from cwc.governance.external_materialization import SweParquetVerification, canonical_sha256, parse_terminal_dataset_manifest
from cwc.governance.external_source_authority import ExternalSourceAuthority, ExternalSourceStage, promote_materialized_verified
from cwc.governance.git_tree_reconstruction import git_blob_oid_path, reconstruct_git_tree
from cwc.governance.materialization_transaction import AtomicEvidenceGeneration, sha256_file
from cwc.governance.workload_seal import seal_materialized_workload

COMMIT = "a" * 40
TREE = "b" * 40
MATERIALIZER = "d" * 64
SWE_IDS = ("swe-1", "swe-2")
TB_TASKS = ("task-a", "task-b")


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _source_row(*, family_id: str, upstream_revision: str, identity: dict, method: str) -> dict:
    authority = ExternalSourceAuthority(
        family_id=family_id,
        stage=ExternalSourceStage.SOURCE_VERIFIED,
        upstream_revision=upstream_revision,
        upstream_identity_digest=_h(f"identity:{family_id}"),
        source_verification_method=method,
        source_verification_evidence_digest=_h(f"verification:{family_id}"),
    )
    return {
        "family_id": family_id,
        "stage": "SOURCE_VERIFIED",
        "upstream_revision": upstream_revision,
        "identity": identity,
        "upstream_identity_digest": authority.upstream_identity_digest,
        "verification": {"verification_method": method},
        "source_verification_evidence_digest": authority.source_verification_evidence_digest,
        "authority_digest": authority.digest,
    }


def _make_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "generation"
    registry_path = tmp_path / "external_source_authority.json"

    with AtomicEvidenceGeneration(root) as tx:
        assert tx.staging_root is not None
        swe_root = tx.staging_root / "SWE_BENCH_VERIFIED"
        parquet = swe_root / "data" / "test-00000-of-00001.parquet"
        parquet.parent.mkdir(parents=True)
        parquet.write_bytes(b"synthetic-parquet-bytes")
        parquet_sha = sha256_file(parquet)
        swe_manifest = canonical_sha256(tuple(sorted(SWE_IDS)))
        swe_verified = SweParquetVerification(
            bytes_size=parquet.stat().st_size,
            sha256=parquet_sha,
            row_count=len(SWE_IDS),
            instance_ids=tuple(sorted(SWE_IDS)),
            task_manifest_sha256=swe_manifest,
        )
        monkeypatch.setattr(reference_module, "verify_swe_parquet", lambda *args, **kwargs: swe_verified)
        swe_seal = seal_materialized_workload(
            family_id="SWE_BENCH_VERIFIED",
            root=swe_root,
            task_ids=SWE_IDS,
            expected_task_count=len(SWE_IDS),
        )

        tb_repo = tx.staging_root / "TERMINAL_BENCH_2_1" / "repo"
        tasks_root = tb_repo / "tasks"
        tasks_root.mkdir(parents=True)
        dataset = tasks_root / "dataset.toml"
        dataset.write_text(
            "[dataset]\nname='synthetic-terminal'\n"
            "[[tasks]]\nname='task-a'\ndigest='sha256:" + "1" * 64 + "'\n"
            "[[tasks]]\nname='task-b'\ndigest='sha256:" + "2" * 64 + "'\n",
            encoding="utf-8",
        )
        (tasks_root / "task-a.txt").write_text("a", encoding="utf-8")
        (tasks_root / "task-b.txt").write_text("b", encoding="utf-8")
        (tb_repo / "README.md").write_text("terminal", encoding="utf-8")
        tb_manifest = parse_terminal_dataset_manifest(dataset.read_text(), expected_count=len(TB_TASKS))
        tb_seal = seal_materialized_workload(
            family_id="TERMINAL_BENCH_2_1",
            root=tasks_root,
            task_ids=TB_TASKS,
            expected_task_count=len(TB_TASKS),
        )
        repo_tree = reconstruct_git_tree(tb_repo).root_tree_oid
        tasks_tree = reconstruct_git_tree(tasks_root).root_tree_oid
        dataset_blob = git_blob_oid_path(dataset)
        upstream_commit = "7" * 40

        swe_row = _source_row(
            family_id="SWE_BENCH_VERIFIED",
            upstream_revision="rev-swe",
            identity={
                "family_id": "SWE_BENCH_VERIFIED",
                "revision": "rev-swe",
                "parquet_path": "data/test-00000-of-00001.parquet",
                "parquet_sha256": parquet_sha,
                "expected_task_count": len(SWE_IDS),
            },
            method="TEST_SWE_AUTHORITY",
        )
        tb_row = _source_row(
            family_id="TERMINAL_BENCH_2_1",
            upstream_revision=upstream_commit,
            identity={
                "family_id": "TERMINAL_BENCH_2_1",
                "commit": upstream_commit,
                "tree": repo_tree,
                "tasks_tree": tasks_tree,
                "dataset_manifest_blob": dataset_blob,
                "expected_task_count": len(TB_TASKS),
            },
            method="TEST_GIT_OBJECT_CHAIN",
        )
        registry = {
            "schema": "DGC_EXTERNAL_SOURCE_AUTHORITY_REGISTRY_V1",
            "families": [swe_row, tb_row],
            "product_promotion_authorized": False,
        }
        registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        registry_sha = sha256_file(registry_path)

        source_swe = reference_module._source_authority(swe_row)
        source_tb = reference_module._source_authority(tb_row)
        mat_swe = promote_materialized_verified(
            source_swe,
            materialized_tree_sha256=swe_seal.file_tree_sha256,
            materialized_task_manifest_sha256=swe_seal.task_manifest_sha256,
        )
        mat_tb = promote_materialized_verified(
            source_tb,
            materialized_tree_sha256=tb_seal.file_tree_sha256,
            materialized_task_manifest_sha256=tb_seal.task_manifest_sha256,
        )
        receipt = {
            "schema": "DGC_EXTERNAL_MATERIALIZATION_RECEIPT_V2",
            "families": [
                {
                    "family_id": "SWE_BENCH_VERIFIED",
                    "stage": "MATERIALIZED_VERIFIED",
                    "source_authority_digest": source_swe.digest,
                    "authority_digest": mat_swe.digest,
                    "parquet": {
                        "bytes_size": swe_verified.bytes_size,
                        "sha256": swe_verified.sha256,
                        "row_count": swe_verified.row_count,
                        "instance_id_manifest_sha256": swe_verified.task_manifest_sha256,
                    },
                    "workload_seal": asdict(swe_seal),
                },
                {
                    "family_id": "TERMINAL_BENCH_2_1",
                    "stage": "MATERIALIZED_VERIFIED",
                    "source_authority_digest": source_tb.digest,
                    "authority_digest": mat_tb.digest,
                    "git_identity": {
                        "commit": upstream_commit,
                        "repository_tree": repo_tree,
                        "tasks_tree": tasks_tree,
                        "dataset_manifest_blob": dataset_blob,
                    },
                    "dataset_manifest": {
                        "dataset_name": tb_manifest.dataset_name,
                        "task_count": tb_manifest.task_count,
                        "task_name_digest_manifest_sha256": tb_manifest.canonical_task_digest,
                    },
                    "workload_seal": asdict(tb_seal),
                },
            ],
            "source_registry_sha256": registry_sha,
            "repository_commit": COMMIT,
            "repository_tree": TREE,
            "materializer_sha256": MATERIALIZER,
            "execution_authorized": False,
            "product_promotion_authorized": False,
        }
        provenance = {
            "schema": "DGC_MATERIALIZATION_PROVENANCE_V1",
            "claim": "VERIFIED_MATERIALIZATION_ONLY",
            "repository": {"git_commit": COMMIT, "git_tree": TREE},
            "materials": {
                "external_source_registry_sha256": registry_sha,
                "materializer_sha256": MATERIALIZER,
                "source_authority_digests": sorted([source_swe.digest, source_tb.digest]),
            },
            "slsa_conformance_claim": False,
            "execution_authorized": False,
            "product_promotion_authorized": False,
        }
        tx.publish(receipt=receipt, provenance=provenance)
    return root, registry_path


def _verify(root: Path, registry: Path):
    return verify_materialization_generation(
        root,
        expected_repository_commit=COMMIT,
        expected_repository_tree=TREE,
        source_registry_path=registry,
    )


def test_valid_generation_reconstructs_payload_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, registry = _make_generation(tmp_path, monkeypatch)
    reference = _verify(root, registry)
    assert reference.repository_commit == COMMIT
    assert [binding.family_id for binding in reference.family_bindings] == ["SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"]
    for binding in reference.family_bindings:
        assert binding.materialized_tree_sha256
        assert binding.materialized_task_manifest_sha256
        assert binding.source_authority_digest != binding.materialized_authority_digest
        assert len(binding.semantic_verification_digest) == 64
    assert reference.binding("SWE_BENCH_VERIFIED").expected_task_count == len(SWE_IDS)
    assert reference.binding("TERMINAL_BENCH_2_1").expected_task_count == len(TB_TASKS)


def test_swe_payload_is_semantically_reverified_on_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, registry = _make_generation(tmp_path, monkeypatch)
    called = {"count": 0}
    original = reference_module.verify_swe_parquet

    def observed(*args, **kwargs):
        called["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(reference_module, "verify_swe_parquet", observed)
    _verify(root, registry)
    assert called["count"] == 1


def test_terminal_bytes_are_reconstructed_without_git_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, registry = _make_generation(tmp_path, monkeypatch)
    assert not (root / "TERMINAL_BENCH_2_1" / "repo" / ".git").exists()
    _verify(root, registry)


def test_terminal_payload_tamper_is_rejected_even_if_control_files_are_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, registry = _make_generation(tmp_path, monkeypatch)
    (root / "TERMINAL_BENCH_2_1" / "repo" / "README.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(ExternalEvidenceError, match="publication file manifest mismatch"):
        _verify(root, registry)


def test_wrong_canonical_registry_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, registry = _make_generation(tmp_path, monkeypatch)
    data = json.loads(registry.read_text())
    data["families"][0]["upstream_revision"] = "forged"
    registry.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ExternalEvidenceError, match="not produced from the supplied canonical source registry"):
        _verify(root, registry)


def test_wrong_repository_identity_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, registry = _make_generation(tmp_path, monkeypatch)
    with pytest.raises(ExternalEvidenceError, match="repository identity mismatch"):
        verify_materialization_generation(
            root,
            expected_repository_commit="1" * 40,
            expected_repository_tree=TREE,
            source_registry_path=registry,
        )


def test_generation_root_symlink_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, registry = _make_generation(tmp_path, monkeypatch)
    link = tmp_path / "generation-link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ExternalEvidenceError, match="symlink"):
        _verify(link, registry)
