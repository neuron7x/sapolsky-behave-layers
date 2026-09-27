from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.mechanism_b2_fit_authority import authorize_mechanism_b2_fit

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _output(value: str) -> Path:
    path = _path(value).resolve()
    path.relative_to(RUNTIME_ROOT.resolve())
    if path.exists():
        raise FileExistsError("mechanism B2 authority output is immutable")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorize deterministic risk-free mechanism B2 fit.")
    parser.add_argument("--execution-freeze", required=True)
    parser.add_argument("--task-partition", required=True)
    parser.add_argument("--fit-input", required=True)
    parser.add_argument("--fit-receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = authorize_mechanism_b2_fit(
        execution_manifest_freeze_path=_path(args.execution_freeze),
        task_partition_path=_path(args.task_partition),
        fit_input_path=_path(args.fit_input),
        fit_receipt_path=_path(args.fit_receipt),
    )
    output = _output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
    except BaseException:
        output.unlink(missing_ok=True); raise
    print(json.dumps({
        "status": "PASS",
        "authority_digest": authority.authority_digest,
        "fitted_model_digest": authority.fitted_model_digest,
        "risk_fields_consumed": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
