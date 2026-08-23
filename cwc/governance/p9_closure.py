from __future__ import annotations

from pathlib import Path

from cwc.governance.confirmatory_execution_authority import (
    verify_confirmatory_execution_authority_document,
)
from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.executed_p9_authority import (
    build_executed_p9_authority,
    verify_executed_p9_authority_document,
)
from cwc.governance.materialization_closure import (
    SOURCE_REGISTRY_REL,
    RepositoryIdentityChecker,
    _assert_repository_identity,
)
from cwc.governance.qualification_closure import _stage_evidence_file


def _repo_file(ledger: EvidenceClosureLedger, value: Path, *, label: str) -> tuple[Path, str]:
    candidate = value if value.is_absolute() else ledger.repository_root / value
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(ledger.repository_root)
    except ValueError as exc:
        raise ClosureError(f"{label} path escapes repository") from exc
    if resolved.is_symlink() or not resolved.is_file():
        raise ClosureError(f"{label} must be a regular file")
    return resolved, rel.as_posix()


def close_p9_supported(
    ledger: EvidenceClosureLedger,
    *,
    p9_authority_path: Path,
    execution_bundle_root: Path,
    physical_cost_bundle_root: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "P9_SUPPORTED":
        raise ClosureError("P9_SUPPORTED is not the next admissible stage")
    resolved, rel = _repo_file(ledger, p9_authority_path, label="P9 authority")
    try:
        declared = verify_executed_p9_authority_document(resolved)
    except RuntimeError as exc:
        raise ClosureError("P9 authority verification failed") from exc
    if declared.get("p9_supported") is not True:
        raise ClosureError("P9 support is not established across exact B0-B3 population")
    if declared.get("physical_cost_accounting_verified") is not True:
        raise ClosureError("P9 cannot close without complete physical cost accounting")
    if declared.get("net_cost_superiority_supported") is not True:
        raise ClosureError("P9 cannot close without physically-costed net cost superiority")

    execution_authority_path, _, _ = _stage_evidence_file(ledger, stage="CONFIRMATORY_EXECUTED")
    root_authority_path, _, _ = _stage_evidence_file(ledger, stage="GENERATION_ROOT_FROZEN")
    harness_path, _, _ = _stage_evidence_file(ledger, stage="HARNESS_FROZEN")
    execution_freeze_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    materialization_reference_path, _, _ = _stage_evidence_file(ledger, stage="MATERIALIZED_VERIFIED")
    source_registry_path = ledger.repository_root / SOURCE_REGISTRY_REL
    if source_registry_path.is_symlink() or not source_registry_path.is_file():
        raise ClosureError("canonical source authority registry missing")

    try:
        execution_authority = verify_confirmatory_execution_authority_document(execution_authority_path)
        recomputed = build_executed_p9_authority(
            confirmatory_execution_authority_path=execution_authority_path,
            execution_bundle_root=Path(execution_bundle_root),
            physical_cost_bundle_root=Path(physical_cost_bundle_root),
            confirmatory_root_authority_path=root_authority_path,
            harness_freeze_path=harness_path,
            execution_manifest_freeze_path=execution_freeze_path,
            materialization_reference_path=materialization_reference_path,
            source_registry_path=source_registry_path,
        )
    except RuntimeError as exc:
        raise ClosureError("P9 full-population physical-cost recomputation failed") from exc
    if recomputed.authority_digest != declared.get("authority_digest"):
        raise ClosureError("declared P9 authority differs from recomputed executed population")
    if not recomputed.p9_supported or not recomputed.net_cost_superiority_supported:
        raise ClosureError("recomputed P9 does not certify simultaneous physical-cost superiority/noninferiority")
    if declared.get("execution_authority_digest") != execution_authority.get("authority_digest"):
        raise ClosureError("P9 authority is bound to a different CONFIRMATORY_EXECUTED authority")
    if declared.get("execution_population_digest") != execution_authority.get("execution_population_digest"):
        raise ClosureError("P9 authority execution population differs from CONFIRMATORY_EXECUTED stage")

    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(resolved), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="P9_SUPPORTED",
        commands=(),
        evidence=(artifact,),
    ))
