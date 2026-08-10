"""Fail-closed semantic validation for committed CWC evidence.

Checks properties that checksums and JSON parsing alone cannot establish:
finite numbers, seed/file agreement, duplicate seeds within an experimental arm,
required bundle structure, and recomputability of the primary aggregate.
The validator is read-only.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.wp4_adaptive_depth.src.analyze import analyze as analyze_wp4
from experiments.wp4_adaptive_depth.src.analyze_exact_compute_v31 import analyze as analyze_wp4_v31
from experiments.wp4_adaptive_depth.src.analyze_end_to_end_v4 import analyze as analyze_wp4_v4

SEED_FILE = re.compile(r"seed(?P<seed>\d+)(?P<arm>_[^.]+)?\.json$")
REQUIRED_BUNDLE_FILES = ("RESULTS.md", "SHA256SUMS")
UNIT_INTERVAL_KEYS = {
    "acc", "accuracy", "solved", "auroc", "route_auroc", "route_nmi",
    "route_balanced_acc", "balanced_acc", "canonical_exact", "tuple_correct",
    "syntax_valid", "collapse_probability", "independent_replication",
}


def _walk_numbers(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            errors.append(f"{path}: non-finite number {value!r}")
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _walk_numbers(item, f"{path}[{i}]", errors)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                key in UNIT_INTERVAL_KEYS
                and isinstance(item, (int, float))
                and not isinstance(item, bool)
                and not 0.0 <= item <= 1.0
            ):
                errors.append(f"{path}.{key}: probability/rate outside [0,1]: {item!r}")
            _walk_numbers(item, f"{path}.{key}", errors)


def _json_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.json") if ".git" not in p.parts and ".venv" not in p.parts)


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    seen: dict[tuple[Path, str, int], Path] = {}
    for path in _json_files(root):
        rel = path.relative_to(root)
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue
        _walk_numbers(payload, str(rel), errors)
        match = SEED_FILE.match(path.name)
        if match and isinstance(payload, dict) and isinstance(payload.get("seed"), int):
            filename_seed = int(match.group("seed"))
            if payload["seed"] != filename_seed:
                errors.append(f"{rel}: payload seed {payload['seed']} != filename seed {filename_seed}")
            arm_key = (path.parent, match.group("arm") or "", filename_seed)
            if arm_key in seen:
                errors.append(f"{rel}: duplicate seed in arm; first seen at {seen[arm_key].relative_to(root)}")
            seen[arm_key] = path

    for bundle in sorted((root / "artifacts").glob("wp*")):
        if not bundle.is_dir():
            continue
        if bundle.name == "wp1-release":
            continue
        for name in REQUIRED_BUNDLE_FILES:
            if not (bundle / name).is_file():
                errors.append(f"{bundle.relative_to(root)}: missing {name}")

    # Frozen negatives (RTM REQ-010): immutable bundles under artifacts/history/.
    # They carry no RESULTS.md — the sealed record is SHA256SUMS + CLAIM_BOUNDARY.json.
    # Previously neither this validator (wp* glob) nor verify-evidence (hard-coded
    # list) covered them, so the declared REQ-010 control was dead; now enforced.
    history = root / "artifacts/history"
    if history.is_dir():
        for bundle in sorted(p for p in history.iterdir() if p.is_dir()):
            for name in ("SHA256SUMS", "CLAIM_BOUNDARY.json"):
                if not (bundle / name).is_file():
                    errors.append(f"{bundle.relative_to(root)}: missing {name} (frozen negative)")

    wp4_runs = root / "artifacts/wp4-adaptive-depth-v2/raw_runs"
    wp4_saved = root / "artifacts/wp4-adaptive-depth-v2/analysis.json"
    if wp4_runs.is_dir() and wp4_saved.is_file():
        recomputed = analyze_wp4(wp4_runs)
        saved = json.loads(wp4_saved.read_text())
        if recomputed != saved:
            errors.append("artifacts/wp4-adaptive-depth-v2/analysis.json: does not recompute exactly from raw_runs")
    v31_runs = root / "artifacts/wp4-exact-compute-v31/raw_runs"
    v31_saved = root / "artifacts/wp4-exact-compute-v31/analysis.json"
    if v31_runs.is_dir() and v31_saved.is_file():
        recomputed = analyze_wp4_v31(v31_runs)
        saved = json.loads(v31_saved.read_text())
        if recomputed != saved:
            errors.append("artifacts/wp4-exact-compute-v31/analysis.json: does not recompute exactly")
    v4_runs = root / "artifacts/wp4-end-to-end-v4/raw_runs"
    v4_saved = root / "artifacts/wp4-end-to-end-v4/analysis.json"
    if v4_runs.is_dir() and v4_saved.is_file():
        recomputed = analyze_wp4_v4(v4_runs)
        saved = json.loads(v4_saved.read_text())
        if recomputed != saved:
            errors.append("artifacts/wp4-end-to-end-v4/analysis.json: does not recompute exactly")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f"EVIDENCE-INVALID: {error}")
        print(f"EVIDENCE-VALIDATION: FAIL ({len(errors)} errors)")
        return 1
    print("EVIDENCE-VALIDATION: PASS (JSON finite, seeds coherent, bundles complete, WP4 aggregate reproducible)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
