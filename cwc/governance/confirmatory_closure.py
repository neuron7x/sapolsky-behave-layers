from __future__ import annotations

import math
from pathlib import Path

from cwc.governance.confirmatory_execution_authority import (
    verify_confirmatory_execution_authority_document,
)
from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.execution_evidence_bundle import verify_execution_bundle
from cwc.governance.harness_freeze import verify_harness_freeze_document
from cwc.governance.materialization_closure import RepositoryIdentityChecker, _assert_repository_identity
from cwc.governance.qualification_closure import _stage_evidence_file
from cwc.governance.trial_sizing_authority import verify_trial_sizing_authority_document


def _repo_authority_file(ledger: EvidenceClosureLedger, path: Path, *, label: str) -> tuple[Path, str]:
    candidate = path if path.is_absolute() else ledger.repository_root / path
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(ledger.repository_root)
    except ValueError as exc:
        raise ClosureError(f"{label} path escapes repository") from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise ClosureError(f"{label} must be a regular file")
    return resolved, rel.as_posix()


def close_generation_root_frozen(
    ledger: EvidenceClosureLedger,
    *,
    confirmatory_root_authority_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "GENERATION_ROOT_FROZEN":
        raise ClosureError("GENERATION_ROOT_FROZEN is not the next admissible stage")
    resolved, rel = _repo_authority_file(
        ledger, confirmatory_root_authority_path, label="confirmatory root authority"
    )
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

    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(resolved), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="GENERATION_ROOT_FROZEN",
        commands=(),
        evidence=(artifact,),
    ))


def close_confirmatory_executed(
    ledger: EvidenceClosureLedger,
    *,
    confirmatory_execution_authority_path: Path,
    execution_bundle_root: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "CONFIRMATORY_EXECUTED":
        raise ClosureError("CONFIRMATORY_EXECUTED is not the next admissible stage")
    resolved, rel = _repo_authority_file(
        ledger,
        confirmatory_execution_authority_path,
        label="confirmatory execution authority",
    )
    try:
        execution = verify_confirmatory_execution_authority_document(resolved)
    except RuntimeError as exc:
        raise ClosureError("confirmatory execution authority verification failed") from exc

    root_path, _, _ = _stage_evidence_file(ledger, stage="GENERATION_ROOT_FROZEN")
    try:
        root_authority = verify_confirmatory_root_authority_document(root_path)
        bundle = verify_execution_bundle(
            Path(execution_bundle_root),
            confirmatory_root_authority_path=root_path,
        )
    except RuntimeError as exc:
        raise ClosureError("confirmatory execution subject replay failed") from exc

    if execution.get("root_authority_digest") != root_authority.get("authority_digest"):
        raise ClosureError("execution authority is bound to a different generation-root authority")
    root = root_authority.get("root")
    if not isinstance(root, dict):
        raise ClosureError("generation-root payload missing")
    if execution.get("root_digest") != root.get("root_digest"):
        raise ClosureError("execution authority is bound to a different generation root")
    if execution.get("distributed_spec_digest") != root_authority.get("distributed_spec_digest"):
        raise ClosureError("execution authority is bound to a different distributed spec")
    if execution.get("family_id") != root_authority.get("family_id") or bundle.family_id != execution.get("family_id"):
        raise ClosureError("confirmatory execution family lineage mismatch")

    comparisons = (
        ("execution_bundle_digest", bundle.bundle_digest),
        ("execution_bundle_payload_manifest_sha256", bundle.payload_manifest_sha256),
        ("result_population_digest", bundle.result_population_digest),
        ("audit_root_digest", bundle.audit_root_digest),
    )
    for field, observed in comparisons:
        if execution.get(field) != observed:
            raise ClosureError(f"execution authority {field} differs from replayed bundle")
    if int(execution.get("expected_work_units", -1)) != bundle.completion.expected_units:
        raise ClosureError("execution authority expected work-unit count mismatch")
    if int(execution.get("committed_work_units", -1)) != bundle.completion.committed_units:
        raise ClosureError("execution authority committed work-unit count mismatch")
    if not math.isclose(
        float(execution.get("total_cost_usd", -1)),
        bundle.total_cost_usd,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ClosureError("execution authority total cost differs from replayed bundle")
    if execution.get("materialized_source_authority_digest") != root_authority.get("materialized_source_authority_digest"):
        raise ClosureError("execution authority source lineage differs from frozen materialized authority")

    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(resolved), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="CONFIRMATORY_EXECUTED",
        commands=(),
        evidence=(artifact,),
    ))
