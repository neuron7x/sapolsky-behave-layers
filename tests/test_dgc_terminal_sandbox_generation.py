from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import (
    AtomicEvidenceGeneration,
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
from cwc.governance.terminal_sandbox_generation import (
    TerminalSandboxGenerationError,
    verify_terminal_sandbox_build_generation,
)


def _h(char: str) -> str:
    return char * 64


TASK_MANIFEST = task_population_digest(["task-a"])


def _build_receipt() -> SandboxImageBuildReceipt:
    manifest_json = (
        '{"schemaVersion":2,'
        '"mediaType":"application/vnd.oci.image.manifest.v1+json",'
        '"config":{"mediaType":"application/vnd.oci.image.config.v1+json",'
        '"digest":"sha256:' + _h("2") + '","size":2},'
        '"layers":[]}'
    )
    image_digest = "sha256:" + hashlib.sha256(
        manifest_json.encode("utf-8")
    ).hexdigest()
    staging = "registry.example/dgc/tbench/task-a:dgc-test"
    image_reference = (
        "registry.example/dgc/tbench/task-a@" + image_digest
    )
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
        {"containerimage.digest": image_digest},
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
        "image_reference": image_reference,
        "container_image_digest": image_digest,
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
        staging_reference=str(payload["staging_reference"]),
        image_reference=str(payload["image_reference"]),
        container_image_digest=str(payload["container_image_digest"]),
        docker_version=str(payload["docker_version"]),
        buildx_version=str(payload["buildx_version"]),
        build_command=tuple(command),
        build_metadata_json=metadata_json,
        registry_manifest_json=manifest_json,
        receipt_digest=sha256_bytes(
            canonical_json_bytes(payload)
        ),
    )


def _generation(
    tmp_path: Path,
    *,
    tamper_receipt_after_publish: bool = False,
    extra_receipt: bool = False,
    execution_claim: bool = False,
    population_path_override: str | None = None,
) -> Path:
    build_receipt = _build_receipt()
    root = tmp_path / "generation"
    receipt_rel = (
        "eval_bundle/test-generation/build-receipts/task-a.json"
    )
    receipt_bytes = sandbox_image_build_receipt_bytes(
        build_receipt
    )
    population = freeze_sandbox_image_population(
        family_id="TERMINAL_BENCH_2_1",
        runtime="docker-linux-amd64",
        materialization_reference_digest=_h("1"),
        task_manifest_sha256=TASK_MANIFEST,
        expected_task_count=1,
        bindings=[
            {
                "task_id": "task-a",
                "task_source_sha256": (
                    build_receipt.task_source_sha256
                ),
                "build_context_sha256": (
                    build_receipt.build_context_sha256
                ),
                "image_reference": (
                    build_receipt.image_reference
                ),
                "container_image_digest": (
                    build_receipt.container_image_digest
                ),
                "build_receipt_path": receipt_rel,
                "build_receipt_sha256": sha256_bytes(
                    receipt_bytes
                ),
                "build_receipt_digest": (
                    build_receipt.receipt_digest
                ),
            }
        ],
    )

    with AtomicEvidenceGeneration(root) as transaction:
        assert transaction.staging_root is not None
        staging = transaction.staging_root
        receipts = staging / "build-receipts"
        receipts.mkdir()
        (receipts / "task-a.json").write_bytes(
            receipt_bytes
        )
        if extra_receipt:
            (receipts / "extra.json").write_bytes(
                receipt_bytes
            )

        population_path = (
            staging / "SANDBOX_IMAGE_POPULATION.json"
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
            "family_id": population.family_id,
            "runtime": population.runtime,
            "execution_mode": "PREBUILT_IMMUTABLE_OCI",
            "materialization_reference_digest": (
                population.materialization_reference_digest
            ),
            "task_manifest_sha256": (
                population.task_manifest_sha256
            ),
            "sandbox_image_population_path": (
                population_path_override
                or (
                    "eval_bundle/test-generation/"
                    "SANDBOX_IMAGE_POPULATION.json"
                )
            ),
            "sandbox_image_population_sha256": (
                sha256_file(population_path)
            ),
            "sandbox_image_population_digest": (
                population.population_digest
            ),
        }
        environment_path = (
            staging / "ENVIRONMENT_MANIFEST.json"
        )
        environment_path.write_text(
            json.dumps(
                environment,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        transaction.publish(
            receipt={
                "schema": (
                    "DGC_TERMINAL_SANDBOX_BUILD_"
                    "GENERATION_RECEIPT_V2"
                ),
                "family_id": population.family_id,
                "runtime": population.runtime,
                "platform": "linux/amd64",
                "repository_commit": "a" * 40,
                "repository_tree": "b" * 40,
                "materialization_reference_digest": (
                    population.materialization_reference_digest
                ),
                "task_manifest_sha256": (
                    population.task_manifest_sha256
                ),
                "task_count": 1,
                "sandbox_image_population_digest": (
                    population.population_digest
                ),
                "sandbox_image_population_sha256": (
                    sha256_file(population_path)
                ),
                "environment_manifest_sha256": (
                    sha256_file(environment_path)
                ),
                "image_builds_performed": True,
                "external_benchmark_execution_performed": (
                    execution_claim
                ),
                "confirmatory_execution_authorized": False,
                "product_promotion_authorized": False,
            },
            provenance={
                "schema": (
                    "DGC_TERMINAL_SANDBOX_BUILD_"
                    "PROVENANCE_V2"
                ),
                "claim": "SANDBOX_IMAGE_BUILD_AND_PUSH_ONLY",
                "repository_commit": "a" * 40,
                "repository_tree": "b" * 40,
                "materialization_reference_path": (
                    "eval_bundle/materialization-reference.json"
                ),
                "materialization_reference_sha256": _h("6"),
                "registry_prefix": (
                    "registry.example/dgc/tbench"
                ),
                "platform": "linux/amd64",
                "runtime": "docker-linux-amd64",
                "docker_executable": "docker",
                "single_task_builder_sha256": _h("7"),
                "population_builder_sha256": _h("8"),
                "builder_cli_sha256": _h("9"),
                "external_benchmark_execution_performed": False,
                "product_promotion_authorized": False,
            },
        )

    if tamper_receipt_after_publish:
        (root / "build-receipts" / "task-a.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
    return root


def test_verified_generation_round_trip(tmp_path: Path):
    root = _generation(tmp_path)
    verified = verify_terminal_sandbox_build_generation(
        root
    )
    assert verified.population.expected_task_count == 1
    assert (
        verified.population.resolve(
            "task-a"
        ).container_image_digest
        == _build_receipt().container_image_digest
    )
    assert verified.population_sha256 == sha256_file(
        root / "SANDBOX_IMAGE_POPULATION.json"
    )
    assert verified.environment_sha256 == sha256_file(
        root / "ENVIRONMENT_MANIFEST.json"
    )
    assert len(verified.generation_digest) == 64


def test_build_receipt_byte_tamper_is_rejected(
    tmp_path: Path,
):
    root = _generation(
        tmp_path,
        tamper_receipt_after_publish=True,
    )
    with pytest.raises(
        TerminalSandboxGenerationError,
        match="publication manifest mismatch",
    ):
        verify_terminal_sandbox_build_generation(root)


def test_extra_build_receipt_is_rejected(tmp_path: Path):
    root = _generation(tmp_path, extra_receipt=True)
    with pytest.raises(
        TerminalSandboxGenerationError,
        match="receipt population differs",
    ):
        verify_terminal_sandbox_build_generation(root)


def test_generation_cannot_claim_benchmark_execution(
    tmp_path: Path,
):
    root = _generation(
        tmp_path,
        execution_claim=True,
    )
    with pytest.raises(
        TerminalSandboxGenerationError,
        match="external_benchmark_execution_performed",
    ):
        verify_terminal_sandbox_build_generation(root)


def test_population_byte_tamper_is_rejected_by_publication_manifest(
    tmp_path: Path,
):
    root = _generation(tmp_path)
    population = root / "SANDBOX_IMAGE_POPULATION.json"
    population.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        TerminalSandboxGenerationError,
        match="publication manifest mismatch",
    ):
        verify_terminal_sandbox_build_generation(root)


def test_environment_byte_tamper_is_rejected_by_publication_manifest(
    tmp_path: Path,
):
    root = _generation(tmp_path)
    environment = root / "ENVIRONMENT_MANIFEST.json"
    environment.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        TerminalSandboxGenerationError,
        match="publication manifest mismatch",
    ):
        verify_terminal_sandbox_build_generation(root)


def test_escaping_declared_population_path_is_rejected(
    tmp_path: Path,
):
    root = _generation(
        tmp_path,
        population_path_override="../SANDBOX_IMAGE_POPULATION.json",
    )
    with pytest.raises(
        TerminalSandboxGenerationError,
        match="safe repository-relative",
    ):
        verify_terminal_sandbox_build_generation(root)
