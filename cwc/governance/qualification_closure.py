from __future__ import annotations

import json
from pathlib import Path

from cwc.governance.b2_fit_authority import verify_b2_fit_authority_document
from cwc.governance.ccf_spec_authority import verify_ccf_spec_authority_document
from cwc.governance.evidence_closure import (
    ClosureError,
    EvidenceArtifact,
    EvidenceClosureLedger,
    StageExecution,
    sha256_file,
)
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.generalization_registry import (
    recompute_generalization_registry_from_document,
    verify_generalization_registry_document,
)
from cwc.governance.harness_freeze import verify_harness_freeze_document
from cwc.governance.materialization_closure import RepositoryIdentityChecker, _assert_repository_identity
from cwc.governance.trial_sizing_authority import verify_trial_sizing_authority_document


def _repo_relative(root: Path, value: Path) -> tuple[Path, str]:
    candidate = value if value.is_absolute() else root / value
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ClosureError("qualification evidence path escapes repository root") from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise ClosureError("qualification evidence must be a regular file")
    return resolved, rel.as_posix()


def _stage_evidence_file(ledger: EvidenceClosureLedger, *, stage: str) -> tuple[Path, str, dict[str, object]]:
    state = ledger.load()
    receipts = state["receipts"]
    matches = [receipt for receipt in receipts if isinstance(receipt, dict) and receipt.get("stage") == stage]
    if len(matches) != 1:
        raise ClosureError(f"closure ledger must contain exactly one {stage} receipt")
    evidence = matches[0].get("evidence")
    if not isinstance(evidence, list) or len(evidence) != 1 or not isinstance(evidence[0], dict):
        raise ClosureError(f"{stage} receipt must bind exactly one evidence artifact")
    path_value = str(evidence[0].get("path", ""))
    if not path_value:
        raise ClosureError(f"{stage} evidence path missing")
    path, rel = _repo_relative(ledger.repository_root, Path(path_value))
    if sha256_file(path) != evidence[0].get("sha256"):
        raise ClosureError(f"{stage} evidence bytes changed after stage closure")
    return path, rel, evidence[0]


def _prior_materialization_reference(ledger: EvidenceClosureLedger) -> tuple[str, str]:
    state = ledger.load()
    completed = state["completed_stages"]
    if completed != ["SOURCE_VERIFIED", "MATERIALIZED_VERIFIED"]:
        raise ClosureError("execution-manifest freeze requires exactly SOURCE_VERIFIED + MATERIALIZED_VERIFIED history")
    reference_path, path_value, _ = _stage_evidence_file(ledger, stage="MATERIALIZED_VERIFIED")
    try:
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClosureError("prior materialization reference is unreadable") from exc
    if not isinstance(reference, dict) or reference.get("schema") != "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2":
        raise ClosureError("prior materialization reference schema mismatch")
    digest = str(reference.get("reference_digest", ""))
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ClosureError("prior materialization reference digest malformed")
    return path_value, digest


def close_execution_manifests_frozen(
    ledger: EvidenceClosureLedger,
    *,
    freeze_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "EXECUTION_MANIFESTS_FROZEN":
        raise ClosureError("EXECUTION_MANIFESTS_FROZEN is not the next admissible stage")
    path, rel = _repo_relative(ledger.repository_root, freeze_path)
    try:
        freeze = verify_execution_manifest_freeze_document(path)
    except RuntimeError as exc:
        raise ClosureError("execution manifest freeze verification failed") from exc
    if freeze.get("repository_commit") != ledger.repo_commit or freeze.get("repository_tree") != ledger.repo_tree:
        raise ClosureError("execution manifest freeze repository identity mismatch")
    prior_path, prior_digest = _prior_materialization_reference(ledger)
    if freeze.get("materialization_reference_path") != prior_path:
        raise ClosureError("execution manifest freeze references a different materialization subject")
    if freeze.get("materialization_reference_digest") != prior_digest:
        raise ClosureError("execution manifest freeze materialization reference digest mismatch")
    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="EXECUTION_MANIFESTS_FROZEN",
        commands=(),
        evidence=(artifact,),
    ))


def close_ccf_spec_frozen(
    ledger: EvidenceClosureLedger,
    *,
    ccf_spec_authority_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "CCF_SPEC_FROZEN":
        raise ClosureError("CCF_SPEC_FROZEN is not the next admissible stage")
    path, rel = _repo_relative(ledger.repository_root, ccf_spec_authority_path)
    try:
        authority = verify_ccf_spec_authority_document(path)
    except RuntimeError as exc:
        raise ClosureError("CCF spec authority verification failed") from exc
    execution_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    try:
        execution = verify_execution_manifest_freeze_document(execution_path)
    except RuntimeError as exc:
        raise ClosureError("prior execution manifest freeze is invalid") from exc
    if authority.get("execution_manifest_freeze_digest") != execution.get("freeze_digest"):
        raise ClosureError("CCF spec authority is bound to a different execution freeze")
    if authority.get("family_id") != execution.get("family_id"):
        raise ClosureError("CCF spec authority family differs from execution freeze")
    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="CCF_SPEC_FROZEN",
        commands=(),
        evidence=(artifact,),
    ))


def close_generalization_registry_frozen(
    ledger: EvidenceClosureLedger,
    *,
    generalization_registry_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "GENERALIZATION_REGISTRY_FROZEN":
        raise ClosureError("GENERALIZATION_REGISTRY_FROZEN is not the next admissible stage")
    path, rel = _repo_relative(ledger.repository_root, generalization_registry_path)
    execution_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    try:
        declared = verify_generalization_registry_document(path)
        rebuilt = recompute_generalization_registry_from_document(
            repository_root=ledger.repository_root,
            execution_manifest_freeze_path=execution_path,
            registry_path=path,
        )
        execution = verify_execution_manifest_freeze_document(execution_path)
    except RuntimeError as exc:
        raise ClosureError("G1-G5 generalization registry subject replay failed") from exc
    if rebuilt.registry_digest != declared.get("registry_digest"):
        raise ClosureError("declared G1-G5 registry differs from repository subjects")
    if declared.get("execution_manifest_freeze_digest") != execution.get("freeze_digest"):
        raise ClosureError("G1-G5 registry is bound to a different execution freeze")
    if declared.get("family_id") != execution.get("family_id"):
        raise ClosureError("G1-G5 registry family differs from execution freeze")
    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="GENERALIZATION_REGISTRY_FROZEN",
        commands=(),
        evidence=(artifact,),
    ))


def close_b2_fitted(
    ledger: EvidenceClosureLedger,
    *,
    b2_authority_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "B2_FITTED":
        raise ClosureError("B2_FITTED is not the next admissible stage")
    path, rel = _repo_relative(ledger.repository_root, b2_authority_path)
    try:
        authority = verify_b2_fit_authority_document(path)
    except RuntimeError as exc:
        raise ClosureError("B2 fit authority verification failed") from exc

    freeze_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    ccf_path, _, _ = _stage_evidence_file(ledger, stage="CCF_SPEC_FROZEN")
    generalization_path, _, _ = _stage_evidence_file(ledger, stage="GENERALIZATION_REGISTRY_FROZEN")
    try:
        freeze = verify_execution_manifest_freeze_document(freeze_path)
        ccf = verify_ccf_spec_authority_document(ccf_path)
        generalization = verify_generalization_registry_document(generalization_path)
    except RuntimeError as exc:
        raise ClosureError("pre-outcome execution/CCF/generalization freeze is invalid") from exc
    if authority.get("execution_manifest_freeze_digest") != freeze.get("freeze_digest"):
        raise ClosureError("B2 authority is bound to a different execution manifest freeze")
    if ccf.get("execution_manifest_freeze_digest") != freeze.get("freeze_digest"):
        raise ClosureError("B2 stage lost preregistered CCF freeze lineage")
    if generalization.get("execution_manifest_freeze_digest") != freeze.get("freeze_digest"):
        raise ClosureError("B2 stage lost preregistered G1-G5 registry lineage")
    if authority.get("confirmatory_task_digest") != generalization.get("primary_confirmatory_task_digest"):
        raise ClosureError("B2 confirmatory task population differs from preregistered generalization registry")
    if authority.get("generalization_task_digest") != generalization.get("g1_holdout_task_digest"):
        raise ClosureError("B2 G1 holdout population differs from preregistered generalization registry")
    if not (
        authority.get("family_id") == freeze.get("family_id")
        and ccf.get("family_id") == freeze.get("family_id")
        and generalization.get("family_id") == freeze.get("family_id")
    ):
        raise ClosureError("B2/CCF/generalization family differs from execution manifest freeze")

    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="B2_FITTED",
        commands=(),
        evidence=(artifact,),
    ))


def close_harness_frozen(
    ledger: EvidenceClosureLedger,
    *,
    harness_freeze_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "HARNESS_FROZEN":
        raise ClosureError("HARNESS_FROZEN is not the next admissible stage")
    path, rel = _repo_relative(ledger.repository_root, harness_freeze_path)
    try:
        harness = verify_harness_freeze_document(path)
    except RuntimeError as exc:
        raise ClosureError("harness freeze verification failed") from exc

    execution_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    ccf_path, _, _ = _stage_evidence_file(ledger, stage="CCF_SPEC_FROZEN")
    generalization_path, _, _ = _stage_evidence_file(ledger, stage="GENERALIZATION_REGISTRY_FROZEN")
    b2_path, _, _ = _stage_evidence_file(ledger, stage="B2_FITTED")
    try:
        execution = verify_execution_manifest_freeze_document(execution_path)
        ccf = verify_ccf_spec_authority_document(ccf_path)
        generalization = verify_generalization_registry_document(generalization_path)
        b2 = verify_b2_fit_authority_document(b2_path)
    except RuntimeError as exc:
        raise ClosureError("upstream harness authorities are invalid") from exc

    if harness.get("execution_manifest_freeze_digest") != execution.get("freeze_digest"):
        raise ClosureError("harness freeze is bound to a different execution manifest freeze")
    if harness.get("ccf_spec_authority_digest") != ccf.get("authority_digest"):
        raise ClosureError("harness freeze is bound to a different CCF preregistration")
    if harness.get("ccf_spec_digest") != ccf.get("ccf_spec_digest"):
        raise ClosureError("harness CCF spec identity differs from preregistered CCF spec")
    if harness.get("generalization_registry_digest") != generalization.get("registry_digest"):
        raise ClosureError("harness freeze is bound to a different G1-G5 preregistration")
    if harness.get("g1_holdout_task_digest") != generalization.get("g1_holdout_task_digest"):
        raise ClosureError("harness G1 holdout identity differs from preregistered registry")
    if harness.get("b2_fit_authority_digest") != b2.get("authority_digest"):
        raise ClosureError("harness freeze is bound to a different B2 authority")
    if not (
        harness.get("family_id") == execution.get("family_id")
        and harness.get("family_id") == b2.get("family_id")
        and harness.get("family_id") == ccf.get("family_id")
        and harness.get("family_id") == generalization.get("family_id")
    ):
        raise ClosureError("harness freeze family differs from upstream authorities")

    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="HARNESS_FROZEN",
        commands=(),
        evidence=(artifact,),
    ))


def close_trial_sized(
    ledger: EvidenceClosureLedger,
    *,
    trial_sizing_authority_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "TRIAL_SIZED":
        raise ClosureError("TRIAL_SIZED is not the next admissible stage")
    path, rel = _repo_relative(ledger.repository_root, trial_sizing_authority_path)
    try:
        sizing = verify_trial_sizing_authority_document(path)
    except RuntimeError as exc:
        raise ClosureError("trial-sizing authority verification failed") from exc

    execution_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    b2_path, _, _ = _stage_evidence_file(ledger, stage="B2_FITTED")
    harness_path, _, _ = _stage_evidence_file(ledger, stage="HARNESS_FROZEN")
    try:
        execution = verify_execution_manifest_freeze_document(execution_path)
        b2 = verify_b2_fit_authority_document(b2_path)
        harness = verify_harness_freeze_document(harness_path)
    except RuntimeError as exc:
        raise ClosureError("upstream trial-sizing authorities are invalid") from exc

    if sizing.get("execution_manifest_freeze_digest") != execution.get("freeze_digest"):
        raise ClosureError("trial-sizing authority is bound to a different execution freeze")
    if sizing.get("b2_fit_authority_digest") != b2.get("authority_digest"):
        raise ClosureError("trial-sizing authority is bound to a different B2 fit")
    if sizing.get("harness_freeze_digest") != harness.get("harness_freeze_digest"):
        raise ClosureError("trial-sizing authority is bound to a different harness freeze")
    if sizing.get("family_id") != harness.get("family_id"):
        raise ClosureError("trial-sizing authority family differs from harness")

    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="TRIAL_SIZED",
        commands=(),
        evidence=(artifact,),
    ))
