from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import (
    AtomicEvidenceGeneration,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from cwc.governance.sandbox_image_population import (
    freeze_sandbox_image_population,
    task_population_digest,
)
from cwc.governance.terminal_sandbox_builder import BUILD_RECEIPT_SCHEMA
from cwc.governance.terminal_sandbox_generation import (
    TerminalSandboxGenerationError,
    verify_terminal_sandbox_build_generation,
)


def _h(char: str) -> str:
    return char * 64


TASK_MANIFEST = task_population_digest(["task-a"])


def _build_receipt(*, receipt_sha_override: str | None = None) -> tuple[dict[str, object], str]:
    payload = {
        "schema": BUILD_RECEIPT_SCHEMA,
        "family_id": "TERMINAL_BENCH_2_1",
        "task_id": "task-a",
        "runtime": "docker-linux-amd64",
        "platform": "linux/amd64",
        "materialization_reference_digest": _h("1"),
        "materialized_task_manifest_sha256": TASK_MANIFEST,
        "task_source_sha256": _h("3"),
        "build_context_sha256": _h("4"),
        "dockerfile_sha256": _h("5"),
        "docker_version_evidence_sha256": _h("6"),
        "image_tag": "registry.example/dgc/tbench:task-a",
        "image_reference": "registry.example/dgc/tbench@sha256:" + _h("7"),
        "container_image_digest": "sha256:" + _h("7"),
        "build_stdout_sha256": _h("8"),
        "build_stderr_sha256": _h("9"),
        "push_stdout_sha256": _h("a"),
        "push_stderr_sha256": _h("b"),
        "inspect_stderr_sha256": _h("c"),
        "external_benchmark_execution_performed": False,
        "product_promotion_authorized": False,
    }
    digest = sha256_bytes(canonical_json_bytes(payload))
    return {**payload, "receipt_sha256": receipt_sha_override or digest}, digest


def _generation(
    tmp_path: Path,
    *,
    bad_build_receipt_digest: bool = False,
    extra_receipt: bool = False,
    execution_claim: bool = False,
) -> Path:
    receipt_doc, receipt_digest = _build_receipt(
        receipt_sha_override=_h("f") if bad_build_receipt_digest else None
    )
    population = freeze_sandbox_image_population(
        family_id="TERMINAL_BENCH_2_1",
        runtime="docker-linux-amd64",
        materialization_reference_digest=_h("1"),
        task_manifest_sha256=TASK_MANIFEST,
        expected_task_count=1,
        bindings=[{
            "task_id": "task-a",
            "task_source_sha256": _h("3"),
            "build_context_sha256": _h("4"),
            "image_reference": "registry.example/dgc/tbench@sha256:" + _h("7"),
            "container_image_digest": "sha256:" + _h("7"),
            "build_receipt_sha256": receipt_digest,
        }],
    )
    root = tmp_path / "generation"
    with AtomicEvidenceGeneration(root) as transaction:
        assert transaction.staging_root is not None
        staging = transaction.staging_root
        population_path = staging / "SANDBOX_IMAGE_POPULATION.json"
        population_path.write_text(
            json.dumps(population.document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        receipts = staging / "build-receipts"
        receipts.mkdir()
        (receipts / "task-a.json").write_text(
            json.dumps(receipt_doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if extra_receipt:
            (receipts / "extra.json").write_text(
                json.dumps(receipt_doc, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        transaction.publish(
            receipt={
                "schema": "DGC_TERMINAL_SANDBOX_BUILD_GENERATION_RECEIPT_V1",
                "family_id": population.family_id,
                "runtime": population.runtime,
                "materialization_reference_digest": population.materialization_reference_digest,
                "task_manifest_sha256": population.task_manifest_sha256,
                "task_count": population.expected_task_count,
                "sandbox_image_population_digest": population.population_digest,
                "sandbox_image_population_sha256": sha256_file(population_path),
                "external_benchmark_execution_performed": execution_claim,
                "product_promotion_authorized": False,
            },
            provenance={
                "schema": "DGC_TERMINAL_SANDBOX_BUILD_PROVENANCE_V1",
                "claim": "SANDBOX_IMAGE_BUILD_AND_PUSH_ONLY",
                "materialization_reference_sha256": _h("d"),
                "registry_prefix": "registry.example/dgc/tbench",
                "platform": "linux/amd64",
                "docker_executable": "docker",
                "external_benchmark_execution_performed": False,
                "product_promotion_authorized": False,
            },
        )
    return root


def test_verified_generation_round_trip(tmp_path: Path):
    root = _generation(tmp_path)
    verified = verify_terminal_sandbox_build_generation(root)
    assert verified.population.expected_task_count == 1
    assert verified.population.resolve("task-a").container_image_digest == "sha256:" + _h("7")
    assert verified.population_sha256 == sha256_file(root / "SANDBOX_IMAGE_POPULATION.json")
    assert len(verified.generation_digest) == 64


def test_build_receipt_semantic_digest_tamper_is_rejected(tmp_path: Path):
    root = _generation(tmp_path, bad_build_receipt_digest=True)
    with pytest.raises(TerminalSandboxGenerationError, match="build receipt digest mismatch"):
        verify_terminal_sandbox_build_generation(root)


def test_extra_build_receipt_is_rejected(tmp_path: Path):
    root = _generation(tmp_path, extra_receipt=True)
    with pytest.raises(TerminalSandboxGenerationError, match="receipt population differs"):
        verify_terminal_sandbox_build_generation(root)


def test_generation_cannot_claim_benchmark_execution(tmp_path: Path):
    root = _generation(tmp_path, execution_claim=True)
    with pytest.raises(TerminalSandboxGenerationError, match="cannot claim benchmark execution"):
        verify_terminal_sandbox_build_generation(root)


def test_population_byte_tamper_is_rejected_by_publication_manifest(tmp_path: Path):
    root = _generation(tmp_path)
    population = root / "SANDBOX_IMAGE_POPULATION.json"
    population.write_text("{}\n", encoding="utf-8")
    with pytest.raises(TerminalSandboxGenerationError, match="publication manifest mismatch"):
        verify_terminal_sandbox_build_generation(root)
