from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from cwc.governance.external_materialization import parse_terminal_dataset_manifest
from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
)
from cwc.governance.sandbox_image_build import (
    SandboxImageBuildReceipt,
    build_and_push_terminal_task_image,
    sandbox_image_build_receipt_bytes,
)
from cwc.governance.sandbox_image_population import (
    SandboxImageBinding,
    SandboxImagePopulation,
    freeze_sandbox_image_population,
    task_population_digest,
)

REFERENCE_SCHEMA = "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2"
FAMILY = "TERMINAL_BENCH_2_1"
RUNTIME = "docker-linux-amd64"
PLATFORM = "linux/amd64"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TerminalSandboxBuildError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TerminalSandboxBuildResult:
    population: SandboxImagePopulation
    receipts: tuple[SandboxImageBuildReceipt, ...]


def _tree_digest(root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(file_manifest(root)))


def _reference_binding(path: Path) -> tuple[str, Mapping[str, object]]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise TerminalSandboxBuildError(
            "materialization reference must be a regular file"
        )
    try:
        document = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalSandboxBuildError(
            "invalid materialization reference JSON"
        ) from exc
    if not isinstance(document, dict) or document.get("schema") != REFERENCE_SCHEMA:
        raise TerminalSandboxBuildError(
            "unexpected materialization reference schema"
        )
    if document.get("subject_type") != "DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2":
        raise TerminalSandboxBuildError(
            "unexpected materialization reference subject type"
        )
    reference_digest = str(document.get("reference_digest", "")).strip().lower()
    payload = dict(document)
    payload.pop("reference_digest", None)
    if not _SHA256_RE.fullmatch(reference_digest):
        raise TerminalSandboxBuildError(
            "materialization reference digest malformed"
        )
    if sha256_bytes(canonical_json_bytes(payload)) != reference_digest:
        raise TerminalSandboxBuildError(
            "materialization reference digest mismatch"
        )
    rows = document.get("family_bindings")
    if not isinstance(rows, list):
        raise TerminalSandboxBuildError(
            "materialization family bindings missing"
        )
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping) and row.get("family_id") == FAMILY
    ]
    if len(matches) != 1:
        raise TerminalSandboxBuildError(
            "exactly one Terminal-Bench materialization binding required"
        )
    return reference_digest, matches[0]


def _receipt_prefix(value: str) -> Path:
    path = Path(str(value).strip())
    if not str(value).strip() or path.is_absolute() or ".." in path.parts:
        raise TerminalSandboxBuildError(
            "receipt_path_prefix must be a safe repository-relative path"
        )
    return path


def build_terminal_sandbox_population(
    *,
    materialized_tasks_root: Path,
    materialization_reference_path: Path,
    registry_prefix: str,
    receipt_path_prefix: str,
    runtime: str = RUNTIME,
    platform: str = PLATFORM,
    docker_executable: str = "docker",
    command_timeout_seconds: float = 3600.0,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> TerminalSandboxBuildResult:
    tasks_root = Path(materialized_tasks_root)
    if tasks_root.is_symlink() or not tasks_root.is_dir():
        raise TerminalSandboxBuildError(
            "materialized tasks root must be a real directory"
        )
    tasks_root = tasks_root.resolve()
    dataset = tasks_root / "dataset.toml"
    if dataset.is_symlink() or not dataset.is_file():
        raise TerminalSandboxBuildError(
            "Terminal-Bench dataset.toml missing"
        )

    reference_digest, binding = _reference_binding(
        Path(materialization_reference_path)
    )
    try:
        expected_count = int(binding.get("expected_task_count"))
    except (TypeError, ValueError) as exc:
        raise TerminalSandboxBuildError(
            "materialization expected_task_count malformed"
        ) from exc
    expected_task_manifest = str(
        binding.get("materialized_task_manifest_sha256", "")
    ).strip().lower()
    if not _SHA256_RE.fullmatch(expected_task_manifest):
        raise TerminalSandboxBuildError(
            "materialization task manifest digest malformed"
        )
    expected_tree = str(
        binding.get("materialized_tree_sha256", "")
    ).strip().lower()
    if not _SHA256_RE.fullmatch(expected_tree):
        raise TerminalSandboxBuildError(
            "materialization tree digest malformed"
        )
    observed_tree = _tree_digest(tasks_root)
    if observed_tree != expected_tree:
        raise TerminalSandboxBuildError(
            "materialized Terminal task bytes differ from evidence reference"
        )

    try:
        manifest = parse_terminal_dataset_manifest(
            dataset.read_text(encoding="utf-8"),
            expected_count=expected_count,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise TerminalSandboxBuildError(
            "Terminal-Bench dataset manifest verification failed"
        ) from exc
    task_ids = tuple(name for name, _digest in manifest.tasks)
    if task_population_digest(task_ids) != expected_task_manifest:
        raise TerminalSandboxBuildError(
            "materialized Terminal task population differs from evidence reference"
        )

    runtime_id = str(runtime).strip()
    platform_id = str(platform).strip()
    docker = str(docker_executable).strip()
    if runtime_id != RUNTIME:
        raise TerminalSandboxBuildError(
            f"runtime must be frozen to {RUNTIME}"
        )
    if platform_id != PLATFORM:
        raise TerminalSandboxBuildError(
            f"platform must be frozen to {PLATFORM}"
        )
    if not docker:
        raise TerminalSandboxBuildError("docker executable required")
    if command_timeout_seconds <= 0:
        raise TerminalSandboxBuildError(
            "command_timeout_seconds must be > 0"
        )
    receipt_prefix = _receipt_prefix(receipt_path_prefix)

    receipts: list[SandboxImageBuildReceipt] = []
    bindings: list[SandboxImageBinding] = []
    for task_id in task_ids:
        task_root = tasks_root / task_id
        try:
            receipt = build_and_push_terminal_task_image(
                task_id=task_id,
                task_root=task_root,
                registry_prefix=registry_prefix,
                docker_command=docker,
                platform=platform_id,
                command_timeout_seconds=command_timeout_seconds,
                runner=runner,
            )
        except Exception as exc:
            if isinstance(exc, TerminalSandboxBuildError):
                raise
            raise TerminalSandboxBuildError(
                f"{task_id}: sandbox image build failed"
            ) from exc

        receipt_bytes = sandbox_image_build_receipt_bytes(receipt)
        receipt_path = (receipt_prefix / f"{task_id}.json").as_posix()
        bindings.append(
            SandboxImageBinding(
                task_id=task_id,
                task_source_sha256=receipt.task_source_sha256,
                build_context_sha256=receipt.build_context_sha256,
                image_reference=receipt.image_reference,
                container_image_digest=receipt.container_image_digest,
                build_receipt_path=receipt_path,
                build_receipt_sha256=sha256_bytes(receipt_bytes),
                build_receipt_digest=receipt.receipt_digest,
            )
        )
        receipts.append(receipt)

    population = freeze_sandbox_image_population(
        family_id=FAMILY,
        runtime=runtime_id,
        materialization_reference_digest=reference_digest,
        task_manifest_sha256=expected_task_manifest,
        expected_task_count=expected_count,
        bindings=bindings,
    )
    return TerminalSandboxBuildResult(
        population=population,
        receipts=tuple(receipts),
    )
