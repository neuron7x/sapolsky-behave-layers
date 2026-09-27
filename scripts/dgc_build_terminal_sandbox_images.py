from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.governance.materialization_transaction import AtomicEvidenceGeneration, sha256_file
from cwc.governance.terminal_sandbox_builder import build_terminal_sandbox_population


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build and push the exact Terminal-Bench sandbox image population, "
            "then publish an immutable task->OCI digest evidence generation."
        )
    )
    parser.add_argument("--tasks-root", required=True)
    parser.add_argument("--materialization-reference", required=True)
    parser.add_argument("--registry-prefix", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--runtime", default="docker-linux-amd64")
    parser.add_argument("--platform", default="linux/amd64")
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    args = parser.parse_args()

    output = Path(args.output_root).resolve()
    reference = Path(args.materialization_reference).resolve()
    result = build_terminal_sandbox_population(
        materialized_tasks_root=Path(args.tasks_root),
        materialization_reference_path=reference,
        registry_prefix=args.registry_prefix,
        runtime=args.runtime,
        platform=args.platform,
        docker_executable=args.docker,
        command_timeout_seconds=args.timeout_seconds,
    )

    with AtomicEvidenceGeneration(output) as transaction:
        assert transaction.staging_root is not None
        root = transaction.staging_root
        population_path = root / "SANDBOX_IMAGE_POPULATION.json"
        population_path.write_text(
            json.dumps(result.population.document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        receipts_root = root / "build-receipts"
        receipts_root.mkdir()
        for receipt in result.receipts:
            task_id = str(receipt["task_id"])
            (receipts_root / f"{task_id}.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        receipt = {
            "schema": "DGC_TERMINAL_SANDBOX_BUILD_GENERATION_RECEIPT_V1",
            "family_id": result.population.family_id,
            "runtime": result.population.runtime,
            "materialization_reference_digest": result.population.materialization_reference_digest,
            "task_manifest_sha256": result.population.task_manifest_sha256,
            "task_count": result.population.expected_task_count,
            "sandbox_image_population_digest": result.population.population_digest,
            "sandbox_image_population_sha256": sha256_file(population_path),
            "external_benchmark_execution_performed": False,
            "product_promotion_authorized": False,
        }
        provenance = {
            "schema": "DGC_TERMINAL_SANDBOX_BUILD_PROVENANCE_V1",
            "claim": "SANDBOX_IMAGE_BUILD_AND_PUSH_ONLY",
            "materialization_reference_path": str(reference),
            "materialization_reference_sha256": sha256_file(reference),
            "registry_prefix": args.registry_prefix,
            "platform": args.platform,
            "docker_executable": args.docker,
            "external_benchmark_execution_performed": False,
            "product_promotion_authorized": False,
        }
        published = transaction.publish(receipt=receipt, provenance=provenance)

    print(
        json.dumps(
            {
                "status": "PASS",
                "family_id": result.population.family_id,
                "task_count": result.population.expected_task_count,
                "population_digest": result.population.population_digest,
                "payload_manifest_sha256": published.payload_manifest_sha256,
                "publication_manifest_sha256": published.publication_manifest_sha256,
                "output_root": str(output),
                "external_benchmark_execution_performed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
