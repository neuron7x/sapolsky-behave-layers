from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from cwc.governance.evidence_closure import (
    ClosureError,
    EvidenceArtifact,
    EvidenceClosureLedger,
    StageExecution,
    sha256_file,
)
from cwc.governance.external_evidence_reference import (
    reference_bytes,
    verify_materialization_generation,
)

SOURCE_REGISTRY_REL = Path("artifacts/dgc-product-v1/external_source_authority.json")
RUNTIME_ROOT_REL = Path("eval_bundle")
SOURCE_GATE_COMMAND = ("python", "scripts/dgc_product_external_source_gate.py")
MATERIALIZER_REL = Path("scripts/dgc_materialize_external_sources.py")


def _assert_repository_identity(ledger: EvidenceClosureLedger) -> None:
    def capture(*args: str) -> str:
        try:
            proc = subprocess.run(
                ["git", "-C", str(ledger.repository_root), *args],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ClosureError("repository Git identity cannot be verified") from exc
        return proc.stdout.strip()

    if capture("rev-parse", "HEAD") != ledger.repo_commit:
        raise ClosureError("repository HEAD does not match closure ledger commit")
    if capture("rev-parse", "HEAD^{tree}") != ledger.repo_tree:
        raise ClosureError("repository tree does not match closure ledger tree")
    if capture("status", "--porcelain=v1", "--untracked-files=all"):
        raise ClosureError("repository must be clean for evidence closure")


RepositoryIdentityChecker = Callable[[EvidenceClosureLedger], None]


def _runtime_relative(repository_root: Path, path: Path) -> Path:
    root = repository_root.resolve()
    runtime = (root / RUNTIME_ROOT_REL).resolve()
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(runtime)
    except ValueError as exc:
        raise ClosureError("runtime evidence path must be inside eval_bundle") from exc
    return resolved.relative_to(root)


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            raise ClosureError("existing runtime evidence reference conflicts with verified subject")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def close_source_verified(
    ledger: EvidenceClosureLedger,
    *,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "SOURCE_VERIFIED":
        raise ClosureError("SOURCE_VERIFIED is not the next admissible stage")
    registry = ledger.repository_root / SOURCE_REGISTRY_REL
    if not registry.is_file() or registry.is_symlink():
        raise ClosureError("canonical external source registry missing")
    artifact = EvidenceArtifact(
        path=SOURCE_REGISTRY_REL.as_posix(),
        sha256=sha256_file(registry),
        minimum_bytes=2,
    )
    return ledger.advance(
        StageExecution(
            stage="SOURCE_VERIFIED",
            commands=(SOURCE_GATE_COMMAND,),
            evidence=(artifact,),
        )
    )


def close_materialized_verified(
    ledger: EvidenceClosureLedger,
    *,
    generation_root: Path,
    reference_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "MATERIALIZED_VERIFIED":
        raise ClosureError("MATERIALIZED_VERIFIED is not the next admissible stage")
    relative_reference = _runtime_relative(ledger.repository_root, reference_path)
    canonical_registry = ledger.repository_root / SOURCE_REGISTRY_REL
    canonical_materializer = ledger.repository_root / MATERIALIZER_REL
    if not canonical_registry.is_file() or canonical_registry.is_symlink():
        raise ClosureError("canonical external source registry missing")
    if not canonical_materializer.is_file() or canonical_materializer.is_symlink():
        raise ClosureError("canonical materializer missing")
    reference = verify_materialization_generation(
        generation_root,
        expected_repository_commit=ledger.repo_commit,
        expected_repository_tree=ledger.repo_tree,
        source_registry_path=canonical_registry,
    )
    if reference.source_registry_sha256 != sha256_file(canonical_registry):
        raise ClosureError("external generation source registry does not match current repository")
    if reference.materializer_sha256 != sha256_file(canonical_materializer):
        raise ClosureError("external generation materializer does not match current repository")
    reference_abs = ledger.repository_root / relative_reference
    data = reference_bytes(reference)
    _write_immutable(reference_abs, data)
    artifact = EvidenceArtifact(
        path=relative_reference.as_posix(),
        sha256=sha256_file(reference_abs),
        minimum_bytes=len(data),
    )
    return ledger.advance(
        StageExecution(
            stage="MATERIALIZED_VERIFIED",
            commands=(),
            evidence=(artifact,),
        )
    )
