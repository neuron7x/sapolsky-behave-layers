from __future__ import annotations

import copy
import os
import re
import shutil
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
    sha256_file,
)
from cwc.governance.sandbox_image_population import SandboxImageBinding

SCHEMA = "DGC_TERMINAL_TASK_OCI_OVERLAY_V1"
_ENVIRONMENT_HEADER_RE = re.compile(r"^\s*\[environment\]\s*(?:#.*)?$")
_TABLE_HEADER_RE = re.compile(r"^\s*\[")
_DOCKER_IMAGE_RE = re.compile(r"^\s*docker_image\s*=")


class TerminalTaskOverlayError(RuntimeError):
    pass


def _tree_digest(root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(file_manifest(root)))


def _reject_escaping_symlinks(root: Path) -> None:
    resolved_root = root.resolve()
    for rel, object_type, _mode, _size, _digest in file_manifest(root):
        if object_type != "symlink":
            continue
        path = root / rel
        target = os.readlink(path)
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise TerminalTaskOverlayError(
                f"task symlink escapes task root: {rel}"
            ) from exc


def _semantic_toml(text: str) -> dict[str, object]:
    try:
        parsed = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        raise TerminalTaskOverlayError("invalid task.toml") from exc
    if not isinstance(parsed, dict):
        raise TerminalTaskOverlayError("task.toml must decode to a table")
    return parsed


def _patch_environment_docker_image(text: str, image_reference: str) -> str:
    if any(ch in image_reference for ch in ('"', "\\", "\x00", "\n", "\r", " ")):
        raise TerminalTaskOverlayError("unsafe immutable image reference")
    original = _semantic_toml(text)
    environment = original.get("environment")
    if not isinstance(environment, dict):
        raise TerminalTaskOverlayError("task.toml requires [environment] table")

    lines = text.splitlines(keepends=True)
    environment_headers = [
        index for index, line in enumerate(lines) if _ENVIRONMENT_HEADER_RE.match(line.rstrip("\r\n"))
    ]
    if len(environment_headers) != 1:
        raise TerminalTaskOverlayError("task.toml requires exactly one [environment] table")
    start = environment_headers[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _TABLE_HEADER_RE.match(lines[index]):
            end = index
            break
    docker_rows = [
        index
        for index in range(start + 1, end)
        if _DOCKER_IMAGE_RE.match(lines[index])
    ]
    replacement = f'docker_image = "{image_reference}"\n'
    if len(docker_rows) > 1:
        raise TerminalTaskOverlayError("duplicate environment.docker_image")
    if docker_rows:
        current = lines[docker_rows[0]]
        newline = "\r\n" if current.endswith("\r\n") else "\n"
        lines[docker_rows[0]] = replacement.rstrip("\n") + newline
    else:
        lines.insert(start + 1, replacement)

    patched = "".join(lines)
    patched_doc = _semantic_toml(patched)
    patched_environment = patched_doc.get("environment")
    if not isinstance(patched_environment, dict):
        raise TerminalTaskOverlayError("patched task.toml lost [environment]")
    if patched_environment.get("docker_image") != image_reference:
        raise TerminalTaskOverlayError("patched docker_image does not equal frozen OCI reference")

    expected = copy.deepcopy(original)
    expected_environment = expected.get("environment")
    if not isinstance(expected_environment, dict):
        raise TerminalTaskOverlayError("task.toml environment disappeared")
    expected_environment["docker_image"] = image_reference
    if patched_doc != expected:
        raise TerminalTaskOverlayError(
            "task overlay modified semantics beyond environment.docker_image"
        )
    return patched


@dataclass(frozen=True, slots=True)
class TerminalTaskOverlayReceipt:
    task_id: str
    source_task_sha256: str
    source_build_context_sha256: str
    image_reference: str
    container_image_digest: str
    build_receipt_sha256: str
    original_task_toml_sha256: str
    patched_task_toml_sha256: str
    staged_task_sha256: str
    overlay_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "semantic_delta": "environment.docker_image_only",
            "force_build_required": False,
            "external_execution_performed": False,
            "product_promotion_authorized": False,
        }


def prepare_terminal_task_overlay(
    *,
    task_id: str,
    task_root: Path,
    destination_root: Path,
    binding: SandboxImageBinding,
) -> TerminalTaskOverlayReceipt:
    task = str(task_id).strip()
    if not task or task != binding.task_id:
        raise TerminalTaskOverlayError("task identity differs from sandbox image binding")
    source = Path(task_root)
    if source.is_symlink() or not source.is_dir():
        raise TerminalTaskOverlayError("source task root must be a real directory")
    source = source.resolve()
    _reject_escaping_symlinks(source)

    task_toml = source / "task.toml"
    environment = source / "environment"
    if task_toml.is_symlink() or not task_toml.is_file():
        raise TerminalTaskOverlayError("source task.toml must be a regular file")
    if environment.is_symlink() or not environment.is_dir():
        raise TerminalTaskOverlayError("source task environment must be a real directory")

    source_task_digest = _tree_digest(source)
    source_context_digest = _tree_digest(environment)
    if source_task_digest != binding.task_source_sha256:
        raise TerminalTaskOverlayError("source task bytes differ from sandbox image binding")
    if source_context_digest != binding.build_context_sha256:
        raise TerminalTaskOverlayError(
            "source environment bytes differ from sandbox build context"
        )

    destination_parent = Path(destination_root)
    if destination_parent.exists() and destination_parent.is_symlink():
        raise TerminalTaskOverlayError("destination root symlink rejected")
    destination_parent.mkdir(parents=True, exist_ok=True)
    destination = destination_parent / task
    if destination.exists() or destination.is_symlink():
        raise TerminalTaskOverlayError("task overlay destination must not pre-exist")
    shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)
    _reject_escaping_symlinks(destination)

    staged_toml = destination / "task.toml"
    original_toml_sha = sha256_file(task_toml)
    original_text = staged_toml.read_text(encoding="utf-8")
    patched_text = _patch_environment_docker_image(original_text, binding.image_reference)
    staged_toml.write_text(patched_text, encoding="utf-8")
    patched_toml_sha = sha256_file(staged_toml)
    if patched_toml_sha == original_toml_sha and binding.image_reference not in original_text:
        raise TerminalTaskOverlayError("task overlay failed to change docker image semantics")

    source_rows = {row[0]: row for row in file_manifest(source)}
    staged_rows = {row[0]: row for row in file_manifest(destination)}
    if set(source_rows) != set(staged_rows):
        raise TerminalTaskOverlayError("task overlay file population changed")
    for path, source_row in source_rows.items():
        if path == "task.toml":
            continue
        if staged_rows[path] != source_row:
            raise TerminalTaskOverlayError(f"task overlay changed frozen file: {path}")

    staged_task_digest = _tree_digest(destination)
    payload = {
        "task_id": task,
        "source_task_sha256": source_task_digest,
        "source_build_context_sha256": source_context_digest,
        "image_reference": binding.image_reference,
        "container_image_digest": binding.container_image_digest,
        "build_receipt_sha256": binding.build_receipt_sha256,
        "original_task_toml_sha256": original_toml_sha,
        "patched_task_toml_sha256": patched_toml_sha,
        "staged_task_sha256": staged_task_digest,
        "semantic_delta": "environment.docker_image_only",
        "force_build_required": False,
    }
    overlay_digest = sha256_bytes(canonical_json_bytes(payload))
    return TerminalTaskOverlayReceipt(
        task_id=task,
        source_task_sha256=source_task_digest,
        source_build_context_sha256=source_context_digest,
        image_reference=binding.image_reference,
        container_image_digest=binding.container_image_digest,
        build_receipt_sha256=binding.build_receipt_sha256,
        original_task_toml_sha256=original_toml_sha,
        patched_task_toml_sha256=patched_toml_sha,
        staged_task_sha256=staged_task_digest,
        overlay_digest=overlay_digest,
    )
