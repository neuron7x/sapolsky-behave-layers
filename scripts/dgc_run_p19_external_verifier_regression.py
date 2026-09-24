from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_python_runtime import inspect_python_runtime
from cwc.governance.p19_external_verification_contract import CANONICAL_REGRESSION_COMMAND
from cwc.governance.p19_external_verifier_regression import (
    build_p19_external_verifier_regression_receipt,
)

DEFAULT_OUTPUT_DIR = "artifacts/dgc-product-v1/generated/verifier-regression"


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"git command failed: {' '.join(args)}") from exc


def _write_immutable(path: Path, data: bytes, *, allow_empty: bool) -> None:
    if not allow_empty and not data:
        raise RuntimeError(f"refusing to write empty required regression subject: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _resolve_canonical_python() -> Path:
    command_name = CANONICAL_REGRESSION_COMMAND[0]
    candidate = shutil.which(command_name)
    if not candidate:
        raise RuntimeError(f"canonical verifier regression interpreter unavailable: {command_name}")
    resolved = Path(candidate).resolve()
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise RuntimeError("canonical verifier regression interpreter path invalid")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the exact canonical P19 external-verifier regression suite at immutable T_verifier "
            "with a content-addressed CPython 3.10.x runtime and emit a raw receipt. This command never "
            "activates Plan V4; activation requires separate dual-external-signature authority."
        )
    )
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    root = Path(args.repository_root).resolve()
    output = Path(args.output_dir)
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("regression output directory escapes repository") from exc
    if output.exists():
        raise RuntimeError("regression output directory already exists; immutable replay requires a fresh path")

    source_commit = _git(root, "rev-parse", "HEAD")
    source_tree = _git(root, "rev-parse", "HEAD^{tree}")
    tracked_dirty = _git(root, "status", "--porcelain", "--untracked-files=no")
    if tracked_dirty:
        raise RuntimeError("canonical verifier regression requires a clean tracked Git worktree")

    python_executable = _resolve_canonical_python()
    python_runtime = inspect_python_runtime(python_executable)
    executed_argv = [str(python_executable), *CANONICAL_REGRESSION_COMMAND[1:]]

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(root) if not existing_pythonpath else f"{root}{os.pathsep}{existing_pythonpath}"
    try:
        completed = subprocess.run(
            executed_argv,
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("canonical verifier regression process could not start") from exc

    stdout_path = output / "stdout.bin"
    stderr_path = output / "stderr.bin"
    _write_immutable(stdout_path, completed.stdout, allow_empty=False)
    _write_immutable(stderr_path, completed.stderr, allow_empty=True)
    if completed.returncode != 0:
        print(f"DGC-P19-VERIFIER-REGRESSION: FAIL exit={completed.returncode}")
        print(f"DGC-P19-VERIFIER-PYTHON-RUNTIME-DIGEST: {python_runtime.runtime_digest}")
        print(f"DGC-P19-VERIFIER-REGRESSION-STDOUT: {stdout_path.relative_to(root).as_posix()}")
        print(f"DGC-P19-VERIFIER-REGRESSION-STDERR: {stderr_path.relative_to(root).as_posix()}")
        return int(completed.returncode) if int(completed.returncode) > 0 else 1

    receipt = build_p19_external_verifier_regression_receipt(
        repository_root=root,
        source_commit=source_commit,
        source_tree=source_tree,
        command_argv=CANONICAL_REGRESSION_COMMAND,
        stdout_path=stdout_path.relative_to(root),
        stderr_path=stderr_path.relative_to(root),
        exit_code=completed.returncode,
        python_runtime_identity=python_runtime.document,
    )
    receipt_path = output / "receipt.json"
    _write_immutable(
        receipt_path,
        canonical_json_bytes(receipt.document) + b"\n",
        allow_empty=False,
    )
    print("DGC-P19-VERIFIER-REGRESSION: PASS")
    print(f"DGC-P19-VERIFIER-T_VERIFIER-COMMIT: {source_commit}")
    print(f"DGC-P19-VERIFIER-T_VERIFIER-TREE: {source_tree}")
    print(f"DGC-P19-VERIFIER-PYTHON: {python_runtime.implementation} {python_runtime.version_major}.{python_runtime.version_minor}.{python_runtime.version_micro}")
    print(f"DGC-P19-VERIFIER-PYTHON-RUNTIME-DIGEST: {python_runtime.runtime_digest}")
    print(f"DGC-P19-VERIFIER-PYTHON-EXECUTABLE-SHA256: {python_runtime.executable_sha256}")
    print(f"DGC-P19-VERIFIER-REGRESSION-RECEIPT: {receipt_path.relative_to(root).as_posix()}")
    print(f"DGC-P19-VERIFIER-REGRESSION-RECEIPT-DIGEST: {receipt.receipt_digest}")
    print("DGC-P19-VERIFIER-PLAN-V4-ACTIVATION-AUTHORIZED: false")
    print("DGC-P19-VERIFIER-NEXT: obtain two distinct external signatures over the exact receipt attestation bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
