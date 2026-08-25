from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verification_contract import (
    CANONICAL_REGRESSION_COMMAND,
    CHECK_METHOD_IDS,
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)

SCHEMA = "DGC_P19_EXTERNAL_VERIFIER_REGRESSION_RECEIPT_V1"
REGRESSION_GENERATION = "P19_EXTERNAL_VERIFIER_CANONICAL_REGRESSION_V1"


class P19ExternalVerifierRegressionError(RuntimeError):
    pass


def _git_oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerifierRegressionError(f"{name} must be lowercase 40-hex Git OID")
    return text


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerifierRegressionError(f"{name} must be lowercase SHA-256")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if (
        not text
        or text != text.strip()
        or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\"))
        or "//" in text
    ):
        raise P19ExternalVerifierRegressionError(f"{label} must be canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise P19ExternalVerifierRegressionError(f"{label} must be canonical repository-relative POSIX path")
    return rel.as_posix()


def _repo_file(root: Path, rel: str, *, label: str, allow_empty: bool = False) -> Path:
    candidate = root / rel
    if candidate.is_symlink():
        raise P19ExternalVerifierRegressionError(f"{label} symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise P19ExternalVerifierRegressionError(f"{label} escapes repository") from exc
    if not resolved.is_file():
        raise P19ExternalVerifierRegressionError(f"{label} missing")
    if not allow_empty and resolved.stat().st_size <= 0:
        raise P19ExternalVerifierRegressionError(f"{label} must be non-empty")
    return resolved


def _manifest(root: Path, paths: Sequence[str]) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for rel in paths:
        normalized = _safe_rel(rel, label="regression subject")
        path = _repo_file(root, normalized, label=f"regression subject {normalized}")
        rows.append({
            "path": normalized,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
    return tuple(rows)


def current_runtime_manifest(repository_root: Path) -> tuple[dict[str, object], ...]:
    root = Path(repository_root).resolve()
    return _manifest(root, (VERIFIER_ENTRYPOINT, *VERIFIER_RUNTIME_DEPENDENCIES))


def current_test_manifest(repository_root: Path) -> tuple[dict[str, object], ...]:
    root = Path(repository_root).resolve()
    return _manifest(root, REGRESSION_TEST_FILES)


def current_runtime_digest(repository_root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(list(current_runtime_manifest(repository_root))))


def current_test_manifest_digest(repository_root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(list(current_test_manifest(repository_root))))


def method_map_digest() -> str:
    rows = [
        {"check_id": check_id, "method_id": CHECK_METHOD_IDS[check_id]}
        for check_id in sorted(CHECK_METHOD_IDS)
    ]
    return sha256_bytes(canonical_json_bytes(rows))


@dataclass(frozen=True, slots=True)
class P19ExternalVerifierRegressionReceipt:
    regression_generation: str
    source_commit: str
    source_tree: str
    canonical_command_argv: tuple[str, ...]
    runtime_manifest: tuple[dict[str, object], ...]
    runtime_manifest_digest: str
    test_manifest: tuple[dict[str, object], ...]
    test_manifest_digest: str
    method_map_digest: str
    stdout_path: str
    stdout_sha256: str
    stdout_bytes: int
    stderr_path: str
    stderr_sha256: str
    stderr_bytes: int
    exit_code: int
    all_regression_tests_passed: bool
    execution_provenance_scope: str
    receipt_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {"schema": SCHEMA, **asdict(self), "activation_authorized": False}


def build_p19_external_verifier_regression_receipt(
    *,
    repository_root: Path,
    source_commit: str,
    source_tree: str,
    command_argv: Sequence[str],
    stdout_path: Path,
    stderr_path: Path,
    exit_code: int,
) -> P19ExternalVerifierRegressionReceipt:
    root = Path(repository_root).resolve()
    if tuple(command_argv) != CANONICAL_REGRESSION_COMMAND:
        raise P19ExternalVerifierRegressionError("regression command differs from canonical verifier regression command")
    if int(exit_code) != 0:
        raise P19ExternalVerifierRegressionError("regression exit code must be zero")

    stdout_rel = _safe_rel(Path(stdout_path).as_posix(), label="regression stdout")
    stderr_rel = _safe_rel(Path(stderr_path).as_posix(), label="regression stderr")
    stdout = _repo_file(root, stdout_rel, label="regression stdout", allow_empty=False)
    stderr = _repo_file(root, stderr_rel, label="regression stderr", allow_empty=True)
    runtime = current_runtime_manifest(root)
    tests = current_test_manifest(root)
    payload = {
        "regression_generation": REGRESSION_GENERATION,
        "source_commit": _git_oid("source_commit", source_commit),
        "source_tree": _git_oid("source_tree", source_tree),
        "canonical_command_argv": list(CANONICAL_REGRESSION_COMMAND),
        "runtime_manifest": list(runtime),
        "runtime_manifest_digest": sha256_bytes(canonical_json_bytes(list(runtime))),
        "test_manifest": list(tests),
        "test_manifest_digest": sha256_bytes(canonical_json_bytes(list(tests))),
        "method_map_digest": method_map_digest(),
        "stdout_path": stdout_rel,
        "stdout_sha256": sha256_file(stdout),
        "stdout_bytes": stdout.stat().st_size,
        "stderr_path": stderr_rel,
        "stderr_sha256": sha256_file(stderr),
        "stderr_bytes": stderr.stat().st_size,
        "exit_code": 0,
        "all_regression_tests_passed": True,
        "execution_provenance_scope": "RAW_EXIT_CODE_AND_TRANSCRIPT_BOUND_NOT_REMOTE_RUNNER_ATTESTED",
    }
    return P19ExternalVerifierRegressionReceipt(
        **payload,
        canonical_command_argv=tuple(payload["canonical_command_argv"]),
        runtime_manifest=runtime,
        test_manifest=tests,
        receipt_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_p19_external_verifier_regression_receipt(
    path: Path,
    *,
    repository_root: Path,
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    if candidate.is_symlink() or not candidate.is_file():
        raise P19ExternalVerifierRegressionError("regression receipt must be a regular non-symlink file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19ExternalVerifierRegressionError("invalid verifier regression receipt JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19ExternalVerifierRegressionError("unexpected verifier regression receipt schema")
    if raw != canonical_json_bytes(doc) + b"\n":
        raise P19ExternalVerifierRegressionError("verifier regression receipt must use canonical JSON bytes")
    if doc.get("activation_authorized") is not False:
        raise P19ExternalVerifierRegressionError("regression receipt cannot itself authorize activation")

    keys = (
        "regression_generation", "source_commit", "source_tree", "canonical_command_argv",
        "runtime_manifest", "runtime_manifest_digest", "test_manifest", "test_manifest_digest",
        "method_map_digest", "stdout_path", "stdout_sha256", "stdout_bytes", "stderr_path",
        "stderr_sha256", "stderr_bytes", "exit_code", "all_regression_tests_passed",
        "execution_provenance_scope",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise P19ExternalVerifierRegressionError("verifier regression receipt payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("receipt_digest", doc.get("receipt_digest")):
        raise P19ExternalVerifierRegressionError("verifier regression receipt digest mismatch")
    if doc.get("regression_generation") != REGRESSION_GENERATION:
        raise P19ExternalVerifierRegressionError("verifier regression generation mismatch")
    _git_oid("source_commit", doc.get("source_commit"))
    _git_oid("source_tree", doc.get("source_tree"))
    if tuple(doc.get("canonical_command_argv", ())) != CANONICAL_REGRESSION_COMMAND:
        raise P19ExternalVerifierRegressionError("verifier regression command mismatch")
    if doc.get("exit_code") != 0 or doc.get("all_regression_tests_passed") is not True:
        raise P19ExternalVerifierRegressionError("verifier regression did not pass")
    if doc.get("execution_provenance_scope") != "RAW_EXIT_CODE_AND_TRANSCRIPT_BOUND_NOT_REMOTE_RUNNER_ATTESTED":
        raise P19ExternalVerifierRegressionError("verifier regression provenance scope mismatch")

    runtime = current_runtime_manifest(root)
    tests = current_test_manifest(root)
    if doc.get("runtime_manifest") != list(runtime):
        raise P19ExternalVerifierRegressionError("verifier runtime bytes differ from regression receipt")
    if doc.get("test_manifest") != list(tests):
        raise P19ExternalVerifierRegressionError("verifier regression test bytes differ from receipt")
    runtime_digest = sha256_bytes(canonical_json_bytes(list(runtime)))
    test_digest = sha256_bytes(canonical_json_bytes(list(tests)))
    if doc.get("runtime_manifest_digest") != runtime_digest:
        raise P19ExternalVerifierRegressionError("verifier runtime manifest digest mismatch")
    if doc.get("test_manifest_digest") != test_digest:
        raise P19ExternalVerifierRegressionError("verifier test manifest digest mismatch")
    if doc.get("method_map_digest") != method_map_digest():
        raise P19ExternalVerifierRegressionError("verifier method map differs from regression receipt")

    for role, allow_empty in (("stdout", False), ("stderr", True)):
        rel = _safe_rel(doc.get(f"{role}_path"), label=f"regression {role}")
        transcript = _repo_file(root, rel, label=f"regression {role}", allow_empty=allow_empty)
        if sha256_file(transcript) != _sha(f"{role}_sha256", doc.get(f"{role}_sha256")):
            raise P19ExternalVerifierRegressionError(f"regression {role} bytes differ from receipt")
        if transcript.stat().st_size != int(doc.get(f"{role}_bytes", -1)):
            raise P19ExternalVerifierRegressionError(f"regression {role} byte count mismatch")
    return doc
