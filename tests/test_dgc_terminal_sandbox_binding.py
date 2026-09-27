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
from cwc.governance.terminal_sandbox_binding import (
    TerminalSandboxBindingError,
    bind_terminal_sandbox_generation,
)
from cwc.governance.terminal_sandbox_builder import BUILD_RECEIPT_SCHEMA
from cwc.governance.terminal_sandbox_generation import TerminalSandboxGenerationError


def _h(char: str) -> str:
    return char * 64


def _generation(tmp_path: Path) -> Path:
    task_manifest = task_population_digest(["task-a"])
    build_payload = {
        "schema": BUILD_RECEIPT_SCHEMA,
        "family_id": "TERMINAL_BENCH_2_1",
        "task_id": "task-a",
        "runtime": "docker-linux-amd64",
        "platform": "linux/amd64",
        "materialization_reference_digest": _h("1"),
        "materialized_task_manifest_sha256": task_manifest,
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
    build_digest = sha256_bytes(canonical_json_bytes(build_payload))
    population = freeze_sandbox_image_population(
        family_id="TERMINAL_BENCH_2_1",
        runtime="docker-linux-amd64",
        materialization_reference_digest=_h("1"),
        task_manifest_sha256=task_manifest,
        expected_task_count=1,
        bindings=[{
            "task_id": "task-a",
            "task_source_sha256": _h("3"),
            "build_context_sha256": _h("4"),
            "image_reference": "registry.example/dgc/tbench@sha256:" + _h("7"),
            "container_image_digest": "sha256:" + _h("7"),
            "build_receipt_sha256": build_digest,
        }],
    )

    root = tmp_path / "build-generation"
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
            json.dumps(
                {**build_payload, "receipt_sha256": build_digest},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        transaction.publish(
            receipt={
                "schema": "DGC_TERMINAL_SANDBOX_BUILD_GENERATION_RECEIPT_V1",
                "family_id": population.family_id,
                "runtime": population.runtime,
                "materialization_reference_digest": population.materialization_reference_digest,
                "task_manifest_sha256": population.task_manifest_sha256,
                "task_count": 1,
                "sandbox_image_population_digest": population.population_digest,
                "sandbox_image_population_sha256": sha256_file(population_path),
                "external_benchmark_execution_performed": False,
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


def test_binding_mints_repo_local_environment_v2(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "eval_bundle").mkdir(parents=True)
    generation = _generation(tmp_path)
    result = bind_terminal_sandbox_generation(
        generation_root=generation,
        repository_root=repo,
        output_root=Path("eval_bundle/terminal-sandbox-binding"),
    )
    assert result.environment_manifest_path.is_file()
    assert result.sandbox_image_population_path.is_file()
    environment = json.loads(result.environment_manifest_path.read_text(encoding="utf-8"))
    assert environment["schema"] == "DGC_ENVIRONMENT_MANIFEST_V2"
    assert environment["execution_mode"] == "PREBUILT_IMMUTABLE_OCI"
    assert environment["sandbox_image_population_path"] == (
        "eval_bundle/terminal-sandbox-binding/SANDBOX_IMAGE_POPULATION.json"
    )
    assert environment["sandbox_image_population_sha256"] == sha256_file(
        result.sandbox_image_population_path
    )
    assert environment["sandbox_image_population_digest"] == (
        result.sandbox_image_population_digest
    )


def test_binding_output_is_immutable(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "eval_bundle").mkdir(parents=True)
    generation = _generation(tmp_path)
    kwargs = {
        "generation_root": generation,
        "repository_root": repo,
        "output_root": Path("eval_bundle/terminal-sandbox-binding"),
    }
    bind_terminal_sandbox_generation(**kwargs)
    with pytest.raises(TerminalSandboxBindingError, match="immutable"):
        bind_terminal_sandbox_generation(**kwargs)


def test_binding_rejects_output_outside_eval_bundle(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    generation = _generation(tmp_path)
    with pytest.raises(TerminalSandboxBindingError, match="inside ignored eval_bundle"):
        bind_terminal_sandbox_generation(
            generation_root=generation,
            repository_root=repo,
            output_root=Path("outside"),
        )


def test_binding_rejects_tampered_generation(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "eval_bundle").mkdir(parents=True)
    generation = _generation(tmp_path)
    (generation / "SANDBOX_IMAGE_POPULATION.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(TerminalSandboxGenerationError, match="publication manifest mismatch"):
        bind_terminal_sandbox_generation(
            generation_root=generation,
            repository_root=repo,
            output_root=Path("eval_bundle/terminal-sandbox-binding"),
        )
