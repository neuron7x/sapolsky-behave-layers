from __future__ import annotations

from dataclasses import asdict

import pytest

from cwc.governance.sandbox_image_population import (
    SandboxImagePopulationError,
    freeze_sandbox_image_population,
    task_population_digest,
    verify_sandbox_image_population_document,
)


def _h(char: str) -> str:
    return char * 64


def _rows() -> list[dict[str, object]]:
    return [
        {
            "task_id": "task-a",
            "task_source_sha256": _h("1"),
            "build_context_sha256": _h("2"),
            "image_reference": "registry.example/dgc/task-a@sha256:" + _h("3"),
            "container_image_digest": "sha256:" + _h("3"),
            "build_receipt_sha256": _h("4"),
        },
        {
            "task_id": "task-b",
            "task_source_sha256": _h("5"),
            "build_context_sha256": _h("6"),
            "image_reference": "registry.example/dgc/task-b@sha256:" + _h("7"),
            "container_image_digest": "sha256:" + _h("7"),
            "build_receipt_sha256": _h("8"),
        },
    ]


def _population():
    task_digest = task_population_digest(["task-a", "task-b"])
    return freeze_sandbox_image_population(
        family_id="TERMINAL_BENCH_2_1",
        runtime="docker-linux-amd64",
        materialization_reference_digest=_h("a"),
        task_manifest_sha256=task_digest,
        expected_task_count=2,
        bindings=_rows(),
    )


def test_population_round_trip_and_task_resolution():
    population = _population()
    verified = verify_sandbox_image_population_document(population.document)
    assert verified.population_digest == population.population_digest
    assert verified.resolve("task-a").container_image_digest == "sha256:" + _h("3")
    assert verified.resolve("task-b").image_reference.endswith("@sha256:" + _h("7"))


def test_missing_task_fails_closed():
    task_digest = task_population_digest(["task-a", "task-b"])
    with pytest.raises(SandboxImagePopulationError, match="task count mismatch"):
        freeze_sandbox_image_population(
            family_id="TERMINAL_BENCH_2_1",
            runtime="docker-linux-amd64",
            materialization_reference_digest=_h("a"),
            task_manifest_sha256=task_digest,
            expected_task_count=2,
            bindings=_rows()[:1],
        )


def test_duplicate_task_fails_closed():
    rows = _rows()
    rows[1]["task_id"] = "task-a"
    task_digest = task_population_digest(["task-a", "task-b"])
    with pytest.raises(SandboxImagePopulationError, match="duplicate"):
        freeze_sandbox_image_population(
            family_id="TERMINAL_BENCH_2_1",
            runtime="docker-linux-amd64",
            materialization_reference_digest=_h("a"),
            task_manifest_sha256=task_digest,
            expected_task_count=2,
            bindings=rows,
        )


def test_task_substitution_fails_closed():
    rows = _rows()
    rows[1]["task_id"] = "task-c"
    task_digest = task_population_digest(["task-a", "task-b"])
    with pytest.raises(SandboxImagePopulationError, match="task population differs"):
        freeze_sandbox_image_population(
            family_id="TERMINAL_BENCH_2_1",
            runtime="docker-linux-amd64",
            materialization_reference_digest=_h("a"),
            task_manifest_sha256=task_digest,
            expected_task_count=2,
            bindings=rows,
        )


@pytest.mark.parametrize(
    "reference",
    [
        "registry.example/dgc/task-a:latest",
        "registry.example/dgc/task-a:2026-09-27",
        "registry.example/dgc/task-a@sha256:" + _h("9"),
    ],
)
def test_nonmatching_or_mutable_image_reference_fails_closed(reference: str):
    rows = _rows()
    rows[0]["image_reference"] = reference
    task_digest = task_population_digest(["task-a", "task-b"])
    with pytest.raises(SandboxImagePopulationError, match="digest-pinned"):
        freeze_sandbox_image_population(
            family_id="TERMINAL_BENCH_2_1",
            runtime="docker-linux-amd64",
            materialization_reference_digest=_h("a"),
            task_manifest_sha256=task_digest,
            expected_task_count=2,
            bindings=rows,
        )


def test_population_digest_tamper_fails_closed():
    document = _population().document
    document["population_digest"] = _h("f")
    with pytest.raises(SandboxImagePopulationError, match="population digest mismatch"):
        verify_sandbox_image_population_document(document)


def test_population_cannot_self_claim_external_execution():
    document = _population().document
    document["external_execution_performed"] = True
    with pytest.raises(SandboxImagePopulationError, match="cannot claim external execution"):
        verify_sandbox_image_population_document(document)
