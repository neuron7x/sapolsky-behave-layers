from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan
from cwc.governance.mechanism_execution_freeze import (
    INPUT_SCHEMA,
    freeze_mechanism_execution_manifests,
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
        raise RuntimeError("repository must be clean before mechanism execution freeze")
    return commit, tree


def _output(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve()
    resolved.relative_to(RUNTIME_ROOT.resolve())
    if resolved.exists():
        raise FileExistsError("mechanism execution freeze output is immutable")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze risk-free mechanism execution identities before mechanism B2 calibration.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != INPUT_SCHEMA:
        raise ValueError("wrong mechanism execution freeze input schema")
    if "risk_endpoint_manifest" in payload.get("components", {}):
        raise ValueError("mechanism execution input cannot contain risk endpoint")
    commit, tree = _repo_identity()
    frozen = freeze_mechanism_execution_manifests(
        repository_root=ROOT,
        repository_commit=commit,
        repository_tree=tree,
        family_id=payload["family_id"],
        materialization_reference_path=Path(payload["materialization_reference_path"]),
        component_paths=payload["components"],
        governance_policy_paths=payload["governance_policies"],
        statistical_plan_payload=payload.get("statistical_plan"),
        mechanism_plan=MechanismStatisticalPlan(),
    )
    output = _output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(frozen.document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
    except BaseException:
        output.unlink(missing_ok=True); raise
    print(json.dumps({
        "status": "PASS",
        "output": str(output.relative_to(ROOT)),
        "family_id": frozen.family_id,
        "freeze_digest": frozen.freeze_digest,
        "mechanism_plan_digest": frozen.mechanism_plan_digest,
        "risk_endpoint_bound": False,
        "mechanism_execution_authorized": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
