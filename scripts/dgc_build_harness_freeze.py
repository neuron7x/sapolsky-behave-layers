from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.harness_freeze import build_harness_freeze

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"


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
        raise FileExistsError("harness freeze output is immutable")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the final post-B2 B0-B3+DGC evaluation harness freeze.")
    parser.add_argument("--execution-freeze", required=True)
    parser.add_argument("--b2-authority", required=True)
    parser.add_argument("--baseline-panel-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_harness_freeze(
        execution_manifest_freeze_path=_path(args.execution_freeze),
        b2_fit_authority_path=_path(args.b2_authority),
        baseline_panel_input_path=_path(args.baseline_panel_input),
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
        "baseline_panel_digest": authority.baseline_panel_digest,
        "comparison_frame_digest": authority.comparison_frame_digest,
        "harness_freeze_digest": authority.harness_freeze_digest,
        "harness_frozen": True,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
