from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
)
from cwc.governance.sandbox_image_population import task_population_digest
from cwc.governance.terminal_sandbox_builder import (
    TerminalSandboxBuildError,
    build_terminal_sandbox_population,
)


def _tree_digest(root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(file_manifest(root)))


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    tasks = tmp_path / "tasks"
    for task_id in ("task-a", "task-b"):
        environment = tasks / task_id / "environment"
        environment.mkdir(parents=True)
        (tasks / task_id / "task.toml").write_text(
            "[environment]\ncpus = 1\n",
            encoding="utf-8",
        )
        (tasks / task_id / "instruction.md").write_text(
            f"solve {task_id}\n",
            encoding="utf-8",
        )
        (environment / "Dockerfile").write_text(
            "FROM ubuntu:24.04\n",
            encoding="utf-8",
        )
    (tasks / "dataset.toml").write_text(
        "[dataset]\n"
        'name = "terminal-bench-test"\n'
        "\n"
        "[[tasks]]\n"
        'name = "task-a"\n'
        'digest = "sha256:' + "1" * 64 + '"\n'
        "\n"
        "[[tasks]]\n"
        'name = "task-b"\n'
        'digest = "sha256:' + "2" * 64 + '"\n',
        encoding="utf-8",
    )
    task_manifest = task_population_digest(["task-a", "task-b"])
    payload = {
        "schema": "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2",
        "subject_type": "DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2",
        "publication_manifest_sha256": "3" * 64,
        "payload_manifest_sha256": "4" * 64,
        "materialization_receipt_sha256": "5" * 64,
        "materialization_provenance_sha256": "6" * 64,
        "source_registry_sha256": "7" * 64,
        "materializer_sha256": "8" * 64,
        "repository_commit": "a" * 40,
        "repository_tree": "b" * 40,
        "family_bindings": [
            {
                "family_id": "SWE_BENCH_VERIFIED",
                "source_authority_digest": "9" * 64,
                "materialized_authority_digest": "a" * 64,
                "materialized_tree_sha256": "b" * 64,
                "materialized_task_manifest_sha256": "c" * 64,
                "expected_task_count": 500,
                "semantic_verification_digest": "d" * 64,
            },
            {
                "family_id": "TERMINAL_BENCH_2_1",
                "source_authority_digest": "e" * 64,
                "materialized_authority_digest": "f" * 64,
                "materialized_tree_sha256": _tree_digest(tasks),
                "materialized_task_manifest_sha256": task_manifest,
                "expected_task_count": 2,
                "semantic_verification_digest": "0" * 64,
            },
        ],
        "file_count": 10,
    }
    payload["reference_digest"] = sha256_bytes(canonical_json_bytes(payload))
    reference = tmp_path / "reference.json"
    reference.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return tasks, reference


class FakeDocker:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        cmd = list(command)
        self.commands.append(cmd)
        if cmd[1:3] == ["version", "--format"]:
            return SimpleNamespace(returncode=0, stdout=b'{"Client":{"Version":"test"}}', stderr=b"")
        if cmd[1] == "build":
            return SimpleNamespace(returncode=0, stdout=b"build-ok", stderr=b"")
        if cmd[1] == "push":
            return SimpleNamespace(returncode=0, stdout=b"push-ok", stderr=b"")
        if cmd[1:3] == ["image", "inspect"]:
            tag = cmd[3]
            task = "task-a" if "task-a-" in tag else "task-b"
            digest = "a" * 64 if task == "task-a" else "b" * 64
            repository = tag.rsplit(":", 1)[0]
            stdout = json.dumps([f"{repository}@sha256:{digest}"]).encode("utf-8")
            return SimpleNamespace(returncode=0, stdout=stdout, stderr=b"")
        raise AssertionError(cmd)


def test_builder_emits_exact_task_scoped_oci_population(tmp_path: Path):
    tasks, reference = _fixture(tmp_path)
    docker = FakeDocker()
    result = build_terminal_sandbox_population(
        materialized_tasks_root=tasks,
        materialization_reference_path=reference,
        registry_prefix="registry.example/dgc/terminal-bench-2-1",
        runner=docker,
    )
    assert result.population.expected_task_count == 2
    assert len(result.population.bindings) == 2
    assert result.population.resolve("task-a").container_image_digest == "sha256:" + "a" * 64
    assert result.population.resolve("task-b").container_image_digest == "sha256:" + "b" * 64
    assert all(row["external_benchmark_execution_performed"] is False for row in result.receipts)
    build_commands = [cmd for cmd in docker.commands if len(cmd) > 1 and cmd[1] == "build"]
    assert len(build_commands) == 2
    assert all("--pull" in cmd and "--platform" in cmd for cmd in build_commands)


def test_materialized_task_byte_substitution_is_rejected_before_docker(tmp_path: Path):
    tasks, reference = _fixture(tmp_path)
    (tasks / "task-a" / "instruction.md").write_text("tampered\n", encoding="utf-8")
    docker = FakeDocker()
    with pytest.raises(TerminalSandboxBuildError, match="task bytes differ"):
        build_terminal_sandbox_population(
            materialized_tasks_root=tasks,
            materialization_reference_path=reference,
            registry_prefix="registry.example/dgc/terminal-bench-2-1",
            runner=docker,
        )
    assert docker.commands == []


def test_registry_prefix_with_mutable_tag_is_rejected(tmp_path: Path):
    tasks, reference = _fixture(tmp_path)
    docker = FakeDocker()
    with pytest.raises(TerminalSandboxBuildError, match="must not contain a tag"):
        build_terminal_sandbox_population(
            materialized_tasks_root=tasks,
            materialization_reference_path=reference,
            registry_prefix="registry.example/dgc/terminal-bench-2-1:latest",
            runner=docker,
        )


def test_missing_repo_digest_fails_closed(tmp_path: Path):
    tasks, reference = _fixture(tmp_path)

    class MissingDigestDocker(FakeDocker):
        def __call__(self, command, **kwargs):
            cmd = list(command)
            if cmd[1:3] == ["image", "inspect"]:
                self.commands.append(cmd)
                return SimpleNamespace(returncode=0, stdout=b"[]", stderr=b"")
            return super().__call__(command, **kwargs)

    docker = MissingDigestDocker()
    with pytest.raises(TerminalSandboxBuildError, match="immutable repository digest"):
        build_terminal_sandbox_population(
            materialized_tasks_root=tasks,
            materialization_reference_path=reference,
            registry_prefix="registry.example/dgc/terminal-bench-2-1",
            runner=docker,
        )
