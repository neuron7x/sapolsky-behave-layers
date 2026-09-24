from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cwc.governance.evidence_packaging_authority import (
    EvidencePackagingAuthorityError,
    build_evidence_packaging_authority,
)
from cwc.governance.product_qualification_pointer import VerifiedProductQualificationPointer


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", message], check=True, stdout=subprocess.PIPE)
    return _git(root, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.org"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "DGC Test"], check=True)
    (root / "cwc/governance").mkdir(parents=True)
    (root / "artifacts/dgc-product-v1").mkdir(parents=True)
    (root / "cwc/governance/kernel.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json").write_text(
        '{"activation_authorized":false}\n', encoding="utf-8"
    )
    (root / "artifacts/dgc-product-v1/evidence_status.json").write_text(
        '{"product_qualified":false}\n', encoding="utf-8"
    )
    commit = _commit(root, "execution source")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    return root, commit, tree


def _qualification(commit: str, tree: str) -> VerifiedProductQualificationPointer:
    return VerifiedProductQualificationPointer(
        generation_id="generation-1",
        repo_commit=commit,
        repo_tree=tree,
        ledger_path="eval_bundle/ledger.json",
        ledger_sha256="1" * 64,
        global_v5_authority_path="eval_bundle/global-v5.json",
        global_v5_authority_sha256="2" * 64,
        global_v5_authority_digest="3" * 64,
        source_registry_path="artifacts/dgc-product-v1/external_source_authority.json",
        family_p19_paths=("eval_bundle/swe-p19.json", "eval_bundle/terminal-p19.json"),
        p19_verifier_policy_path="artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json",
        ledger_tip_receipt_digest="4" * 64,
        pointer_digest="5" * 64,
    )


def test_append_only_evidence_packaging_can_follow_frozen_execution_revision(tmp_path: Path):
    root, execution_commit, execution_tree = _repo(tmp_path)
    pointer = root / "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json"
    pointer.write_text('{"activation_authorized":true}\n', encoding="utf-8")
    evidence = root / "artifacts/dgc-product-v1/generated/final.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text('{"status":"PASS"}\n', encoding="utf-8")
    packaging_commit = _commit(root, "package evidence")

    authority = build_evidence_packaging_authority(
        repository_root=root,
        qualification=_qualification(execution_commit, execution_tree),
    )
    assert authority.qualified_execution_commit == execution_commit
    assert authority.packaging_commit == packaging_commit
    assert authority.qualified_execution_tree != authority.packaging_tree
    assert authority.protected_execution_source_unchanged is True
    assert authority.global_v5_authority_digest == "3" * 64
    assert {row.status for row in authority.delta_rows} == {"A", "M"}
    assert authority.slsa_conformance_claim is False


def test_post_outcome_executable_source_modification_fails_closed(tmp_path: Path):
    root, execution_commit, execution_tree = _repo(tmp_path)
    (root / "cwc/governance/kernel.py").write_text("VALUE = 2\n", encoding="utf-8")
    _commit(root, "illegal post-outcome source mutation")
    with pytest.raises(EvidencePackagingAuthorityError, match="protected execution-source path"):
        build_evidence_packaging_authority(
            repository_root=root,
            qualification=_qualification(execution_commit, execution_tree),
        )


def test_post_outcome_deletion_is_never_append_only(tmp_path: Path):
    root, execution_commit, execution_tree = _repo(tmp_path)
    (root / "artifacts/dgc-product-v1/evidence_status.json").unlink()
    _commit(root, "delete mirror")
    with pytest.raises(EvidencePackagingAuthorityError, match="not append-only"):
        build_evidence_packaging_authority(
            repository_root=root,
            qualification=_qualification(execution_commit, execution_tree),
        )


def test_added_file_outside_evidence_namespaces_fails_closed(tmp_path: Path):
    root, execution_commit, execution_tree = _repo(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/posthoc.md").write_text("post hoc methodology\n", encoding="utf-8")
    _commit(root, "illegal post-outcome doc")
    with pytest.raises(EvidencePackagingAuthorityError, match="outside evidence-only namespaces"):
        build_evidence_packaging_authority(
            repository_root=root,
            qualification=_qualification(execution_commit, execution_tree),
        )


def test_post_outcome_evidence_symlink_is_rejected_even_inside_allowed_namespace(tmp_path: Path):
    root, execution_commit, execution_tree = _repo(tmp_path)
    generated = root / "artifacts/dgc-product-v1/generated"
    generated.mkdir(parents=True)
    (generated / "target.json").write_text("{}\n", encoding="utf-8")
    (generated / "alias.json").symlink_to("target.json")
    _commit(root, "symlink evidence")
    with pytest.raises(EvidencePackagingAuthorityError, match="symlink/special mode rejected"):
        build_evidence_packaging_authority(
            repository_root=root,
            qualification=_qualification(execution_commit, execution_tree),
        )


def test_post_outcome_ambiguous_control_character_path_is_rejected(tmp_path: Path):
    root, execution_commit, execution_tree = _repo(tmp_path)
    generated = root / "artifacts/dgc-product-v1/generated"
    generated.mkdir(parents=True)
    (generated / "bad\tname.json").write_text("{}\n", encoding="utf-8")
    _commit(root, "ambiguous evidence path")
    with pytest.raises(EvidencePackagingAuthorityError, match="forbidden control/ambiguous character"):
        build_evidence_packaging_authority(
            repository_root=root,
            qualification=_qualification(execution_commit, execution_tree),
        )


def test_approved_pointer_cannot_change_git_mode(tmp_path: Path):
    root, execution_commit, execution_tree = _repo(tmp_path)
    pointer = root / "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json"
    pointer.write_text('{"activation_authorized":true}\n', encoding="utf-8")
    pointer.chmod(0o755)
    _commit(root, "illegal pointer mode change")
    with pytest.raises(EvidencePackagingAuthorityError, match="changed Git mode"):
        build_evidence_packaging_authority(
            repository_root=root,
            qualification=_qualification(execution_commit, execution_tree),
        )


def test_dirty_tracked_packaging_tree_fails_closed(tmp_path: Path):
    root, execution_commit, execution_tree = _repo(tmp_path)
    (root / "artifacts/dgc-product-v1/evidence_status.json").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(EvidencePackagingAuthorityError, match="must be clean"):
        build_evidence_packaging_authority(
            repository_root=root,
            qualification=_qualification(execution_commit, execution_tree),
        )
