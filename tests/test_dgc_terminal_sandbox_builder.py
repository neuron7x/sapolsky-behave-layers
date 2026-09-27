from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
)
from cwc.governance.sandbox_image_build import (
    sandbox_image_build_receipt_bytes,
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


class FakeBuildx:
    def __init__(self, *, wrong_digest: bool = False) -> None:
        self.commands: list[list[str]] = []
        self.wrong_digest = wrong_digest
        self.manifests = {
            "task-a": (
                b'{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json",'
                b'"config":{"mediaType":"application/vnd.oci.image.config.v1+json",'
                b'"digest":"sha256:' + b"1" * 64 + b'","size":2},"layers":[]}'
            ),
            "task-b": (
                b'{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json",'
                b'"config":{"mediaType":"application/vnd.oci.image.config.v1+json",'
                b'"digest":"sha256:' + b"2" * 64 + b'","size":2},"layers":[]}'
            ),
        }

    def _task(self, value: str) -> str:
        if "/task-a" in value:
            return "task-a"
        if "/task-b" in value:
            return "task-b"
        raise AssertionError(value)

    def __call__(self, command, **kwargs):
        cmd = list(command)
        self.commands.append(cmd)
        if cmd[1:2] == ["version"]:
            return SimpleNamespace(
                returncode=0,
                stdout=b'{"Version":"28.0.0"}',
                stderr=b"",
            )
        if cmd[1:3] == ["buildx", "version"]:
            return SimpleNamespace(
                returncode=0,
                stdout=b"github.com/docker/buildx v0.30.0",
                stderr=b"",
            )
        if cmd[1:3] == ["buildx", "build"]:
            tag = cmd[cmd.index("--tag") + 1]
            task_id = self._task(tag)
            digest = "sha256:" + hashlib.sha256(
                self.manifests[task_id]
            ).hexdigest()
            if self.wrong_digest and task_id == "task-a":
                digest = "sha256:" + "9" * 64
            metadata = Path(
                cmd[cmd.index("--metadata-file") + 1]
            )
            metadata.write_text(
                json.dumps({"containerimage.digest": digest}),
                encoding="utf-8",
            )
            return SimpleNamespace(
                returncode=0,
                stdout=b"build-ok",
                stderr=b"",
            )
        if cmd[1:4] == ["buildx", "imagetools", "inspect"]:
            reference = cmd[-1]
            task_id = self._task(reference)
            return SimpleNamespace(
                returncode=0,
                stdout=self.manifests[task_id],
                stderr=b"",
            )
        raise AssertionError(cmd)


def test_builder_emits_exact_task_scoped_oci_population(tmp_path: Path):
    tasks, reference = _fixture(tmp_path)
    docker = FakeBuildx()
    result = build_terminal_sandbox_population(
        materialized_tasks_root=tasks,
        materialization_reference_path=reference,
        registry_prefix="registry.example/dgc/terminal-bench-2-1",
        receipt_path_prefix="eval_bundle/test/build-receipts",
        runner=docker,
    )
    assert result.population.expected_task_count == 2
    assert len(result.population.bindings) == 2
    assert len(result.receipts) == 2
    for receipt in result.receipts:
        binding = result.population.resolve(receipt.task_id)
        assert binding.container_image_digest == receipt.container_image_digest
        assert binding.image_reference == receipt.image_reference
        assert binding.build_receipt_digest == receipt.receipt_digest
        assert binding.build_receipt_sha256 == sha256_bytes(
            sandbox_image_build_receipt_bytes(receipt)
        )
        assert binding.build_receipt_path.endswith(
            f"build-receipts/{receipt.task_id}.json"
        )
        assert receipt.document["benchmark_execution_performed"] is False
    build_commands = [
        cmd
        for cmd in docker.commands
        if len(cmd) > 2 and cmd[1:3] == ["buildx", "build"]
    ]
    assert len(build_commands) == 2
    assert all(
        "--pull" in cmd
        and "--no-cache" in cmd
        and "--provenance=false" in cmd
        and "--sbom=false" in cmd
        and "--push" in cmd
        for cmd in build_commands
    )


def test_materialized_task_byte_substitution_is_rejected_before_docker(
    tmp_path: Path,
):
    tasks, reference = _fixture(tmp_path)
    (tasks / "task-a" / "instruction.md").write_text(
        "tampered\n",
        encoding="utf-8",
    )
    docker = FakeBuildx()
    with pytest.raises(
        TerminalSandboxBuildError,
        match="task bytes differ",
    ):
        build_terminal_sandbox_population(
            materialized_tasks_root=tasks,
            materialization_reference_path=reference,
            registry_prefix="registry.example/dgc/terminal-bench-2-1",
            receipt_path_prefix="eval_bundle/test/build-receipts",
            runner=docker,
        )
    assert docker.commands == []


def test_registry_prefix_with_mutable_tag_is_rejected(tmp_path: Path):
    tasks, reference = _fixture(tmp_path)
    docker = FakeBuildx()
    with pytest.raises(
        TerminalSandboxBuildError,
        match="sandbox image build failed",
    ):
        build_terminal_sandbox_population(
            materialized_tasks_root=tasks,
            materialization_reference_path=reference,
            registry_prefix="registry.example/dgc/terminal-bench-2-1:latest",
            receipt_path_prefix="eval_bundle/test/build-receipts",
            runner=docker,
        )


def test_registry_digest_mismatch_fails_closed(tmp_path: Path):
    tasks, reference = _fixture(tmp_path)
    docker = FakeBuildx(wrong_digest=True)
    with pytest.raises(
        TerminalSandboxBuildError,
        match="sandbox image build failed",
    ):
        build_terminal_sandbox_population(
            materialized_tasks_root=tasks,
            materialization_reference_path=reference,
            registry_prefix="registry.example/dgc/terminal-bench-2-1",
            receipt_path_prefix="eval_bundle/test/build-receipts",
            runner=docker,
        )


def test_receipt_path_prefix_must_be_repository_relative(tmp_path: Path):
    tasks, reference = _fixture(tmp_path)
    docker = FakeBuildx()
    with pytest.raises(
        TerminalSandboxBuildError,
        match="receipt_path_prefix",
    ):
        build_terminal_sandbox_population(
            materialized_tasks_root=tasks,
            materialization_reference_path=reference,
            registry_prefix="registry.example/dgc/terminal-bench-2-1",
            receipt_path_prefix="/tmp/receipts",
            runner=docker,
        )
