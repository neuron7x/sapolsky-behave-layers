from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_replay import CHECK_HANDLERS
from cwc.governance.p19_external_verification_contract import (
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_external_verification_plan import (
    CANONICAL_PLAN_PATH,
    build_inactive_p19_external_verification_plan_document,
)
from cwc.governance.p19_external_verifier_freeze_readiness import (
    P19ExternalVerifierFreezeReadinessError,
    build_p19_external_verifier_freeze_readiness,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _write(root: Path, rel: str, data: str = "x\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return path


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "dgc-test@example.org"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "DGC Test"], check=True)

    _write(root, VERIFIER_ENTRYPOINT, "print('verifier')\n")
    for rel in VERIFIER_RUNTIME_DEPENDENCIES:
        _write(root, rel, f"# runtime: {rel}\n")
    for rel in REGRESSION_TEST_FILES:
        _write(root, rel, f"# regression: {rel}\n")
    _write(root, "scripts/dgc_freeze_p19_external_verification_plan.py", "# freezer\n")
    _write(root, "scripts/dgc_materialize_inactive_p19_external_verification_plan.py", "# materializer\n")

    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "freeze candidate"], check=True)
    return root


def test_clean_tracked_verifier_surface_is_ready_to_freeze(tmp_path: Path):
    root = _fixture(tmp_path)
    authority = build_p19_external_verifier_freeze_readiness(repository_root=root)
    assert authority.ready_to_freeze is True
    assert authority.all_freeze_subjects_tracked_clean is True
    assert authority.canonical_plan_present is False
    assert authority.canonical_plan_matches_candidate is False
    assert authority.exact_check_count == 8
    assert authority.runtime_dependency_count == len(VERIFIER_RUNTIME_DEPENDENCIES)
    assert authority.regression_test_count == len(REGRESSION_TEST_FILES)


def test_dirty_tracked_runtime_subject_blocks_freeze(tmp_path: Path):
    root = _fixture(tmp_path)
    target = root / VERIFIER_RUNTIME_DEPENDENCIES[0]
    target.write_text(target.read_text(encoding="utf-8") + "# mutation\n", encoding="utf-8")
    with pytest.raises(Exception, match="clean tracked Git worktree|dirty"):
        build_p19_external_verifier_freeze_readiness(repository_root=root)


def test_untracked_runtime_subject_blocks_freeze(tmp_path: Path):
    root = _fixture(tmp_path)
    rel = VERIFIER_RUNTIME_DEPENDENCIES[0]
    subprocess.run(["git", "-C", str(root), "rm", "--cached", "-q", "--", rel], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "remove runtime subject from index"], check=True)
    assert (root / rel).is_file()
    with pytest.raises(P19ExternalVerifierFreezeReadinessError, match="not Git-tracked"):
        build_p19_external_verifier_freeze_readiness(repository_root=root)


def test_untracked_canonical_plan_cannot_masquerade_as_frozen(tmp_path: Path):
    root = _fixture(tmp_path)
    doc = build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(CHECK_HANDLERS)),
    )
    plan = root / CANONICAL_PLAN_PATH
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_bytes(canonical_json_bytes(doc) + b"\n")
    with pytest.raises(P19ExternalVerifierFreezeReadinessError, match="not Git-tracked"):
        build_p19_external_verifier_freeze_readiness(repository_root=root)


def test_committed_canonical_inactive_plan_must_match_current_candidate(tmp_path: Path):
    root = _fixture(tmp_path)
    doc = build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(CHECK_HANDLERS)),
    )
    plan = root / CANONICAL_PLAN_PATH
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_bytes(canonical_json_bytes(doc) + b"\n")
    subprocess.run(["git", "-C", str(root), "add", "--", CANONICAL_PLAN_PATH], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "freeze inactive verifier plan"], check=True)

    authority = build_p19_external_verifier_freeze_readiness(repository_root=root)
    assert authority.canonical_plan_present is True
    assert authority.canonical_plan_matches_candidate is True
    assert authority.ready_to_freeze is True


def test_committed_stale_plan_is_rejected_after_runtime_change(tmp_path: Path):
    root = _fixture(tmp_path)
    doc = build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(CHECK_HANDLERS)),
    )
    plan = root / CANONICAL_PLAN_PATH
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_bytes(canonical_json_bytes(doc) + b"\n")
    subprocess.run(["git", "-C", str(root), "add", "--", CANONICAL_PLAN_PATH], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "freeze inactive verifier plan"], check=True)

    target = root / VERIFIER_RUNTIME_DEPENDENCIES[0]
    target.write_text(target.read_text(encoding="utf-8") + "# semantic change\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "--", VERIFIER_RUNTIME_DEPENDENCIES[0]], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "change verifier semantics"], check=True)

    with pytest.raises(Exception, match="bytes differ|differs from current inactive candidate"):
        build_p19_external_verifier_freeze_readiness(repository_root=root)
