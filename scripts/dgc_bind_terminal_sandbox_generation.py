from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.governance.terminal_sandbox_binding import bind_terminal_sandbox_generation

ROOT = Path(__file__).resolve().parents[1]


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

    result = bind_terminal_sandbox_generation(
        generation_root=Path(args.generation_root),
        repository_root=ROOT,
        output_root=Path(args.output_root),
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "output_root": str(result.output_root.relative_to(ROOT)),
                "environment_manifest": str(
                    result.environment_manifest_path.relative_to(ROOT)
                ),
                "sandbox_image_population": str(
                    result.sandbox_image_population_path.relative_to(ROOT)
                ),
                "sandbox_image_population_digest": (
                    result.sandbox_image_population_digest
                ),
                "binding_payload_manifest_sha256": (
                    result.binding_payload_manifest_sha256
                ),
                "binding_publication_manifest_sha256": (
                    result.binding_publication_manifest_sha256
                ),
                "external_benchmark_execution_performed": False,
                "product_promotion_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
