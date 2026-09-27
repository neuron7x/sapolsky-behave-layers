from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import (
    AtomicEvidenceGeneration,
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
    sha256_file,
)
from cwc.governance.sandbox_image_build import (
    SandboxImageBuildError,
    verify_sandbox_image_build_receipt_document,
)
from cwc.governance.sandbox_image_population import (
    EXECUTION_MODE,
    SandboxImagePopulation,
    SandboxImagePopulationError,
    verify_sandbox_image_population_document,
)

GENERATION_RECEIPT_SCHEMA = "DGC_TERMINAL_SANDBOX_BUILD_GENERATION_RECEIPT_V2"
GENERATION_PROVENANCE_SCHEMA = "DGC_TERMINAL_SANDBOX_BUILD_PROVENANCE_V2"
ENVIRONMENT_SCHEMA = "DGC_ENVIRONMENT_MANIFEST_V2"
FAMILY = "TERMINAL_BENCH_2_1"
PLATFORM = "linux/amd64"


class TerminalSandboxGenerationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedTerminalSandboxGeneration:
    population: SandboxImagePopulation
    population_sha256: str
    environment_sha256: str
    payload_manifest_sha256: str
    publication_manifest_sha256: str
    generation_digest: str


def _read_json(path: Path, *, schema: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise TerminalSandboxGenerationError(
            f"missing regular JSON file: {path.name}"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalSandboxGenerationError(
            f"invalid JSON file: {path.name}"
        ) from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise TerminalSandboxGenerationError(
            f"unexpected schema for {path.name}"
        )
    return value


def _manifest_rows(
    rows: object,
) -> tuple[tuple[str, str, int, int, str], ...]:
    if not isinstance(rows, list):
        raise TerminalSandboxGenerationError(
            "generation manifest files must be a list"
        )
    normalized: list[tuple[str, str, int, int, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise TerminalSandboxGenerationError(
                "invalid generation manifest row"
            )
        path = str(row.get("path", ""))
        object_type = str(row.get("type", ""))
        try:
            mode = int(row.get("mode"))
            size = int(row.get("bytes"))
        except (TypeError, ValueError) as exc:
            raise TerminalSandboxGenerationError(
                "manifest mode/bytes malformed"
            ) from exc
        digest = str(row.get("sha256", "")).strip().lower()
        if (
            not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or object_type not in {"file", "symlink"}
            or mode < 0
            or mode > 0o7777
            or size < 0
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise TerminalSandboxGenerationError(
                "invalid generation manifest file row"
            )
        if path in seen:
            raise TerminalSandboxGenerationError(
                "duplicate generation manifest path"
            )
        seen.add(path)
        normalized.append(
            (path, object_type, mode, size, digest)
        )
    return tuple(sorted(normalized))


def _verify_environment(
    *,
    path: Path,
    population: SandboxImagePopulation,
    population_sha256: str,
) -> tuple[str, str]:
    environment = _read_json(path, schema=ENVIRONMENT_SCHEMA)
    expected = {
        "family_id": population.family_id,
        "runtime": population.runtime,
        "execution_mode": EXECUTION_MODE,
        "materialization_reference_digest": (
            population.materialization_reference_digest
        ),
        "task_manifest_sha256": population.task_manifest_sha256,
        "sandbox_image_population_sha256": population_sha256,
        "sandbox_image_population_digest": population.population_digest,
    }
    for key, value in expected.items():
        if environment.get(key) != value:
            raise TerminalSandboxGenerationError(
                f"environment {key} differs from verified population"
            )
    population_path = str(
        environment.get("sandbox_image_population_path", "")
    ).strip()
    declared_path = Path(population_path)
    if (
        not population_path
        or declared_path.is_absolute()
        or ".." in declared_path.parts
        or declared_path.name != "SANDBOX_IMAGE_POPULATION.json"
    ):
        raise TerminalSandboxGenerationError(
            "environment population path must be safe repository-relative SANDBOX_IMAGE_POPULATION.json"
        )
    return sha256_file(path), population_path


def _verify_build_receipt(
    *,
    path: Path,
    population: SandboxImagePopulation,
    task_id: str,
    expected_binding_path: str,
) -> None:
    if path.is_symlink() or not path.is_file():
        raise TerminalSandboxGenerationError(
            f"{task_id}: build receipt missing"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalSandboxGenerationError(
            f"{task_id}: invalid build receipt JSON"
        ) from exc
    if not isinstance(raw, Mapping):
        raise TerminalSandboxGenerationError(
            f"{task_id}: build receipt must be a JSON object"
        )
    try:
        receipt = verify_sandbox_image_build_receipt_document(raw)
    except SandboxImageBuildError as exc:
        raise TerminalSandboxGenerationError(
            f"{task_id}: invalid build receipt"
        ) from exc
    try:
        binding = population.resolve(task_id)
    except SandboxImagePopulationError as exc:
        raise TerminalSandboxGenerationError(
            f"{task_id}: sandbox image binding missing"
        ) from exc

    if sha256_file(path) != binding.build_receipt_sha256:
        raise TerminalSandboxGenerationError(
            f"{task_id}: build receipt file digest mismatch"
        )
    if receipt.receipt_digest != binding.build_receipt_digest:
        raise TerminalSandboxGenerationError(
            f"{task_id}: build receipt semantic digest mismatch"
        )
    expected = {
        "family_id": FAMILY,
        "task_id": task_id,
        "task_source_sha256": binding.task_source_sha256,
        "build_context_sha256": binding.build_context_sha256,
        "image_reference": binding.image_reference,
        "container_image_digest": binding.container_image_digest,
    }
    for key, value in expected.items():
        if getattr(receipt, key) != value:
            raise TerminalSandboxGenerationError(
                f"{task_id}: build receipt {key} differs from sandbox population"
            )
    if receipt.platform != PLATFORM:
        raise TerminalSandboxGenerationError(
            f"{task_id}: build receipt platform mismatch"
        )
    if binding.build_receipt_path != expected_binding_path:
        raise TerminalSandboxGenerationError(
            f"{task_id}: build receipt path binding mismatch"
        )


def verify_terminal_sandbox_build_generation(
    generation_root: Path,
) -> VerifiedTerminalSandboxGeneration:
    supplied = Path(generation_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise TerminalSandboxGenerationError(
            "generation root must be a real directory"
        )
    root = supplied.resolve()

    manifest_path = root / AtomicEvidenceGeneration.MANIFEST_NAME
    receipt_path = root / AtomicEvidenceGeneration.RECEIPT_NAME
    provenance_path = root / AtomicEvidenceGeneration.PROVENANCE_NAME
    population_path = root / "SANDBOX_IMAGE_POPULATION.json"
    environment_path = root / "ENVIRONMENT_MANIFEST.json"

    manifest = _read_json(
        manifest_path,
        schema="DGC_EVIDENCE_GENERATION_MANIFEST_V2",
    )
    receipt = _read_json(
        receipt_path,
        schema=GENERATION_RECEIPT_SCHEMA,
    )
    provenance = _read_json(
        provenance_path,
        schema=GENERATION_PROVENANCE_SCHEMA,
    )

    publication_rows = file_manifest(
        root,
        excluded_names=frozenset(
            {AtomicEvidenceGeneration.MANIFEST_NAME}
        ),
    )
    if publication_rows != _manifest_rows(
        manifest.get("files")
    ):
        raise TerminalSandboxGenerationError(
            "generation publication manifest mismatch"
        )
    publication_digest = sha256_bytes(
        canonical_json_bytes(publication_rows)
    )
    if (
        manifest.get("publication_manifest_sha256")
        != publication_digest
    ):
        raise TerminalSandboxGenerationError(
            "generation publication digest mismatch"
        )

    payload_rows = file_manifest(
        root,
        excluded_names=AtomicEvidenceGeneration._CONTROL_FILES,
    )
    payload_digest = sha256_bytes(
        canonical_json_bytes(payload_rows)
    )
    if manifest.get("payload_manifest_sha256") != payload_digest:
        raise TerminalSandboxGenerationError(
            "generation payload digest mismatch"
        )
    if receipt.get("payload_manifest_sha256") != payload_digest:
        raise TerminalSandboxGenerationError(
            "generation receipt payload binding mismatch"
        )
    if provenance.get("payload_manifest_sha256") != payload_digest:
        raise TerminalSandboxGenerationError(
            "generation provenance payload binding mismatch"
        )

    population_document = _read_json(
        population_path,
        schema="DGC_SANDBOX_IMAGE_POPULATION_V1",
    )
    try:
        population = verify_sandbox_image_population_document(
            population_document
        )
    except SandboxImagePopulationError as exc:
        raise TerminalSandboxGenerationError(
            "invalid sandbox image population"
        ) from exc
    if population.family_id != FAMILY:
        raise TerminalSandboxGenerationError(
            "sandbox build generation family mismatch"
        )
    population_sha = sha256_file(population_path)
    environment_sha, declared_population_path = _verify_environment(
        path=environment_path,
        population=population,
        population_sha256=population_sha,
    )
    declared_generation_root = Path(
        declared_population_path
    ).parent

    receipt_checks = {
        "family_id": population.family_id,
        "runtime": population.runtime,
        "platform": PLATFORM,
        "materialization_reference_digest": (
            population.materialization_reference_digest
        ),
        "task_manifest_sha256": (
            population.task_manifest_sha256
        ),
        "task_count": population.expected_task_count,
        "sandbox_image_population_digest": (
            population.population_digest
        ),
        "sandbox_image_population_sha256": population_sha,
        "environment_manifest_sha256": environment_sha,
        "image_builds_performed": True,
        "external_benchmark_execution_performed": False,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    }
    for key, value in receipt_checks.items():
        if receipt.get(key) != value:
            raise TerminalSandboxGenerationError(
                f"generation receipt {key} differs from verified generation"
            )

    if provenance.get("claim") != "SANDBOX_IMAGE_BUILD_AND_PUSH_ONLY":
        raise TerminalSandboxGenerationError(
            "sandbox build provenance claim mismatch"
        )
    for key in (
        "repository_commit",
        "repository_tree",
        "materialization_reference_path",
        "materialization_reference_sha256",
        "registry_prefix",
        "docker_executable",
        "single_task_builder_sha256",
        "population_builder_sha256",
        "builder_cli_sha256",
    ):
        if not str(provenance.get(key, "")).strip():
            raise TerminalSandboxGenerationError(
                f"build provenance {key} missing"
            )
    if provenance.get("platform") != PLATFORM:
        raise TerminalSandboxGenerationError(
            "build provenance platform mismatch"
        )
    if provenance.get("runtime") != population.runtime:
        raise TerminalSandboxGenerationError(
            "build provenance runtime mismatch"
        )
    if (
        provenance.get("external_benchmark_execution_performed")
        is not False
    ):
        raise TerminalSandboxGenerationError(
            "build provenance cannot claim benchmark execution"
        )
    if provenance.get("product_promotion_authorized") is not False:
        raise TerminalSandboxGenerationError(
            "build provenance cannot grant product authority"
        )

    receipts_root = root / "build-receipts"
    if receipts_root.is_symlink() or not receipts_root.is_dir():
        raise TerminalSandboxGenerationError(
            "build-receipts directory missing"
        )
    expected_names = {
        f"{row.task_id}.json"
        for row in population.bindings
    }
    observed = list(receipts_root.iterdir())
    regular_paths = [
        path
        for path in observed
        if path.is_file() and not path.is_symlink()
    ]
    if {path.name for path in regular_paths} != expected_names:
        raise TerminalSandboxGenerationError(
            "build receipt population differs from sandbox image population"
        )
    if any(
        path.is_dir() or path.is_symlink()
        for path in observed
    ):
        raise TerminalSandboxGenerationError(
            "unexpected object in build-receipts directory"
        )
    for binding in population.bindings:
        _verify_build_receipt(
            path=receipts_root / f"{binding.task_id}.json",
            population=population,
            task_id=binding.task_id,
            expected_binding_path=(
                declared_generation_root
                / "build-receipts"
                / f"{binding.task_id}.json"
            ).as_posix(),
        )

    generation_digest = sha256_bytes(
        canonical_json_bytes(
            {
                "population_digest": population.population_digest,
                "population_sha256": population_sha,
                "environment_sha256": environment_sha,
                "payload_manifest_sha256": payload_digest,
                "publication_manifest_sha256": publication_digest,
            }
        )
    )
    return VerifiedTerminalSandboxGeneration(
        population=population,
        population_sha256=population_sha,
        environment_sha256=environment_sha,
        payload_manifest_sha256=payload_digest,
        publication_manifest_sha256=publication_digest,
        generation_digest=generation_digest,
    )
