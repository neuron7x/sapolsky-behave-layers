from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.generalization_registry import (
    GeneralizationAxis,
    build_generalization_registry,
)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"


def _input(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _repo_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("generalization subject paths must be repository-relative")
    return path


def _output(value: str) -> Path:
    path = _input(value).resolve()
    try:
        path.relative_to(RUNTIME_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output must remain inside eval_bundle") from exc
    if path.exists():
        raise FileExistsError("generalization registry output is immutable")
    return path


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze exact G1-G5 evaluation definitions before B2/confirmatory outcomes."
    )
    parser.add_argument("--execution-freeze", required=True)
    parser.add_argument("--task-partition", required=True)
    parser.add_argument("--baseline-panel-input", required=True)
    parser.add_argument("--g1-manifest", required=True)
    parser.add_argument("--g2-manifest", required=True)
    parser.add_argument("--g3-manifest", required=True)
    parser.add_argument("--g4-manifest", required=True)
    parser.add_argument("--g5-manifest", required=True)
    parser.add_argument("--b0-policy-id", required=True)
    parser.add_argument("--b1-policy-id", required=True)
    parser.add_argument("--b2-policy-id", required=True)
    parser.add_argument("--b3-policy-id", required=True)
    parser.add_argument("--dgc-policy-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_generalization_registry(
        repository_root=ROOT,
        execution_manifest_freeze_path=_input(args.execution_freeze),
        task_partition_path=_repo_relative(args.task_partition),
        baseline_panel_input_path=_repo_relative(args.baseline_panel_input),
        axis_manifest_paths={
            GeneralizationAxis.UNSEEN_TASKS: _repo_relative(args.g1_manifest),
            GeneralizationAxis.UNSEEN_DOMAIN: _repo_relative(args.g2_manifest),
            GeneralizationAxis.UNSEEN_MODEL_PROVIDER: _repo_relative(args.g3_manifest),
            GeneralizationAxis.CHANGED_ECONOMICS: _repo_relative(args.g4_manifest),
            GeneralizationAxis.PERTURBATION_SHIFT: _repo_relative(args.g5_manifest),
        },
        policy_role_bindings={
            "B0_FIXED_COMPUTE": args.b0_policy_id,
            "B1_UNCERTAINTY_ROUTER": args.b1_policy_id,
            "B2_LEARNED_COST_QUALITY_ROUTER": args.b2_policy_id,
            "B3_SEQUENTIAL_VERIFICATION": args.b3_policy_id,
            "DGC": args.dgc_policy_id,
        },
    )
    output = _output(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps({
        "status": "PASS",
        "output": str(output.relative_to(ROOT)),
        "registry_digest": authority.registry_digest,
        "baseline_panel_input_sha256": authority.baseline_panel_input_sha256,
        "g1_holdout_task_digest": authority.g1_holdout_task_digest,
        "per_claim_alpha": authority.per_claim_alpha,
        "axes": [row.axis for row in authority.axes],
        "policy_retuning_allowed": False,
        "generalization_execution_authorized": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
