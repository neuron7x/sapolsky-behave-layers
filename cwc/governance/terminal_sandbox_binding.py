from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from cwc.governance.materialization_transaction import AtomicEvidenceGeneration, sha256_file
from cwc.governance.terminal_sandbox_generation import (
    VerifiedTerminalSandboxGeneration,
    verify_terminal_sandbox_build_generation,
)


class TerminalSandboxBindingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TerminalSandboxBindingResult:
    output_root: Path
    environment_manifest_path: Path
    sandbox_image_population_path: Path
    sandbox_image_population_digest: str
    binding_payload_manifest_sha256: str
    binding_publication_manifest_sha256: str


def bind_terminal_sandbox_generation(
    *,
    generation_root: Path,
    repository_root: Path,
    output_root: Path,
) -> TerminalSandboxBindingResult:
    repository = Path(repository_root).resolve()
    if not repository.is_dir():
        raise TerminalSandboxBindingError("repository root missing")
    runtime_root = repository / "eval_bundle"
    output = Path(output_root)
    if not output.is_absolute():
        output = repository / output
    output = output.resolve()
    try:
        output.relative_to(runtime_root.resolve())
    except ValueError as exc:
        raise TerminalSandboxBindingError(
            "output root must be inside ignored eval_bundle runtime root"
        ) from exc
    if output.exists():
        raise TerminalSandboxBindingError("sandbox binding output is immutable")

    generation = Path(generation_root).resolve()
    verified: VerifiedTerminalSandboxGeneration = verify_terminal_sandbox_build_generation(
        generation
    )
    relative_output = output.relative_to(repository)
    final_population_rel = (
        relative_output / "SANDBOX_IMAGE_POPULATION.json"
    ).as_posix()
    final_environment_rel = (relative_output / "environment.json").as_posix()

    with AtomicEvidenceGeneration(output) as transaction:
        assert transaction.staging_root is not None
        root = transaction.staging_root
        source_population = generation / "SANDBOX_IMAGE_POPULATION.json"
        population_path = root / "SANDBOX_IMAGE_POPULATION.json"
        shutil.copyfile(source_population, population_path)
        if sha256_file(population_path) != verified.population_sha256:
            raise TerminalSandboxBindingError("sandbox population copy digest mismatch")

        environment = {
            "schema": "DGC_ENVIRONMENT_MANIFEST_V2",
            "family_id": verified.population.family_id,
            "runtime": verified.population.runtime,
            "execution_mode": "PREBUILT_IMMUTABLE_OCI",
            "materialization_reference_digest": (
                verified.population.materialization_reference_digest
            ),
            "task_manifest_sha256": verified.population.task_manifest_sha256,
            "sandbox_image_population_path": final_population_rel,
            "sandbox_image_population_sha256": verified.population_sha256,
            "sandbox_image_population_digest": verified.population.population_digest,
        }
        environment_path = root / "environment.json"
        environment_path.write_text(
            json.dumps(environment, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        receipt = {
            "schema": "DGC_TERMINAL_SANDBOX_BINDING_RECEIPT_V1",
            "family_id": verified.population.family_id,
            "runtime": verified.population.runtime,
            "task_count": verified.population.expected_task_count,
            "materialization_reference_digest": (
                verified.population.materialization_reference_digest
            ),
            "task_manifest_sha256": verified.population.task_manifest_sha256,
            "sandbox_image_population_digest": verified.population.population_digest,
            "sandbox_image_population_sha256": verified.population_sha256,
            "environment_manifest_sha256": sha256_file(environment_path),
            "source_build_generation_digest": verified.generation_digest,
            "external_benchmark_execution_performed": False,
            "product_promotion_authorized": False,
        }
        provenance = {
            "schema": "DGC_TERMINAL_SANDBOX_BINDING_PROVENANCE_V1",
            "claim": "VERIFIED_SANDBOX_BINDING_ONLY",
            "source_payload_manifest_sha256": verified.payload_manifest_sha256,
            "source_publication_manifest_sha256": verified.publication_manifest_sha256,
            "source_build_generation_digest": verified.generation_digest,
            "external_benchmark_execution_performed": False,
            "product_promotion_authorized": False,
        }
        published = transaction.publish(receipt=receipt, provenance=provenance)

    return TerminalSandboxBindingResult(
        output_root=output,
        environment_manifest_path=repository / final_environment_rel,
        sandbox_image_population_path=repository / final_population_rel,
        sandbox_image_population_digest=verified.population.population_digest,
        binding_payload_manifest_sha256=published.payload_manifest_sha256,
        binding_publication_manifest_sha256=published.publication_manifest_sha256,
    )
