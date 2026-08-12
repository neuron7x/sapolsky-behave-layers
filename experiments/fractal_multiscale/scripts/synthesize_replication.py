from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC = PKG_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cwc_fractal.cwc_adapter import observations_from_cwc_record  # noqa: E402
from cwc_fractal.replication import (  # noqa: E402
    cross_seed_pair_diagnostics,
    evaluate_programme_nulls,
)
from cwc_fractal.robust_protocol import load_yaml, robust_mappings  # noqa: E402
from cwc_fractal.types import CausalWindow  # noqa: E402

DEFAULT_PROTOCOL = PKG_ROOT / "experiments" / "cwc_fractal_protocol_v2.yaml"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_window(path: Path) -> CausalWindow:
    observations = []
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            observations.extend(observations_from_cwc_record(record, timestamp=count))
            count += 1
    if not observations:
        raise SystemExit(f"empty trace: {path}")
    return CausalWindow(end_timestamp=count - 1, observations=tuple(observations))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--synthetic-controls", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    seeds = (101, 211, 307)
    variable_traces = [args.trace_dir / f"seed{seed}_variable_72.jsonl" for seed in seeds]
    fixed_analyses = [args.analysis_dir / f"seed{seed}_fixed_64.json" for seed in seeds]
    variable_analyses = [args.analysis_dir / f"seed{seed}_variable_72.json" for seed in seeds]
    required = variable_traces + fixed_analyses + variable_analyses + [args.synthetic_controls]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"missing required inputs: {missing}")

    protocol = load_yaml(args.protocol)
    mappings = robust_mappings(protocol)
    analyses: dict[str, dict[str, Any]] = {}
    pass_count = 0
    pair_reports: dict[str, list[dict[str, Any]]] = {}
    for seed, path in zip(seeds, variable_analyses, strict=True):
        payload = json.loads(path.read_text(encoding="utf-8"))
        analyses[str(seed)] = payload
        null_eval = payload.get("null_evaluation") or {}
        passed = bool(null_eval.get("passed", False))
        pass_count += int(passed)
        pair_reports[str(seed)] = list(payload["coherence"]["pair_reports"])

    synthetic = json.loads(args.synthetic_controls.read_text(encoding="utf-8"))
    calibration_pass = bool(synthetic.get("calibration_pass", False))
    fixed_identifiable = 0
    for path in fixed_analyses:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("verdict")
            != "MULTISCALE_ORGANIZATION_NOT_IDENTIFIABLE_UNDER_CURRENT_INSTRUMENTATION"
        ):
            fixed_identifiable += 1

    windows = [load_window(path) for path in variable_traces]
    pooled = evaluate_programme_nulls(
        windows,
        mappings=mappings,
        confounder_strata=protocol["confounder_strata"],
        null_models=protocol["null_models"],
        iterations=args.iterations,
        seed=args.seed,
    )
    replication_veto = pass_count < 2
    # Since ADV-02 was introduced after inspecting per-trace data, it can only veto/narrow.
    generalized_support_authorized = False
    if replication_veto:
        verdict = "CROSS_SEED_RESIDUAL_MULTISCALE_ORGANIZATION_NOT_REPLICATED"
    elif not calibration_pass:
        verdict = "PROGRAMME_SYNTHESIS_BLOCKED_BY_SYNTHETIC_CALIBRATION"
    else:
        verdict = "POSTHOC_SYNTHESIS_NONAUTHORITATIVE_REQUIRES_PROSPECTIVE_REPLICATION"

    payload = {
        "schema_version": "cwc.fractal.replication_audit.v1",
        "protocol_id": protocol["protocol_id"],
        "seeds": list(seeds),
        "input_hashes": {str(path): sha256(path) for path in required},
        "variable_trace_pass_count": pass_count,
        "variable_trace_total": len(seeds),
        "variable_trace_pass_fraction": pass_count / len(seeds),
        "replication_veto_triggered": replication_veto,
        "fixed_shape_identifiable_count": fixed_identifiable,
        "fixed_shape_total": len(seeds),
        "synthetic_control_calibration_pass": calibration_pass,
        "pooled_null_diagnostic": pooled.to_dict(),
        "pair_diagnostics": cross_seed_pair_diagnostics(pair_reports),
        "verdict": verdict,
        "generalized_support_authorized": generalized_support_authorized,
        "scientific_ascension_authority": False,
        "via_authority": False,
        "claim_boundary": (
            "This is a post-hoc one-way replication veto and exploratory pooled null diagnostic. "
            "It can narrow or reject generalized support but cannot upgrade inspected data to a "
            "confirmatory positive claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
