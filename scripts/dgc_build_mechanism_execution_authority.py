from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan
from cwc.governance.mechanism_execution_authority import build_mechanism_execution_authority

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _output(value: str) -> Path:
    resolved = _path(value).resolve()
    try:
        resolved.relative_to(RUNTIME_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output must be inside ignored eval_bundle runtime root") from exc
    if resolved.exists():
        raise FileExistsError("mechanism authority output is immutable")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mint bounded DGC real-workload mechanism execution authority."
    )
    parser.add_argument("--execution-freeze", required=True)
    parser.add_argument("--harness-freeze", required=True)
    parser.add_argument("--task-partition", required=True)
    parser.add_argument("--mechanism-sizing", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_mechanism_execution_authority(
        repository_root=ROOT,
        execution_manifest_freeze_path=_path(args.execution_freeze),
        harness_freeze_path=_path(args.harness_freeze),
        task_partition_path=_path(args.task_partition),
        mechanism_sizing_path=_path(args.mechanism_sizing),
        mechanism_plan=MechanismStatisticalPlan(),
    )
    output = _output(args.output)
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
        "authority_digest": authority.authority_digest,
        "distributed_spec_digest": authority.distributed_spec_digest,
        "expected_units": (
            authority.confirmatory_task_count
            * 5
            * authority.required_trials_per_task
        ),
        "mechanism_execution_authorized": True,
        "risk_qualification_authorized": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
