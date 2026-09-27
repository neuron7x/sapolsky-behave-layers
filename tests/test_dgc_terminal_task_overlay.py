from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
)
from cwc.governance.sandbox_image_population import SandboxImageBinding
from cwc.governance.terminal_task_overlay import (
    TerminalTaskOverlayError,
    prepare_terminal_task_overlay,
)


def _tree_digest(root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(file_manifest(root)))


def _fixture(tmp_path: Path) -> tuple[Path, SandboxImageBinding]:
    task = tmp_path / "source" / "task-a"
    (task / "environment").mkdir(parents=True)
    (task / "instruction.md").write_text("solve it\n", encoding="utf-8")
    (task / "task.toml").write_text(
        "[environment]\n"
        "cpus = 2\n"
        "memory_mb = 1024\n"
        "\n"
        "[verifier]\n"
        "timeout_sec = 30\n",
        encoding="utf-8",
    )
    (task / "environment" / "Dockerfile").write_text(
        "FROM ubuntu:24.04\nWORKDIR /workspace\n",
        encoding="utf-8",
    )
    digest = "3" * 64
    binding = SandboxImageBinding(
        task_id="task-a",
        task_source_sha256=_tree_digest(task),
        build_context_sha256=_tree_digest(task / "environment"),
        image_reference="registry.example/dgc/task-a@sha256:" + digest,
        container_image_digest="sha256:" + digest,
        build_receipt_sha256="4" * 64,
    )
    return task, binding


def test_overlay_changes_only_environment_docker_image(tmp_path: Path):
    task, binding = _fixture(tmp_path)
    receipt = prepare_terminal_task_overlay(
        task_id="task-a",
        task_root=task,
        destination_root=tmp_path / "overlay",
        binding=binding,
    )
    staged = tmp_path / "overlay" / "task-a"
    parsed = staged.joinpath("task.toml").read_text(encoding="utf-8")
    assert f'docker_image = "{binding.image_reference}"' in parsed
    assert staged.joinpath("instruction.md").read_text(encoding="utf-8") == "solve it\n"
    assert staged.joinpath("environment", "Dockerfile").read_text(encoding="utf-8").startswith(
        "FROM ubuntu:24.04"
    )
    assert receipt.source_task_sha256 == binding.task_source_sha256
    assert receipt.source_build_context_sha256 == binding.build_context_sha256
    assert receipt.container_image_digest == binding.container_image_digest
    assert receipt.overlay_digest


def test_overlay_preserves_existing_task_semantics(tmp_path: Path):
    task, binding = _fixture(tmp_path)
    before = task.joinpath("task.toml").read_text(encoding="utf-8")
    prepare_terminal_task_overlay(
        task_id="task-a",
        task_root=task,
        destination_root=tmp_path / "overlay",
        binding=binding,
    )
    after = (tmp_path / "overlay" / "task-a" / "task.toml").read_text(encoding="utf-8")
    assert "[verifier]\ntimeout_sec = 30" in after
    assert "docker_image" not in before


def test_source_task_substitution_fails_closed(tmp_path: Path):
    task, binding = _fixture(tmp_path)
    (task / "instruction.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(TerminalTaskOverlayError, match="source task bytes differ"):
        prepare_terminal_task_overlay(
            task_id="task-a",
            task_root=task,
            destination_root=tmp_path / "overlay",
            binding=binding,
        )


def test_build_context_substitution_fails_closed(tmp_path: Path):
    task, binding = _fixture(tmp_path)
    changed = SandboxImageBinding(
        task_id=binding.task_id,
        task_source_sha256=binding.task_source_sha256,
        build_context_sha256="9" * 64,
        image_reference=binding.image_reference,
        container_image_digest=binding.container_image_digest,
        build_receipt_sha256=binding.build_receipt_sha256,
    )
    with pytest.raises(TerminalTaskOverlayError, match="build context"):
        prepare_terminal_task_overlay(
            task_id="task-a",
            task_root=task,
            destination_root=tmp_path / "overlay",
            binding=changed,
        )


def test_task_identity_substitution_fails_closed(tmp_path: Path):
    task, binding = _fixture(tmp_path)
    with pytest.raises(TerminalTaskOverlayError, match="task identity differs"):
        prepare_terminal_task_overlay(
            task_id="task-b",
            task_root=task,
            destination_root=tmp_path / "overlay",
            binding=binding,
        )


def test_escaping_task_symlink_fails_closed(tmp_path: Path):
    task, binding = _fixture(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    os.symlink(outside, task / "escape")
    rebound = SandboxImageBinding(
        task_id=binding.task_id,
        task_source_sha256=_tree_digest(task),
        build_context_sha256=binding.build_context_sha256,
        image_reference=binding.image_reference,
        container_image_digest=binding.container_image_digest,
        build_receipt_sha256=binding.build_receipt_sha256,
    )
    with pytest.raises(TerminalTaskOverlayError, match="symlink escapes"):
        prepare_terminal_task_overlay(
            task_id="task-a",
            task_root=task,
            destination_root=tmp_path / "overlay",
            binding=rebound,
        )


def test_duplicate_environment_table_fails_closed(tmp_path: Path):
    task, binding = _fixture(tmp_path)
    task_toml = task / "task.toml"
    task_toml.write_text(
        task_toml.read_text(encoding="utf-8") + "\n[environment]\ncpus = 4\n",
        encoding="utf-8",
    )
    rebound = SandboxImageBinding(
        task_id=binding.task_id,
        task_source_sha256=_tree_digest(task),
        build_context_sha256=binding.build_context_sha256,
        image_reference=binding.image_reference,
        container_image_digest=binding.container_image_digest,
        build_receipt_sha256=binding.build_receipt_sha256,
    )
    with pytest.raises(TerminalTaskOverlayError):
        prepare_terminal_task_overlay(
            task_id="task-a",
            task_root=task,
            destination_root=tmp_path / "overlay",
            binding=rebound,
        )
