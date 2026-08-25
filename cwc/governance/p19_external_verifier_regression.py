from __future__ import annotations

import json
import subprocess
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

SCHEMA = "DGC_P19_EXTERNAL_VERIFIER_REGRESSION_RECEIPT_V3"
REGRESSION_GENERATION = "P19_EXTERNAL_VERIFIER_CANONICAL_REGRESSION_V3_FROZEN_SOURCE_DESCENDANT_REPLAY"
EXECUTION_PROVENANCE_SCOPE = (
    "GIT_BOUND_T_VERIFIER_RUNTIME_TESTS_EXIT_TRANSCRIPT_WITH_DESCENDANT_ACTIVATION_REPLAY_"
    "REMOTE_RUNNER_NOT_MACHINE_PROVEN"
)


class P19ExternalVerifierRegressionError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise P19ExternalVerifierRegressionError(f"git command failed: {' '.join(args)}") from exc


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise P19ExternalVerifierRegressionError(f"git command failed: {' '.join(args)}") from exc


def current_repository_identity(repository_root: Path) -> tuple[str, str]:
    root = Path(repository_root).resolve()
    commit = _git(root, "rev-parse", "HEAD").lower()
    tree = _git(root, "rev-parse", "HEAD^{tree}").lower()
    _git_oid("current source commit", commit)
    _git_oid("current source tree", tree)
    tracked_dirty = _git(root, "status", "--porcelain", "--untracked-files=no")
    if tracked_dirty:
        raise P19ExternalVerifierRegressionError("verifier regression requires a clean tracked Git worktree")
    return commit, tree


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


def _source_tree(root: Path, source_commit: str) -> str:
    return _git(root, "rev-parse", f"{source_commit}^{{tree}}").lower()


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise P19ExternalVerifierRegressionError("git ancestry check failed") from exc
    if result.returncode not in (0, 1):
        raise P19ExternalVerifierRegressionError("git ancestry check failed")
    return result.returncode == 0


def _verify_manifest_at_source(
    root: Path,
    source_commit: str,
    rows: object,
    *,
    label: str,
) -> None:
    if not isinstance(rows, list) or not rows:
        raise P19ExternalVerifierRegressionError(f"{label} manifest missing")
    for row in rows:
        if not isinstance(row, Mapping):
            raise P19ExternalVerifierRegressionError(f"{label} manifest row malformed")
        rel = _safe_rel(row.get("path"), label=f"{label} source path")
        expected_sha = _sha(f"{label} source sha256", row.get("sha256"))
        expected_bytes = int(row.get("bytes", -1))
        if expected_bytes <= 0:
            raise P19ExternalVerifierRegressionError(f"{label} source byte count invalid")
        blob = _git_bytes(root, "show", f"{source_commit}:{rel}")
        if len(blob) != expected_bytes or sha256_bytes(blob) != expected_sha:
            raise P19ExternalVerifierRegressionError(f"{label} bytes differ from frozen T_verifier Git blob")


def _verify_frozen_source_lineage(
    root: Path,
    *,
    source_commit: str,
    source_tree: str,
    current_commit: str,
    runtime_rows: object,
    test_rows: object,
    require_same_checkout: bool,
) -> None:
    observed_tree = _source_tree(root, source_commit)
    if observed_tree != source_tree:
        raise P19ExternalVerifierRegressionError("regression receipt source tree is not the tree of source commit")
    if require_same_checkout:
        if source_commit != current_commit:
            raise P19ExternalVerifierRegressionError("regression receipt source commit differs from current Git HEAD")
    elif not _is_ancestor(root, source_commit, current_commit):
        raise P19ExternalVerifierRegressionError("T_verifier is not an ancestor of current activation checkout")
    _verify_manifest_at_source(root, source_commit, runtime_rows, label="verifier runtime")
    _verify_manifest_at_source(root, source_commit, test_rows, label="verifier regression tests")


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
    observed_commit, observed_tree = current_repository_identity(root)
    if _git_oid("source_commit", source_commit) != observed_commit:
        raise P19ExternalVerifierRegressionError("declared regression source commit differs from current Git HEAD")
    if _git_oid("source_tree", source_tree) != observed_tree:
        raise P19ExternalVerifierRegressionError("declared regression source tree differs from current Git tree")
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
    runtime_digest = sha256_bytes(canonical_json_bytes(list(runtime)))
    test_digest = sha256_bytes(canonical_json_bytes(list(tests)))
    _verify_frozen_source_lineage(
        root,
        source_commit=observed_commit,
        source_tree=observed_tree,
        current_commit=observed_commit,
        runtime_rows=list(runtime),
        test_rows=list(tests),
        require_same_checkout=True,
    )
    payload: dict[str, object] = {
        "regression_generation": REGRESSION_GENERATION,
        "source_commit": observed_commit,
        "source_tree": observed_tree,
        "canonical_command_argv": list(CANONICAL_REGRESSION_COMMAND),
        "runtime_manifest": list(runtime),
        "runtime_manifest_digest": runtime_digest,
        "test_manifest": list(tests),
        "test_manifest_digest": test_digest,
        "method_map_digest": method_map_digest(),
        "stdout_path": stdout_rel,
        "stdout_sha256": sha256_file(stdout),
        "stdout_bytes": stdout.stat().st_size,
        "stderr_path": stderr_rel,
        "stderr_sha256": sha256_file(stderr),
        "stderr_bytes": stderr.stat().st_size,
        "exit_code": 0,
        "all_regression_tests_passed": True,
        "execution_provenance_scope": EXECUTION_PROVENANCE_SCOPE,
    }
    receipt_digest = sha256_bytes(canonical_json_bytes(payload))
    return P19ExternalVerifierRegressionReceipt(
        regression_generation=REGRESSION_GENERATION,
        source_commit=observed_commit,
        source_tree=observed_tree,
        canonical_command_argv=tuple(CANONICAL_REGRESSION_COMMAND),
        runtime_manifest=runtime,
        runtime_manifest_digest=runtime_digest,
        test_manifest=tests,
        test_manifest_digest=test_digest,
        method_map_digest=str(payload["method_map_digest"]),
        stdout_path=stdout_rel,
        stdout_sha256=str(payload["stdout_sha256"]),
        stdout_bytes=int(payload["stdout_bytes"]),
        stderr_path=stderr_rel,
        stderr_sha256=str(payload["stderr_sha256"]),
        stderr_bytes=int(payload["stderr_bytes"]),
        exit_code=0,
        all_regression_tests_passed=True,
        execution_provenance_scope=EXECUTION_PROVENANCE_SCOPE,
        receipt_digest=receipt_digest,
    )


def verify_p19_external_verifier_regression_receipt(
    path: Path,
    *,
    repository_root: Path,
    allow_descendant_checkout: bool = False,
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    current_commit, current_tree = current_repository_identity(root)
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

    source_commit = _git_oid("source_commit", doc.get("source_commit"))
    source_tree = _git_oid("source_tree", doc.get("source_tree"))
    _verify_frozen_source_lineage(
        root,
        source_commit=source_commit,
        source_tree=source_tree,
        current_commit=current_commit,
        runtime_rows=doc.get("runtime_manifest"),
        test_rows=doc.get("test_manifest"),
        require_same_checkout=not allow_descendant_checkout,
    )
    if not allow_descendant_checkout and source_tree != current_tree:
        raise P19ExternalVerifierRegressionError("regression receipt source tree differs from current Git tree")
    if tuple(doc.get("canonical_command_argv", ())) != CANONICAL_REGRESSION_COMMAND:
        raise P19ExternalVerifierRegressionError("verifier regression command mismatch")
    if doc.get("exit_code") != 0 or doc.get("all_regression_tests_passed") is not True:
        raise P19ExternalVerifierRegressionError("verifier regression did not pass")
    if doc.get("execution_provenance_scope") != EXECUTION_PROVENANCE_SCOPE:
        raise P19ExternalVerifierRegressionError("verifier regression provenance scope mismatch")

    runtime = current_runtime_manifest(root)
    tests = current_test_manifest(root)
    if doc.get("runtime_manifest") != list(runtime):
        raise P19ExternalVerifierRegressionError("verifier runtime bytes differ from frozen T_verifier/current checkout")
    if doc.get("test_manifest") != list(tests):
        raise P19ExternalVerifierRegressionError("verifier regression test bytes differ from frozen T_verifier/current checkout")
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
