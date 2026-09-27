from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import cwc.governance.p19_external_replay as replay
from cwc.governance.generalization_registry import REQUIRED_AXES
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS


def test_external_replay_surface_is_exactly_the_eight_frozen_checks():
    assert set(replay.CHECK_HANDLERS) == REQUIRED_CHECKS
    assert set(replay.CHECK_METHOD_IDS) == REQUIRED_CHECKS
    assert all(replay.CHECK_METHOD_IDS[check].startswith("DGC_P19_EXTERNAL_") for check in REQUIRED_CHECKS)


def test_run_external_check_dispatches_and_binds_evidence_digest(tmp_path: Path, monkeypatch):
    p19_file = tmp_path / "p19.json"
    p19_file.write_text("{}\n", encoding="utf-8")
    p19 = {
        "family_id": "FAMILY",
        "p19_digest": "a" * 64,
        "repository_commit": "b" * 40,
        "repository_tree": "c" * 40,
    }
    monkeypatch.setattr(replay, "_load_p19", lambda root, path: (p19_file, p19))
    monkeypatch.setitem(replay.CHECK_HANDLERS, "REPOSITORY_IDENTITY", lambda root, doc: {"verified": True})
    evidence = replay.run_external_p19_check(
        repository_root=tmp_path,
        p19_path=p19_file,
        check_id="REPOSITORY_IDENTITY",
    )
    assert evidence["result"] == "PASS"
    assert evidence["product_qualification_authorized"] is False
    payload = {key: value for key, value in evidence.items() if key not in {"schema", "evidence_digest"}}
    assert evidence["evidence_digest"] == sha256_bytes(canonical_json_bytes(payload))


def test_repository_identity_requires_exact_tree_and_ancestor(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.org"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "DGC Test"], check=True)
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "t0"], check=True)
    commit = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD^{tree}"], text=True).strip()
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "b.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "t1"], check=True)
    result = replay.replay_repository_identity(tmp_path, {"repository_commit": commit, "repository_tree": tree})
    assert result["ancestor_relation_verified"] is True
    with pytest.raises(replay.P19ExternalReplayError, match="tree differs"):
        replay.replay_repository_identity(tmp_path, {"repository_commit": commit, "repository_tree": "0" * 40})


def test_replay_locator_rehashes_exact_file_bytes(tmp_path: Path):
    subject = tmp_path / "evidence/component.json"
    subject.parent.mkdir(parents=True)
    subject.write_text("{}\n", encoding="utf-8")
    p19 = {
        "external_replay_inputs": [{
            "label": "SOURCE_REGISTRY",
            "path": "evidence/component.json",
            "sha256": sha256_file(subject),
            "bytes": subject.stat().st_size,
        }]
    }
    assert replay._replay_file(tmp_path, p19, "SOURCE_REGISTRY") == subject.resolve()
    subject.write_text('{"mutated":true}\n', encoding="utf-8")
    with pytest.raises(replay.P19ExternalReplayError, match="changed after P19 seal"):
        replay._replay_file(tmp_path, p19, "SOURCE_REGISTRY")


def test_subject_root_rehash_rejects_population_mutation(tmp_path: Path):
    root = tmp_path / "raw"
    root.mkdir()
    (root / "one.json").write_text("{}\n", encoding="utf-8")
    manifest = file_manifest(root)
    p19 = {
        "subject_roots": [{
            "label": "PRIMARY_EXECUTION",
            "path": "raw",
            "file_count": len(manifest),
            "total_bytes": sum(int(row[3]) for row in manifest),
            "manifest_sha256": sha256_bytes(canonical_json_bytes(manifest)),
            "files": [
                {"path": p, "type": kind, "mode": mode, "bytes": size, "sha256": digest}
                for p, kind, mode, size, digest in manifest
            ],
        }]
    }
    replay._subject_root(tmp_path, p19, "PRIMARY_EXECUTION")
    (root / "two.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(replay.P19ExternalReplayError, match="file population changed"):
        replay._subject_root(tmp_path, p19, "PRIMARY_EXECUTION")


def _patch_path_resolvers(monkeypatch):
    monkeypatch.setattr(replay, "_stage_path", lambda root, p19, stage: Path(stage))
    monkeypatch.setattr(replay, "_replay_file", lambda root, p19, label: Path(label))
    monkeypatch.setattr(replay, "_subject_root", lambda root, p19, label, **kwargs: Path(label))


def test_primary_p9_raw_replay_delegates_to_canonical_builders(tmp_path: Path, monkeypatch):
    _patch_path_resolvers(monkeypatch)
    p19 = {
        "primary_anytime_p9_authority_digest": "anytime",
        "primary_ccf_oracle_audit_authority_digest": "ccf",
        "primary_p9_scientific_authority_digest": "scientific",
    }
    monkeypatch.setattr(replay, "verify_p9_scientific_authority_v3_document", lambda path: {"authority_digest": "scientific"})
    monkeypatch.setattr(replay, "build_anytime_p9_authority", lambda **kwargs: SimpleNamespace(authority_digest="anytime", p9_supported_without_iid_assumption=True))
    monkeypatch.setattr(replay, "build_ccf_oracle_audit_authority", lambda **kwargs: SimpleNamespace(authority_digest="ccf", headroom_audit_complete=True))
    monkeypatch.setattr(replay, "build_p9_scientific_authority_v3", lambda **kwargs: SimpleNamespace(authority_digest="scientific", scientific_p9_supported=True))
    result = replay.replay_primary_p9(tmp_path, p19)
    assert result["scientific_p9_authority_digest"] == "scientific"


def test_generalization_raw_replay_requires_all_five_axis_builders(tmp_path: Path, monkeypatch):
    _patch_path_resolvers(monkeypatch)
    p19 = {"generalization_authority_digest": "generalization"}
    monkeypatch.setattr(replay, "verify_generalization_anytime_authority_document", lambda path: {"authority_digest": "generalization"})
    monkeypatch.setattr(
        replay,
        "verify_generalization_source_binding",
        lambda *, repository_root, registry_path, axis: SimpleNamespace(axis=axis.value),
    )
    monkeypatch.setattr(
        replay,
        "verify_generalization_axis_anytime_authority_document",
        lambda path: {
            "axis": next(axis.value for axis in REQUIRED_AXES if path.name.startswith(axis.value.split('_', 1)[0])),
            "authority_digest": path.name.split("_", 1)[0] + "-digest",
        },
    )
    def build_axis(bundle_root, **kwargs):
        prefix = bundle_root.name.split("_", 1)[0]
        return SimpleNamespace(authority_digest=prefix + "-digest", axis_supported_without_iid_assumption=True)
    monkeypatch.setattr(replay, "build_generalization_axis_anytime_authority", build_axis)
    monkeypatch.setattr(
        replay,
        "build_generalization_anytime_authority",
        lambda **kwargs: SimpleNamespace(authority_digest="generalization", generalization_supported_without_iid_assumption=True),
    )
    result = replay.replay_generalization(tmp_path, p19)
    assert len(result["axis_authority_digests"]) == 5
    assert result["generalization_authority_digest"] == "generalization"


def test_fault_tolerance_raw_replay_delegates_to_canonical_builder(tmp_path: Path, monkeypatch):
    _patch_path_resolvers(monkeypatch)
    p19 = {"fault_tolerance_authority_digest": "fault"}
    monkeypatch.setattr(replay, "verify_fault_tolerance_authority_document", lambda path: {"authority_digest": "fault"})
    monkeypatch.setattr(
        replay,
        "build_fault_tolerance_authority",
        lambda *args, **kwargs: SimpleNamespace(authority_digest="fault", all_required_cases_supported=True),
    )
    assert replay.replay_fault_tolerance(tmp_path, p19)["fault_tolerance_authority_digest"] == "fault"


def test_independent_replication_raw_replay_delegates_to_v4_builder(tmp_path: Path, monkeypatch):
    _patch_path_resolvers(monkeypatch)
    p19 = {"independent_replication_authority_digest": "replication"}
    monkeypatch.setattr(replay, "verify_independent_replication_authority_v4_document", lambda path: {"authority_digest": "replication"})
    monkeypatch.setattr(
        replay,
        "build_independent_replication_authority_v4",
        lambda **kwargs: SimpleNamespace(
            authority_digest="replication",
            independent_replication_supported=True,
            social_independence_machine_proven=False,
            replication_package_digest="package",
        ),
    )
    result = replay.replay_independent_replication(tmp_path, p19)
    assert result["independent_replication_authority_digest"] == "replication"
    assert result["social_independence_machine_proven"] is False
