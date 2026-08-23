from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.task_partition import freeze_task_partition

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REGISTRY = ROOT / "artifacts/dgc-product-v1/external_source_authority.json"
RUNTIME_ROOT = ROOT / "eval_bundle"


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _runtime_output(value: str) -> Path:
    path = _repo_path(value).resolve()
    try:
        path.relative_to(RUNTIME_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output must be inside eval_bundle") from exc
    if path.exists():
        raise FileExistsError("task partition output is immutable")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze calibration/confirmatory task split before observing outcomes.")
    parser.add_argument("--generation-root", required=True)
    parser.add_argument("--execution-freeze", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    execution_path = _repo_path(args.execution_freeze)
    execution = verify_execution_manifest_freeze_document(execution_path)
    plan = ProductStatisticalPlan(**execution["statistical_plan"])
    reference = ROOT / str(execution["materialization_reference_path"])
    receipt = freeze_task_partition(
        generation_root=Path(args.generation_root),
        materialization_reference_path=reference,
        source_registry_path=SOURCE_REGISTRY,
        family_id=str(execution["family_id"]),
        statistical_plan=plan,
    )
    if receipt.statistical_plan_digest != execution["statistical_plan_digest"]:
        raise RuntimeError("task partition statistical plan does not match execution freeze")
    if receipt.materialization_reference_digest != execution["materialization_reference_digest"]:
        raise RuntimeError("task partition materialization reference does not match execution freeze")
    if receipt.task_manifest_digest != execution["task_manifest_digest"]:
        raise RuntimeError("task partition task manifest does not match execution freeze")

    output = _runtime_output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(receipt.document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
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
        "family_id": receipt.family_id,
        "calibration_task_count": len(receipt.calibration_task_ids),
        "confirmatory_task_count": len(receipt.confirmatory_task_ids),
        "receipt_digest": receipt.receipt_digest,
        "outcomes_observed": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
