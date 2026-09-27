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
from cwc.governance.sandbox_image_population import (
    SandboxImagePopulation,
    SandboxImagePopulationError,
    verify_sandbox_image_population_document,
)
from cwc.governance.terminal_sandbox_builder import BUILD_RECEIPT_SCHEMA, FAMILY

GENERATION_RECEIPT_SCHEMA = "DGC_TERMINAL_SANDBOX_BUILD_GENERATION_RECEIPT_V1"
GENERATION_PROVENANCE_SCHEMA = "DGC_TERMINAL_SANDBOX_BUILD_PROVENANCE_V1"


class TerminalSandboxGenerationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedTerminalSandboxGeneration:
    population: SandboxImagePopulation
    population_sha256: str
    payload_manifest_sha256: str
    publication_manifest_sha256: str
    generation_digest: str


def _read_json(path: Path, *, schema: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise TerminalSandboxGenerationError(f"missing regular JSON file: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalSandboxGenerationError(f"invalid JSON file: {path.name}") from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise TerminalSandboxGenerationError(f"unexpected schema for {path.name}")
    return value


def _manifest_rows(rows: object) -> tuple[tuple[str, str, int, int, str], ...]:
    if not isinstance(rows, list):
        raise TerminalSandboxGenerationError("generation manifest files must be a list")
    normalized: list[tuple[str, str, int, int, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise TerminalSandboxGenerationError("invalid generation manifest row")
        path = str(row.get("path", ""))
        object_type = str(row.get("type", ""))
        try:
            mode = int(row.get("mode"))
            size = int(row.get("bytes"))
        except (TypeError, ValueError) as exc:
            raise TerminalSandboxGenerationError("manifest mode/bytes malformed") from exc
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
            raise TerminalSandboxGenerationError("invalid generation manifest file row")
        if path in seen:
            raise TerminalSandboxGenerationError("duplicate generation manifest path")
        seen.add(path)
        normalized.append((path, object_type, mode, size, digest))
    return tuple(sorted(normalized))


def _verify_build_receipt(
    *,
    path: Path,
    population: SandboxImagePopulation,
    task_id: str,
) -> None:
    receipt = _read_json(path, schema=BUILD_RECEIPT_SCHEMA)
    declared = str(receipt.get("receipt_sha256", "")).strip().lower()
    payload = dict(receipt)
    payload.pop("receipt_sha256", None)
    observed = sha256_bytes(canonical_json_bytes(payload))
    if declared != observed:
        raise TerminalSandboxGenerationError(f"{task_id}: build receipt digest mismatch")
    binding = population.resolve(task_id)
    expected = {
        "family_id": FAMILY,
        "task_id": task_id,
        "runtime": population.runtime,
        "materialization_reference_digest": population.materialization_reference_digest,
        "materialized_task_manifest_sha256": population.task_manifest_sha256,
        "task_source_sha256": binding.task_source_sha256,
        "build_context_sha256": binding.build_context_sha256,
        "image_reference": binding.image_reference,
        "container_image_digest": binding.container_image_digest,
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise TerminalSandboxGenerationError(
                f"{task_id}: build receipt {key} differs from sandbox population"
            )
    if binding.build_receipt_sha256 != declared:
        raise TerminalSandboxGenerationError(
            f"{task_id}: sandbox population build receipt binding mismatch"
        )
    if receipt.get("external_benchmark_execution_performed") is not False:
        raise TerminalSandboxGenerationError(
            f"{task_id}: build receipt cannot claim benchmark execution"
        )
    if receipt.get("product_promotion_authorized") is not False:
        raise TerminalSandboxGenerationError(
            f"{task_id}: build receipt cannot grant product authority"
        )


def verify_terminal_sandbox_build_generation(
    generation_root: Path,
) -> VerifiedTerminalSandboxGeneration:
    supplied = Path(generation_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise TerminalSandboxGenerationError("generation root must be a real directory")
    root = supplied.resolve()

    manifest_path = root / AtomicEvidenceGeneration.MANIFEST_NAME
    receipt_path = root / AtomicEvidenceGeneration.RECEIPT_NAME
    provenance_path = root / AtomicEvidenceGeneration.PROVENANCE_NAME
    population_path = root / "SANDBOX_IMAGE_POPULATION.json"

    manifest = _read_json(
        manifest_path,
        schema="DGC_EVIDENCE_GENERATION_MANIFEST_V2",
    )
    receipt = _read_json(receipt_path, schema=GENERATION_RECEIPT_SCHEMA)
    provenance = _read_json(provenance_path, schema=GENERATION_PROVENANCE_SCHEMA)

    publication_rows = file_manifest(
        root,
        excluded_names=frozenset({AtomicEvidenceGeneration.MANIFEST_NAME}),
    )
    if publication_rows != _manifest_rows(manifest.get("files")):
        raise TerminalSandboxGenerationError("generation publication manifest mismatch")
    publication_digest = sha256_bytes(canonical_json_bytes(publication_rows))
    if manifest.get("publication_manifest_sha256") != publication_digest:
        raise TerminalSandboxGenerationError("generation publication digest mismatch")

    payload_rows = file_manifest(
        root,
        excluded_names=AtomicEvidenceGeneration._CONTROL_FILES,
    )
    payload_digest = sha256_bytes(canonical_json_bytes(payload_rows))
    if manifest.get("payload_manifest_sha256") != payload_digest:
        raise TerminalSandboxGenerationError("generation payload digest mismatch")
    if receipt.get("payload_manifest_sha256") != payload_digest:
        raise TerminalSandboxGenerationError("generation receipt payload binding mismatch")
    if provenance.get("payload_manifest_sha256") != payload_digest:
        raise TerminalSandboxGenerationError("generation provenance payload binding mismatch")

    population_document = _read_json(
        population_path,
        schema="DGC_SANDBOX_IMAGE_POPULATION_V1",
    )
    try:
        population = verify_sandbox_image_population_document(population_document)
    except SandboxImagePopulationError as exc:
        raise TerminalSandboxGenerationError("invalid sandbox image population") from exc
    if population.family_id != FAMILY:
        raise TerminalSandboxGenerationError("sandbox build generation family mismatch")
    population_sha = sha256_file(population_path)

    receipt_checks = {
        "family_id": population.family_id,
        "runtime": population.runtime,
        "materialization_reference_digest": population.materialization_reference_digest,
        "task_manifest_sha256": population.task_manifest_sha256,
        "task_count": population.expected_task_count,
        "sandbox_image_population_digest": population.population_digest,
        "sandbox_image_population_sha256": population_sha,
    }
    for key, value in receipt_checks.items():
        if receipt.get(key) != value:
            raise TerminalSandboxGenerationError(
                f"generation receipt {key} differs from verified population"
            )
    if receipt.get("external_benchmark_execution_performed") is not False:
        raise TerminalSandboxGenerationError("generation receipt cannot claim benchmark execution")
    if receipt.get("product_promotion_authorized") is not False:
        raise TerminalSandboxGenerationError("generation receipt cannot grant product authority")
    if provenance.get("claim") != "SANDBOX_IMAGE_BUILD_AND_PUSH_ONLY":
        raise TerminalSandboxGenerationError("sandbox build provenance claim mismatch")
    if provenance.get("external_benchmark_execution_performed") is not False:
        raise TerminalSandboxGenerationError("build provenance cannot claim benchmark execution")
    if provenance.get("product_promotion_authorized") is not False:
        raise TerminalSandboxGenerationError("build provenance cannot grant product authority")

    receipts_root = root / "build-receipts"
    if receipts_root.is_symlink() or not receipts_root.is_dir():
        raise TerminalSandboxGenerationError("build-receipts directory missing")
    expected_names = {f"{row.task_id}.json" for row in population.bindings}
    observed_paths = [
        path
        for path in receipts_root.iterdir()
        if path.is_file() and not path.is_symlink()
    ]
    if {path.name for path in observed_paths} != expected_names:
        raise TerminalSandboxGenerationError(
            "build receipt population differs from sandbox image population"
        )
    if any(path.is_dir() or path.is_symlink() for path in receipts_root.iterdir()):
        raise TerminalSandboxGenerationError("unexpected object in build-receipts directory")
    for binding in population.bindings:
        _verify_build_receipt(
            path=receipts_root / f"{binding.task_id}.json",
            population=population,
            task_id=binding.task_id,
        )

    generation_digest = sha256_bytes(
        canonical_json_bytes({
            "population_digest": population.population_digest,
            "population_sha256": population_sha,
            "payload_manifest_sha256": payload_digest,
            "publication_manifest_sha256": publication_digest,
        })
    )
    return VerifiedTerminalSandboxGeneration(
        population=population,
        population_sha256=population_sha,
        payload_manifest_sha256=payload_digest,
        publication_manifest_sha256=publication_digest,
        generation_digest=generation_digest,
    )
