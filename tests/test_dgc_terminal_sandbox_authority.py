from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from cwc.governance.sandbox_image_build import (
    SandboxImageBuildReceipt,
    sandbox_image_build_receipt_bytes,
)
from cwc.governance.sandbox_image_population import (
    freeze_sandbox_image_population,
    task_population_digest,
)
from cwc.governance.terminal_sandbox_authority import (
    TerminalSandboxAuthorityError,
    verify_terminal_sandbox_environment,
)


def _h(char: str) -> str:
    return char * 64


def _receipt() -> SandboxImageBuildReceipt:
    manifest_json = (
        '{"schemaVersion":2,'
        '"mediaType":"application/vnd.oci.image.manifest.v1+json",'
        '"config":{"mediaType":"application/vnd.oci.image.config.v1+json",'
        '"digest":"sha256:' + _h("2") + '","size":2},'
        '"layers":[]}'
    )
    digest = "sha256:" + hashlib.sha256(
        manifest_json.encode("utf-8")
    ).hexdigest()
    staging = "registry.example/dgc/task-a:dgc-test"
    image = "registry.example/dgc/task-a@" + digest
    command = [
        "<DOCKER>",
        "buildx",
        "build",
        "--platform",
        "linux/amd64",
        "--provenance=false",
        "--sbom=false",
        "--push",
        "--metadata-file",
        "<BUILD_METADATA_JSON>",
        "--tag",
        staging,
        "--no-cache",
        "--pull",
        "<FROZEN_TASK_ENVIRONMENT>",
    ]
    metadata_json = json.dumps(
        {"containerimage.digest": digest},
        separators=(",", ":"),
    )
    payload = {
        "family_id": "TERMINAL_BENCH_2_1",
        "task_id": "task-a",
        "platform": "linux/amd64",
        "task_source_sha256": _h("3"),
        "build_context_sha256": _h("4"),
        "dockerfile_sha256": _h("5"),
        "staging_reference": staging,
        "image_reference": image,
        "container_image_digest": digest,
        "docker_version": '{"Version":"28.0.0"}',
        "buildx_version": "github.com/docker/buildx v0.30.0",
        "build_command": command,
        "build_metadata_json": metadata_json,
        "registry_manifest_json": manifest_json,
    }
    return SandboxImageBuildReceipt(
        family_id=str(payload["family_id"]),
        task_id=str(payload["task_id"]),
        platform=str(payload["platform"]),
        task_source_sha256=str(payload["task_source_sha256"]),
        build_context_sha256=str(payload["build_context_sha256"]),
        dockerfile_sha256=str(payload["dockerfile_sha256"]),
        staging_reference=staging,
        image_reference=image,
        container_image_digest=digest,
        docker_version=str(payload["docker_version"]),
        buildx_version=str(payload["buildx_version"]),
        build_command=tuple(command),
        build_metadata_json=metadata_json,
        registry_manifest_json=manifest_json,
        receipt_digest=sha256_bytes(
            canonical_json_bytes(payload)
        ),
    )


def _authority(
    tmp_path: Path,
    *,
    receipt_digest_override: str | None = None,
):
    repo = tmp_path / "repo"
    manifests = repo / "eval_bundle" / "sandbox"
    receipts = manifests / "build-receipts"
    receipts.mkdir(parents=True)

    receipt = _receipt()
    receipt_path = receipts / "task-a.json"
    receipt_path.write_bytes(
        sandbox_image_build_receipt_bytes(receipt)
    )
    task_manifest = task_population_digest(["task-a"])
    population = freeze_sandbox_image_population(
        family_id="TERMINAL_BENCH_2_1",
        runtime="docker-linux-amd64",
        materialization_reference_digest=_h("1"),
        task_manifest_sha256=task_manifest,
        expected_task_count=1,
        bindings=[
            {
                "task_id": "task-a",
                "task_source_sha256": receipt.task_source_sha256,
                "build_context_sha256": receipt.build_context_sha256,
                "image_reference": receipt.image_reference,
                "container_image_digest": receipt.container_image_digest,
                "build_receipt_path": (
                    "eval_bundle/sandbox/build-receipts/task-a.json"
                ),
                "build_receipt_sha256": sha256_file(
                    receipt_path
                ),
                "build_receipt_digest": (
                    receipt_digest_override
                    or receipt.receipt_digest
                ),
            }
        ],
    )
    population_path = (
        manifests / "SANDBOX_IMAGE_POPULATION.json"
    )
    population_path.write_text(
        json.dumps(
            population.document,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    environment = {
        "schema": "DGC_ENVIRONMENT_MANIFEST_V2",
        "family_id": "TERMINAL_BENCH_2_1",
        "runtime": "docker-linux-amd64",
        "execution_mode": "PREBUILT_IMMUTABLE_OCI",
        "materialization_reference_digest": _h("1"),
        "task_manifest_sha256": task_manifest,
        "sandbox_image_population_path": (
            "eval_bundle/sandbox/SANDBOX_IMAGE_POPULATION.json"
        ),
        "sandbox_image_population_sha256": sha256_file(
            population_path
        ),
        "sandbox_image_population_digest": (
            population.population_digest
        ),
    }
    return repo, environment, population_path, receipt_path


def test_terminal_sandbox_authority_round_trip(
    tmp_path: Path,
):
    repo, environment, _population, _receipt_path = (
        _authority(tmp_path)
    )
    verified = verify_terminal_sandbox_environment(
        repository_root=repo,
        environment=environment,
    )
    binding = verified.resolve("task-a")
    assert binding.build_receipt_digest == _receipt().receipt_digest
    assert binding.image_reference.startswith(
        "registry.example/dgc/task-a@sha256:"
    )


def test_population_byte_tamper_fails_closed(
    tmp_path: Path,
):
    repo, environment, population, _receipt_path = (
        _authority(tmp_path)
    )
    population.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        TerminalSandboxAuthorityError,
        match="population bytes differ",
    ):
        verify_terminal_sandbox_environment(
            repository_root=repo,
            environment=environment,
        )


def test_build_receipt_byte_tamper_fails_closed(
    tmp_path: Path,
):
    repo, environment, _population, receipt_path = (
        _authority(tmp_path)
    )
    receipt_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        TerminalSandboxAuthorityError,
        match="receipt bytes differ",
    ):
        verify_terminal_sandbox_environment(
            repository_root=repo,
            environment=environment,
        )


def test_build_receipt_semantic_substitution_fails_closed(
    tmp_path: Path,
):
    repo, environment, _population, _receipt_path = (
        _authority(
            tmp_path,
            receipt_digest_override=_h("f"),
        )
    )
    with pytest.raises(
        TerminalSandboxAuthorityError,
        match="receipt semantic digest mismatch",
    ):
        verify_terminal_sandbox_environment(
            repository_root=repo,
            environment=environment,
        )


def test_population_symlink_path_fails_closed(
    tmp_path: Path,
):
    repo, environment, population, _receipt_path = (
        _authority(tmp_path)
    )
    real = population.with_name("population-real.json")
    population.rename(real)
    population.symlink_to(real)
    with pytest.raises(
        TerminalSandboxAuthorityError,
        match="symlink path rejected",
    ):
        verify_terminal_sandbox_environment(
            repository_root=repo,
            environment=environment,
        )
