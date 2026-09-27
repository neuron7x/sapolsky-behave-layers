from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from cwc.governance.external_materialization import parse_terminal_dataset_manifest
from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
    sha256_file,
)
from cwc.governance.sandbox_image_population import (
    SandboxImageBinding,
    SandboxImagePopulation,
    freeze_sandbox_image_population,
    task_population_digest,
)

REFERENCE_SCHEMA = "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2"
FAMILY = "TERMINAL_BENCH_2_1"
BUILD_RECEIPT_SCHEMA = "DGC_TERMINAL_SANDBOX_BUILD_RECEIPT_V1"
_REGISTRY_RE = re.compile(r"^[A-Za-z0-9._:/-]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TerminalSandboxBuildError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TerminalSandboxBuildResult:
    population: SandboxImagePopulation
    receipts: tuple[dict[str, object], ...]


def _tree_digest(root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(file_manifest(root)))


def _run(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> tuple[bytes, bytes]:
    try:
        proc = runner(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TerminalSandboxBuildError(
            f"container command failed to start or timed out: {command[0]}"
        ) from exc
    stdout = bytes(proc.stdout or b"")
    stderr = bytes(proc.stderr or b"")
    if proc.returncode != 0:
        raise TerminalSandboxBuildError(
            f"container command exited nonzero ({proc.returncode}): {' '.join(command[:3])}"
        )
    return stdout, stderr


def _reference_binding(path: Path) -> tuple[str, Mapping[str, object]]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise TerminalSandboxBuildError("materialization reference must be a regular file")
    try:
        document = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalSandboxBuildError("invalid materialization reference JSON") from exc
    if not isinstance(document, dict) or document.get("schema") != REFERENCE_SCHEMA:
        raise TerminalSandboxBuildError("unexpected materialization reference schema")
    if document.get("subject_type") != "DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2":
        raise TerminalSandboxBuildError("unexpected materialization reference subject type")
    reference_digest = str(document.get("reference_digest", "")).strip().lower()
    payload = dict(document)
    payload.pop("reference_digest", None)
    if not _SHA256_RE.fullmatch(reference_digest):
        raise TerminalSandboxBuildError("materialization reference digest malformed")
    if sha256_bytes(canonical_json_bytes(payload)) != reference_digest:
        raise TerminalSandboxBuildError("materialization reference digest mismatch")
    rows = document.get("family_bindings")
    if not isinstance(rows, list):
        raise TerminalSandboxBuildError("materialization family bindings missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("family_id") == FAMILY]
    if len(matches) != 1:
        raise TerminalSandboxBuildError("exactly one Terminal-Bench materialization binding required")
    return reference_digest, matches[0]


def _registry_prefix(value: str) -> str:
    text = str(value).strip().rstrip("/")
    if (
        not text
        or "@" in text
        or any(ch.isspace() for ch in text)
        or _REGISTRY_RE.fullmatch(text) is None
    ):
        raise TerminalSandboxBuildError("registry_prefix must be an untagged OCI repository name")
    tail = text.rsplit("/", 1)[-1]
    if ":" in tail:
        raise TerminalSandboxBuildError("registry_prefix must not contain a tag")
    return text


def _tag_slug(task_id: str) -> str:
    slug = re.sub(r"[^a-z0-9_.-]+", "-", task_id.lower()).strip("-.")
    if not slug:
        raise TerminalSandboxBuildError("task id cannot be converted to an OCI tag")
    return slug[:80]


def _repo_digest(stdout: bytes, registry_prefix: str) -> str:
    try:
        values = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalSandboxBuildError("docker image inspect RepoDigests is invalid JSON") from exc
    if not isinstance(values, list):
        raise TerminalSandboxBuildError("docker image inspect RepoDigests must be a list")
    prefix = registry_prefix + "@sha256:"
    matches = sorted(
        str(value).strip()
        for value in values
        if isinstance(value, str) and str(value).strip().startswith(prefix)
    )
    if len(matches) != 1:
        raise TerminalSandboxBuildError(
            "pushed image must expose exactly one matching immutable repository digest"
        )
    digest = matches[0].rsplit("@", 1)[-1]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise TerminalSandboxBuildError("repository digest is not sha256")
    return matches[0]


def build_terminal_sandbox_population(
    *,
    materialized_tasks_root: Path,
    materialization_reference_path: Path,
    registry_prefix: str,
    runtime: str = "docker-linux-amd64",
    platform: str = "linux/amd64",
    docker_executable: str = "docker",
    command_timeout_seconds: float = 3600.0,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> TerminalSandboxBuildResult:
    tasks_root = Path(materialized_tasks_root)
    if tasks_root.is_symlink() or not tasks_root.is_dir():
        raise TerminalSandboxBuildError("materialized tasks root must be a real directory")
    tasks_root = tasks_root.resolve()
    dataset = tasks_root / "dataset.toml"
    if dataset.is_symlink() or not dataset.is_file():
        raise TerminalSandboxBuildError("Terminal-Bench dataset.toml missing")

    reference_digest, binding = _reference_binding(Path(materialization_reference_path))
    try:
        expected_count = int(binding.get("expected_task_count"))
    except (TypeError, ValueError) as exc:
        raise TerminalSandboxBuildError("materialization expected_task_count malformed") from exc
    expected_task_manifest = str(
        binding.get("materialized_task_manifest_sha256", "")
    ).strip().lower()
    if not _SHA256_RE.fullmatch(expected_task_manifest):
        raise TerminalSandboxBuildError("materialization task manifest digest malformed")
    expected_tree = str(binding.get("materialized_tree_sha256", "")).strip().lower()
    if not _SHA256_RE.fullmatch(expected_tree):
        raise TerminalSandboxBuildError("materialization tree digest malformed")
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
        raise TerminalSandboxBuildError("Terminal-Bench dataset manifest verification failed") from exc
    task_ids = tuple(name for name, _digest in manifest.tasks)
    if task_population_digest(task_ids) != expected_task_manifest:
        raise TerminalSandboxBuildError(
            "materialized Terminal task population differs from evidence reference"
        )

    registry = _registry_prefix(registry_prefix)
    runtime_id = str(runtime).strip()
    platform_id = str(platform).strip()
    docker = str(docker_executable).strip()
    if not runtime_id or not platform_id or not docker:
        raise TerminalSandboxBuildError("runtime/platform/docker executable required")
    if command_timeout_seconds <= 0:
        raise TerminalSandboxBuildError("command_timeout_seconds must be > 0")

    version_stdout, version_stderr = _run(
        [docker, "version", "--format", "{{json .}}"],
        timeout_seconds=command_timeout_seconds,
        runner=runner,
    )
    docker_version_evidence = sha256_bytes(version_stdout + b"\x00" + version_stderr)

    receipts: list[dict[str, object]] = []
    bindings: list[SandboxImageBinding] = []
    for task_id in task_ids:
        task_root = tasks_root / task_id
        environment = task_root / "environment"
        dockerfile = environment / "Dockerfile"
        if task_root.is_symlink() or not task_root.is_dir():
            raise TerminalSandboxBuildError(f"{task_id}: task root missing or symlinked")
        if environment.is_symlink() or not environment.is_dir():
            raise TerminalSandboxBuildError(f"{task_id}: environment directory missing")
        if dockerfile.is_symlink() or not dockerfile.is_file():
            raise TerminalSandboxBuildError(f"{task_id}: Dockerfile missing")

        task_sha = _tree_digest(task_root)
        context_sha = _tree_digest(environment)
        dockerfile_sha = sha256_file(dockerfile)
        tag = f"{registry}:{_tag_slug(task_id)}-{context_sha[:16]}"

        build_stdout, build_stderr = _run(
            [
                docker,
                "build",
                "--pull",
                "--platform",
                platform_id,
                "--tag",
                tag,
                str(environment),
            ],
            timeout_seconds=command_timeout_seconds,
            runner=runner,
        )
        push_stdout, push_stderr = _run(
            [docker, "push", tag],
            timeout_seconds=command_timeout_seconds,
            runner=runner,
        )
        inspect_stdout, inspect_stderr = _run(
            [docker, "image", "inspect", tag, "--format", "{{json .RepoDigests}}"],
            timeout_seconds=command_timeout_seconds,
            runner=runner,
        )
        image_reference = _repo_digest(inspect_stdout, registry)
        image_digest = image_reference.rsplit("@", 1)[-1]

        receipt_payload = {
            "schema": BUILD_RECEIPT_SCHEMA,
            "family_id": FAMILY,
            "task_id": task_id,
            "runtime": runtime_id,
            "platform": platform_id,
            "materialization_reference_digest": reference_digest,
            "materialized_task_manifest_sha256": expected_task_manifest,
            "task_source_sha256": task_sha,
            "build_context_sha256": context_sha,
            "dockerfile_sha256": dockerfile_sha,
            "docker_version_evidence_sha256": docker_version_evidence,
            "image_tag": tag,
            "image_reference": image_reference,
            "container_image_digest": image_digest,
            "build_stdout_sha256": sha256_bytes(build_stdout),
            "build_stderr_sha256": sha256_bytes(build_stderr),
            "push_stdout_sha256": sha256_bytes(push_stdout),
            "push_stderr_sha256": sha256_bytes(push_stderr),
            "inspect_stderr_sha256": sha256_bytes(inspect_stderr),
            "external_benchmark_execution_performed": False,
            "product_promotion_authorized": False,
        }
        receipt_sha = sha256_bytes(canonical_json_bytes(receipt_payload))
        receipt = {**receipt_payload, "receipt_sha256": receipt_sha}
        receipts.append(receipt)
        bindings.append(
            SandboxImageBinding(
                task_id=task_id,
                task_source_sha256=task_sha,
                build_context_sha256=context_sha,
                image_reference=image_reference,
                container_image_digest=image_digest,
                build_receipt_sha256=receipt_sha,
            )
        )

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
