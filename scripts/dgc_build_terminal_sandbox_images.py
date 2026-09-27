from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from cwc.governance.materialization_transaction import (
    AtomicEvidenceGeneration,
    sha256_file,
)
from cwc.governance.sandbox_image_build import (
    sandbox_image_build_receipt_bytes,
)
from cwc.governance.sandbox_image_population import EXECUTION_MODE
from cwc.governance.terminal_sandbox_builder import (
    PLATFORM,
    RUNTIME,
    build_terminal_sandbox_population,
)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"


def _capture(*args: str) -> str:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _repo_identity() -> tuple[str, str]:
    commit = _capture("git", "rev-parse", "HEAD")
    tree = _capture("git", "rev-parse", "HEAD^{tree}")
    if _capture("git", "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError(
            "repository must be clean before building sandbox image authority"
        )
    return commit, tree


def _runtime_output(value: str) -> tuple[Path, str]:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    output = candidate.resolve()
    try:
        output.relative_to(RUNTIME_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(
            "output-root must be inside ignored eval_bundle runtime root"
        ) from exc
    if output.exists() or output.is_symlink():
        raise FileExistsError(
            "sandbox image generation output must not pre-exist"
        )
    return output, output.relative_to(ROOT).as_posix()


def _verify_reference_repo_identity(
    reference: Path,
    *,
    expected_commit: str,
    expected_tree: str,
) -> None:
    candidate = Path(reference)
    if candidate.is_symlink() or not candidate.is_file():
        raise RuntimeError(
            "materialization reference must be a regular file"
        )
    document = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise RuntimeError("materialization reference must be a JSON object")
    if document.get("repository_commit") != expected_commit:
        raise RuntimeError(
            "materialization reference belongs to a different repository commit"
        )
    if document.get("repository_tree") != expected_tree:
        raise RuntimeError(
            "materialization reference belongs to a different repository tree"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build and push the exact Terminal-Bench sandbox image population, "
            "then atomically publish task->OCI build receipts and the V2 "
            "environment manifest. This does not run benchmark agents."
        )
    )
    parser.add_argument("--tasks-root", required=True)
    parser.add_argument("--materialization-reference", required=True)
    parser.add_argument("--registry-prefix", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    args = parser.parse_args()

    output, output_rel = _runtime_output(args.output_root)
    commit, tree = _repo_identity()
    reference = Path(args.materialization_reference).resolve()
    _verify_reference_repo_identity(
        reference,
        expected_commit=commit,
        expected_tree=tree,
    )

    receipt_prefix = (
        Path(output_rel) / "build-receipts"
    ).as_posix()
    result = build_terminal_sandbox_population(
        materialized_tasks_root=Path(args.tasks_root),
        materialization_reference_path=reference,
        registry_prefix=args.registry_prefix,
        receipt_path_prefix=receipt_prefix,
        runtime=RUNTIME,
        platform=PLATFORM,
        docker_executable=args.docker,
        command_timeout_seconds=args.timeout_seconds,
    )

    with AtomicEvidenceGeneration(output) as transaction:
        assert transaction.staging_root is not None
        root = transaction.staging_root

        receipts_root = root / "build-receipts"
        receipts_root.mkdir()
        for receipt in result.receipts:
            receipt_path = receipts_root / f"{receipt.task_id}.json"
            receipt_path.write_bytes(
                sandbox_image_build_receipt_bytes(receipt)
            )

        population_path = root / "SANDBOX_IMAGE_POPULATION.json"
        population_path.write_text(
            json.dumps(
                result.population.document,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        population_final_rel = (
            Path(output_rel) / "SANDBOX_IMAGE_POPULATION.json"
        ).as_posix()
        environment = {
            "schema": "DGC_ENVIRONMENT_MANIFEST_V2",
            "family_id": result.population.family_id,
            "runtime": result.population.runtime,
            "execution_mode": EXECUTION_MODE,
            "materialization_reference_digest": (
                result.population.materialization_reference_digest
            ),
            "task_manifest_sha256": (
                result.population.task_manifest_sha256
            ),
            "sandbox_image_population_path": population_final_rel,
            "sandbox_image_population_sha256": sha256_file(
                population_path
            ),
            "sandbox_image_population_digest": (
                result.population.population_digest
            ),
        }
        environment_path = root / "ENVIRONMENT_MANIFEST.json"
        environment_path.write_text(
            json.dumps(environment, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        receipt = {
            "schema": "DGC_TERMINAL_SANDBOX_BUILD_GENERATION_RECEIPT_V2",
            "family_id": result.population.family_id,
            "runtime": result.population.runtime,
            "platform": PLATFORM,
            "repository_commit": commit,
            "repository_tree": tree,
            "materialization_reference_digest": (
                result.population.materialization_reference_digest
            ),
            "task_manifest_sha256": (
                result.population.task_manifest_sha256
            ),
            "task_count": result.population.expected_task_count,
            "sandbox_image_population_digest": (
                result.population.population_digest
            ),
            "sandbox_image_population_sha256": sha256_file(
                population_path
            ),
            "environment_manifest_sha256": sha256_file(
                environment_path
            ),
            "image_builds_performed": True,
            "external_benchmark_execution_performed": False,
            "confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
        }
        provenance = {
            "schema": "DGC_TERMINAL_SANDBOX_BUILD_PROVENANCE_V2",
            "claim": "SANDBOX_IMAGE_BUILD_AND_PUSH_ONLY",
            "repository_commit": commit,
            "repository_tree": tree,
            "materialization_reference_path": str(reference),
            "materialization_reference_sha256": sha256_file(
                reference
            ),
            "registry_prefix": args.registry_prefix,
            "platform": PLATFORM,
            "runtime": RUNTIME,
            "docker_executable": args.docker,
            "single_task_builder_sha256": sha256_file(
                ROOT
                / "cwc"
                / "governance"
                / "sandbox_image_build.py"
            ),
            "population_builder_sha256": sha256_file(
                ROOT
                / "cwc"
                / "governance"
                / "terminal_sandbox_builder.py"
            ),
            "builder_cli_sha256": sha256_file(
                Path(__file__).resolve()
            ),
            "external_benchmark_execution_performed": False,
            "product_promotion_authorized": False,
        }
        published = transaction.publish(
            receipt=receipt,
            provenance=provenance,
        )

    print(
        json.dumps(
            {
                "status": "PASS",
                "family_id": result.population.family_id,
                "task_count": result.population.expected_task_count,
                "population_digest": result.population.population_digest,
                "payload_manifest_sha256": (
                    published.payload_manifest_sha256
                ),
                "publication_manifest_sha256": (
                    published.publication_manifest_sha256
                ),
                "output_root": output_rel,
                "environment_manifest": (
                    Path(output_rel)
                    / "ENVIRONMENT_MANIFEST.json"
                ).as_posix(),
                "sandbox_image_population": (
                    Path(output_rel)
                    / "SANDBOX_IMAGE_POPULATION.json"
                ).as_posix(),
                "external_benchmark_execution_performed": False,
                "confirmatory_execution_authorized": False,
                "product_promotion_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
