from __future__ import annotations

from pathlib import Path

from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.fault_injection_spec import (
    build_fault_injection_spec_authority,
    verify_fault_injection_spec_authority_document,
)
from cwc.governance.fault_tolerance_authority import (
    build_fault_tolerance_authority,
    verify_fault_tolerance_authority_document,
)
from cwc.governance.materialization_closure import RepositoryIdentityChecker, _assert_repository_identity
from cwc.governance.qualification_closure import _stage_evidence_file


def _repo_file(ledger: EvidenceClosureLedger, value: Path, *, label: str) -> tuple[Path, str]:
    candidate = value if value.is_absolute() else ledger.repository_root / value
    if candidate.is_symlink():
        raise ClosureError(f"{label} symlink rejected")
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(ledger.repository_root)
    except ValueError as exc:
        raise ClosureError(f"{label} path escapes repository") from exc
    if not resolved.is_file():
        raise ClosureError(f"{label} must be a regular file")
    return resolved, rel.as_posix()


def close_fault_injection_spec_frozen(
    ledger: EvidenceClosureLedger,
    *,
    fault_spec_authority_path: Path,
    fault_spec_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "FAULT_INJECTION_SPEC_FROZEN":
        raise ClosureError("FAULT_INJECTION_SPEC_FROZEN is not the next admissible stage")
    authority_path, rel = _repo_file(ledger, fault_spec_authority_path, label="fault injection spec authority")
    execution_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    generalization_path, _, _ = _stage_evidence_file(ledger, stage="GENERALIZATION_REGISTRY_FROZEN")
    try:
        declared = verify_fault_injection_spec_authority_document(
            authority_path, repository_root=ledger.repository_root
        )
        rebuilt = build_fault_injection_spec_authority(
            repository_root=ledger.repository_root,
            fault_spec_path=Path(fault_spec_path),
            execution_manifest_freeze_path=execution_path,
            generalization_registry_path=generalization_path,
        )
    except RuntimeError as exc:
        raise ClosureError("fault injection preregistration replay failed") from exc
    if rebuilt.authority_digest != declared.get("authority_digest"):
        raise ClosureError("declared fault injection spec authority differs from repository subjects")
    if declared.get("repository_commit") != ledger.repo_commit or declared.get("repository_tree") != ledger.repo_tree:
        raise ClosureError("fault injection spec repository identity mismatch")
    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(authority_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="FAULT_INJECTION_SPEC_FROZEN",
        commands=(),
        evidence=(artifact,),
    ))


def close_fault_tolerance_supported(
    ledger: EvidenceClosureLedger,
    *,
    fault_tolerance_authority_path: Path,
    fault_evidence_bundle_root: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "FAULT_TOLERANCE_SUPPORTED":
        raise ClosureError("FAULT_TOLERANCE_SUPPORTED is not the next admissible stage")
    authority_path, rel = _repo_file(ledger, fault_tolerance_authority_path, label="fault tolerance authority")
    spec_path, _, _ = _stage_evidence_file(ledger, stage="FAULT_INJECTION_SPEC_FROZEN")
    execution_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    harness_path, _, _ = _stage_evidence_file(ledger, stage="HARNESS_FROZEN")
    try:
        declared = verify_fault_tolerance_authority_document(authority_path)
        rebuilt = build_fault_tolerance_authority(
            Path(fault_evidence_bundle_root),
            repository_root=ledger.repository_root,
            fault_spec_authority_path=spec_path,
            execution_manifest_freeze_path=execution_path,
            harness_freeze_path=harness_path,
        )
    except RuntimeError as exc:
        raise ClosureError("fault tolerance raw-subject replay failed") from exc
    if rebuilt.authority_digest != declared.get("authority_digest"):
        raise ClosureError("declared fault tolerance authority differs from raw-subject replay")
    if not rebuilt.all_required_cases_supported:
        raise ClosureError("required fault tolerance matrix is unsupported")
    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(authority_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="FAULT_TOLERANCE_SUPPORTED",
        commands=(),
        evidence=(artifact,),
    ))
