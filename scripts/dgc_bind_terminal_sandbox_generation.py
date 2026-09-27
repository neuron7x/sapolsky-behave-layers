from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from cwc.governance.materialization_transaction import AtomicEvidenceGeneration, sha256_file
from cwc.governance.terminal_sandbox_generation import (
    verify_terminal_sandbox_build_generation,
)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"


def _runtime_root(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(RUNTIME_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output-root must be inside ignored eval_bundle runtime root") from exc
    if resolved.exists():
        raise FileExistsError("sandbox binding output is immutable")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a Terminal-Bench sandbox build generation and atomically bind "
            "its task-scoped OCI population into repo-local execution-freeze inputs."
        )
    )
    parser.add_argument("--generation-root", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    generation_root = Path(args.generation_root).resolve()
    verified = verify_terminal_sandbox_build_generation(generation_root)
    output = _runtime_root(args.output_root)
    relative_output = output.relative_to(ROOT)

    with AtomicEvidenceGeneration(output) as transaction:
        assert transaction.staging_root is not None
        root = transaction.staging_root
        source_population = generation_root / "SANDBOX_IMAGE_POPULATION.json"
        population_path = root / "SANDBOX_IMAGE_POPULATION.json"
        shutil.copyfile(source_population, population_path)
        if sha256_file(population_path) != verified.population_sha256:
            raise RuntimeError("sandbox population copy digest mismatch")

        final_population_rel = (
            relative_output / "SANDBOX_IMAGE_POPULATION.json"
        ).as_posix()
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

    print(
        json.dumps(
            {
                "status": "PASS",
                "output_root": str(relative_output),
                "environment_manifest": (
                    relative_output / "environment.json"
                ).as_posix(),
                "sandbox_image_population": (
                    relative_output / "SANDBOX_IMAGE_POPULATION.json"
                ).as_posix(),
                "sandbox_image_population_digest": verified.population.population_digest,
                "binding_payload_manifest_sha256": published.payload_manifest_sha256,
                "binding_publication_manifest_sha256": published.publication_manifest_sha256,
                "external_benchmark_execution_performed": False,
                "product_promotion_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
