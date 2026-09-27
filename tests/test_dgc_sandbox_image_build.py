from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from cwc.governance.sandbox_image_build import (
    SandboxImageBuildError,
    build_and_push_terminal_task_image,
    verify_sandbox_image_build_receipt_document,
)


def _task(tmp_path: Path) -> Path:
    task = tmp_path / "task-a"
    environment = task / "environment"
    environment.mkdir(parents=True)
    (task / "task.toml").write_text("[environment]\ncpus = 2\n", encoding="utf-8")
    (task / "instruction.md").write_text("solve\n", encoding="utf-8")
    (environment / "Dockerfile").write_text(
        "FROM ubuntu:24.04\nWORKDIR /workspace\n",
        encoding="utf-8",
    )
    return task


def _runner(manifest: bytes, *, metadata_digest: str | None = None):
    digest = "sha256:" + hashlib.sha256(manifest).hexdigest()
    metadata_digest = metadata_digest or digest

    def run(argv, **kwargs):
        argv = list(argv)
        if argv[1:2] == ["version"]:
            return SimpleNamespace(returncode=0, stdout=b'{"Version":"28.0.0"}', stderr=b"")
        if argv[1:3] == ["buildx", "version"]:
            return SimpleNamespace(returncode=0, stdout=b"github.com/docker/buildx v0.30.0", stderr=b"")
        if argv[1:3] == ["buildx", "build"]:
            metadata = Path(argv[argv.index("--metadata-file") + 1])
            metadata.write_text(
                json.dumps({"containerimage.digest": metadata_digest}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout=b"build-ok", stderr=b"")
        if argv[1:4] == ["buildx", "imagetools", "inspect"]:
            assert argv[4] == "--raw"
            assert "@sha256:" in argv[5]
            return SimpleNamespace(returncode=0, stdout=manifest, stderr=b"")
        raise AssertionError(f"unexpected command: {argv}")

    return run, digest


def test_build_receipt_binds_registry_digest_and_frozen_builder_policy(tmp_path: Path):
    task = _task(tmp_path)
    manifest = (
        b'{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json",'
        b'"config":{"mediaType":"application/vnd.oci.image.config.v1+json",'
        b'"digest":"sha256:' + b"1" * 64 + b'","size":2},"layers":[]}'
    )
    runner, digest = _runner(manifest)
    receipt = build_and_push_terminal_task_image(
        task_id="task-a",
        task_root=task,
        registry_prefix="ghcr.io/neuron7x/dgc-terminal",
        runner=runner,
    )
    verified = verify_sandbox_image_build_receipt_document(receipt.document)
    assert verified.container_image_digest == digest
    assert verified.image_reference == f"ghcr.io/neuron7x/dgc-terminal/task-a@{digest}"
    assert "--no-cache" in verified.build_command
    assert "--pull" in verified.build_command
    assert "--provenance=false" in verified.build_command
    assert verified.document["benchmark_execution_performed"] is False
    assert verified.document["product_promotion_authorized"] is False


def test_registry_manifest_digest_mismatch_fails_closed(tmp_path: Path):
    task = _task(tmp_path)
    manifest = b'{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json"}'
    runner, _ = _runner(manifest, metadata_digest="sha256:" + "9" * 64)
    with pytest.raises(SandboxImageBuildError, match="registry-resolved manifest digest differs"):
        build_and_push_terminal_task_image(
            task_id="task-a",
            task_root=task,
            registry_prefix="ghcr.io/neuron7x/dgc-terminal",
            runner=runner,
        )


def test_receipt_tamper_fails_closed(tmp_path: Path):
    task = _task(tmp_path)
    manifest = b'{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json"}'
    runner, _ = _runner(manifest)
    receipt = build_and_push_terminal_task_image(
        task_id="task-a",
        task_root=task,
        registry_prefix="ghcr.io/neuron7x/dgc-terminal",
        runner=runner,
    )
    doc = receipt.document
    doc["docker_version"] = "tampered"
    with pytest.raises(SandboxImageBuildError, match="receipt digest mismatch"):
        verify_sandbox_image_build_receipt_document(doc)


def test_mutable_or_malformed_registry_prefix_is_rejected(tmp_path: Path):
    task = _task(tmp_path)
    manifest = b'{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json"}'
    runner, _ = _runner(manifest)
    with pytest.raises(SandboxImageBuildError, match="registry_prefix"):
        build_and_push_terminal_task_image(
            task_id="task-a",
            task_root=task,
            registry_prefix="https://ghcr.io/neuron7x/dgc-terminal",
            runner=runner,
        )
