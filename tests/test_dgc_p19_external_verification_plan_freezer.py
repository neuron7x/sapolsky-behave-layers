from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cwc.governance.p19_external_verification_plan import (
    CANONICAL_PLAN_PATH,
    ENTRYPOINT,
    REQUIRED_IMPLEMENTATION_DEPENDENCIES,
    load_p19_external_verification_plan,
)
from scripts.dgc_freeze_p19_external_verification_plan import main


def _prepare_verifier_surface(root: Path) -> None:
    entry = root / ENTRYPOINT
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("# deterministic test entrypoint\n", encoding="utf-8")
    for rel in REQUIRED_IMPLEMENTATION_DEPENDENCIES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# deterministic test dependency: {rel}\n", encoding="utf-8")


def test_freezer_materializes_only_inactive_content_addressed_plan_v4(tmp_path: Path, monkeypatch):
    _prepare_verifier_surface(tmp_path)
    output = Path(CANONICAL_PLAN_PATH)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dgc_freeze_p19_external_verification_plan.py",
            "--repository-root", str(tmp_path),
            "--output", str(output),
        ],
    )
    assert main() == 0
    plan = load_p19_external_verification_plan(
        tmp_path / output,
        repository_root=tmp_path,
        require_active=False,
    )
    assert plan.activation_authorized is False
    assert plan.activation_evidence_requirement == "DUAL_EXTERNAL_SSH_SIGNED_GIT_BOUND_CANONICAL_REGRESSION_V1"
    assert plan.all_check_implementations_complete is True
    assert plan.product_qualification_authorized is False
    assert plan.activation_authority_path is None
    assert plan.activation_authority_digest is None
    assert plan.activation_verifier_principals == ()
    assert plan.activation_signer_key_digests == ()
    assert plan.activation_regression_receipt_path is None
    assert plan.activation_regression_receipt_digest is None
    assert plan.activation_regression_test_manifest_digest is None
    with pytest.raises(Exception, match="not activated"):
        load_p19_external_verification_plan(
            tmp_path / output,
            repository_root=tmp_path,
            require_active=True,
        )


def test_freezer_cannot_overwrite_existing_plan(tmp_path: Path, monkeypatch):
    _prepare_verifier_surface(tmp_path)
    output = Path(CANONICAL_PLAN_PATH)
    argv = [
        "dgc_freeze_p19_external_verification_plan.py",
        "--repository-root", str(tmp_path),
        "--output", str(output),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == 0
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(FileExistsError):
        main()


def test_freezer_rejects_output_escape(tmp_path: Path, monkeypatch):
    _prepare_verifier_surface(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dgc_freeze_p19_external_verification_plan.py",
            "--repository-root", str(tmp_path),
            "--output", str(tmp_path.parent / "escaped-plan.json"),
        ],
    )
    with pytest.raises(SystemExit, match="Plan V4 output must remain inside repository"):
        main()
