from __future__ import annotations

import json
from pathlib import Path

from cwc.governance.evidence_closure import (
    ClosureError,
    EvidenceArtifact,
    EvidenceClosureLedger,
    StageExecution,
    sha256_file,
)
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.materialization_closure import RepositoryIdentityChecker, _assert_repository_identity


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


def _prior_materialization_reference(ledger: EvidenceClosureLedger) -> tuple[str, str]:
    state = ledger.load()
    completed = state["completed_stages"]
    receipts = state["receipts"]
    if completed != ["SOURCE_VERIFIED", "MATERIALIZED_VERIFIED"] or len(receipts) != 2:
        raise ClosureError("execution-manifest freeze requires exactly SOURCE_VERIFIED + MATERIALIZED_VERIFIED history")
    materialized = receipts[-1]
    evidence = materialized.get("evidence")
    if not isinstance(evidence, list) or len(evidence) != 1 or not isinstance(evidence[0], dict):
        raise ClosureError("MATERIALIZED_VERIFIED receipt must bind exactly one materialization reference")
    path = str(evidence[0].get("path", ""))
    if not path:
        raise ClosureError("materialization reference path missing from prior receipt")
    reference_path, _ = _repo_relative(ledger.repository_root, Path(path))
    try:
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClosureError("prior materialization reference is unreadable") from exc
    if not isinstance(reference, dict) or reference.get("schema") != "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2":
        raise ClosureError("prior materialization reference schema mismatch")
    digest = str(reference.get("reference_digest", ""))
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ClosureError("prior materialization reference digest malformed")
    if sha256_file(reference_path) != evidence[0].get("sha256"):
        raise ClosureError("prior materialization reference bytes changed after stage closure")
    return path, digest


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
    return ledger.advance(
        StageExecution(
            stage="EXECUTION_MANIFESTS_FROZEN",
            commands=(),
            evidence=(artifact,),
        )
    )
