from __future__ import annotations

from pathlib import Path

from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.harness_freeze import verify_harness_freeze_document
from cwc.governance.materialization_closure import RepositoryIdentityChecker, _assert_repository_identity
from cwc.governance.qualification_closure import _stage_evidence_file
from cwc.governance.trial_sizing_authority import verify_trial_sizing_authority_document


def close_generation_root_frozen(
    ledger: EvidenceClosureLedger,
    *,
    confirmatory_root_authority_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "GENERATION_ROOT_FROZEN":
        raise ClosureError("GENERATION_ROOT_FROZEN is not the next admissible stage")
    path = confirmatory_root_authority_path if confirmatory_root_authority_path.is_absolute() else ledger.repository_root / confirmatory_root_authority_path
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(ledger.repository_root)
    except ValueError as exc:
        raise ClosureError("confirmatory root authority path escapes repository") from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise ClosureError("confirmatory root authority must be a regular file")
    try:
        authority = verify_confirmatory_root_authority_document(resolved)
    except RuntimeError as exc:
        raise ClosureError("confirmatory root authority verification failed") from exc

    harness_path, _, _ = _stage_evidence_file(ledger, stage="HARNESS_FROZEN")
    sizing_path, _, _ = _stage_evidence_file(ledger, stage="TRIAL_SIZED")
    try:
        harness = verify_harness_freeze_document(harness_path)
        sizing = verify_trial_sizing_authority_document(sizing_path)
    except RuntimeError as exc:
        raise ClosureError("upstream confirmatory root authorities are invalid") from exc
    if authority.get("harness_freeze_digest") != harness.get("harness_freeze_digest"):
        raise ClosureError("confirmatory root is bound to a different harness freeze")
    if authority.get("trial_sizing_authority_digest") != sizing.get("authority_digest"):
        raise ClosureError("confirmatory root is bound to a different trial-sizing authority")
    if authority.get("family_id") != harness.get("family_id"):
        raise ClosureError("confirmatory root family differs from harness")
    root = authority.get("root")
    if not isinstance(root, dict):
        raise ClosureError("confirmatory root payload missing")
    if root.get("repo_commit_oid") != ledger.repo_commit or root.get("repo_tree_oid") != ledger.repo_tree:
        raise ClosureError("confirmatory root repository identity differs from closure ledger")
    if root.get("confirmatory_task_manifest_sha256") != harness.get("confirmatory_task_manifest_digest"):
        raise ClosureError("confirmatory root task population differs from held-out harness population")
    if root.get("materialized_task_manifest_sha256") != harness.get("materialized_task_manifest_digest"):
        raise ClosureError("confirmatory root lost full materialized workload identity")

    artifact = EvidenceArtifact(path=rel.as_posix(), sha256=sha256_file(resolved), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="GENERATION_ROOT_FROZEN",
        commands=(),
        evidence=(artifact,),
    ))
