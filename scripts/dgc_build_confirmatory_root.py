from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.confirmatory_root_authority import build_confirmatory_root_authority

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"
SOURCE_REGISTRY = ROOT / "artifacts/dgc-product-v1/external_source_authority.json"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _runtime_output(value: str) -> Path:
    path = _path(value).resolve()
    try:
        path.relative_to(RUNTIME_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output must be inside eval_bundle") from exc
    if path.exists():
        raise FileExistsError("confirmatory root output is immutable")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint one held-out confirmatory generation root from closed DGC evidence lineage.")
    parser.add_argument("--execution-freeze", required=True)
    parser.add_argument("--harness-freeze", required=True)
    parser.add_argument("--trial-sizing-authority", required=True)
    parser.add_argument("--task-partition", required=True)
    parser.add_argument("--materialization-reference", required=True)
    parser.add_argument("--root-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_confirmatory_root_authority(
        execution_manifest_freeze_path=_path(args.execution_freeze),
        harness_freeze_path=_path(args.harness_freeze),
        trial_sizing_authority_path=_path(args.trial_sizing_authority),
        task_partition_path=_path(args.task_partition),
        materialization_reference_path=_path(args.materialization_reference),
        source_registry_path=SOURCE_REGISTRY,
        root_input_path=_path(args.root_input),
    )
    output = _runtime_output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    print(json.dumps({
        "status": "PASS",
        "output": str(output.relative_to(ROOT)),
        "family_id": authority.family_id,
        "generation_id": authority.generation_id,
        "root_digest": authority.root_digest,
        "distributed_spec_digest": authority.distributed_spec_digest,
        "expected_work_units": authority.root["expected_work_units"],
        "confirmatory_execution_authorized": True,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
