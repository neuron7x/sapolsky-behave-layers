from __future__ import annotations

from pathlib import Path
from typing import Mapping

from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.generalization_execution_authority import (
    build_generalization_authority,
    build_generalization_axis_authority,
    verify_generalization_authority_document,
    verify_generalization_axis_authority_document,
)
from cwc.governance.generalization_registry import GeneralizationAxis, REQUIRED_AXES
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


def close_generalization_supported(
    ledger: EvidenceClosureLedger,
    *,
    generalization_authority_path: Path,
    axis_authority_paths: Mapping[GeneralizationAxis, Path],
    axis_bundle_roots: Mapping[GeneralizationAxis, Path],
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "GENERALIZATION_SUPPORTED":
        raise ClosureError("GENERALIZATION_SUPPORTED is not the next admissible stage")
    if set(axis_authority_paths) != set(REQUIRED_AXES) or set(axis_bundle_roots) != set(REQUIRED_AXES):
        raise ClosureError("generalization closure requires exact G1-G5 authority/bundle populations")

    final_path, final_rel = _repo_file(
        ledger, generalization_authority_path, label="generalization authority"
    )
    try:
        declared_final = verify_generalization_authority_document(final_path)
    except RuntimeError as exc:
        raise ClosureError("generalization authority verification failed") from exc
    if declared_final.get("generalization_supported") is not True:
        raise ClosureError("generalization authority does not support exact G1-G5")

    registry_path, _, _ = _stage_evidence_file(ledger, stage="GENERALIZATION_REGISTRY_FROZEN")
    sizing_path, _, _ = _stage_evidence_file(ledger, stage="TRIAL_SIZED")
    p9_path, _, _ = _stage_evidence_file(ledger, stage="P9_SUPPORTED")

    declared_axis_paths: dict[GeneralizationAxis, Path] = {}
    for axis in REQUIRED_AXES:
        authority_path, _ = _repo_file(
            ledger, axis_authority_paths[axis], label=f"{axis.value} authority"
        )
        declared_axis_paths[axis] = authority_path
        try:
            declared_axis = verify_generalization_axis_authority_document(authority_path)
            recomputed_axis = build_generalization_axis_authority(
                Path(axis_bundle_roots[axis]),
                repository_root=ledger.repository_root,
                registry_path=registry_path,
                trial_sizing_authority_path=sizing_path,
            )
        except RuntimeError as exc:
            raise ClosureError(f"{axis.value} raw-subject replay failed") from exc
        if declared_axis.get("axis") != axis.value:
            raise ClosureError(f"{axis.value} authority path/identity mismatch")
        if recomputed_axis.authority_digest != declared_axis.get("authority_digest"):
            raise ClosureError(f"{axis.value} declared authority differs from raw-subject replay")
        if not recomputed_axis.supported:
            raise ClosureError(f"{axis.value} generalization gate failed: {recomputed_axis.reason_code}")

    try:
        recomputed_final = build_generalization_authority(
            registry_path=registry_path,
            p9_scientific_authority_path=p9_path,
            axis_authority_paths=declared_axis_paths,
        )
    except RuntimeError as exc:
        raise ClosureError("G1-G5 final scientific composition failed") from exc
    if recomputed_final.authority_digest != declared_final.get("authority_digest"):
        raise ClosureError("declared generalization authority differs from recomputed G1-G5 composition")
    if not recomputed_final.generalization_supported:
        raise ClosureError("recomputed exact G1-G5 composition is not supported")

    artifact = EvidenceArtifact(path=final_rel, sha256=sha256_file(final_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="GENERALIZATION_SUPPORTED",
        commands=(),
        evidence=(artifact,),
    ))
