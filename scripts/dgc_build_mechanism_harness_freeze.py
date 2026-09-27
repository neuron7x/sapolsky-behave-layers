from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.mechanism_harness_freeze import build_mechanism_harness_freeze

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _output(value: str) -> Path:
    path = _path(value).resolve()
    path.relative_to(RUNTIME_ROOT.resolve())
    if path.exists():
        raise FileExistsError("mechanism harness output is immutable")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build risk-free mechanism B0-B3+DGC harness freeze.")
    parser.add_argument("--execution-freeze", required=True)
    parser.add_argument("--mechanism-b2-authority", required=True)
    parser.add_argument("--baseline-panel-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_mechanism_harness_freeze(
        execution_manifest_freeze_path=_path(args.execution_freeze),
        mechanism_b2_fit_authority_path=_path(args.mechanism_b2_authority),
        baseline_panel_input_path=_path(args.baseline_panel_input),
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
        "harness_freeze_digest": authority.harness_freeze_digest,
        "comparison_frame_digest": authority.comparison_frame_digest,
        "risk_endpoint_bound": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
