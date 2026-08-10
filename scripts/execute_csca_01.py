from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys

from cwc.research_ops.provenance import sha256_file, stable_json_sha256
from cwc.research_ops.telemetry import append_telemetry, run_with_telemetry

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "research/registry/rd02_pipeline_state.json"
ART = ROOT / "artifacts/csca-01"
TELEMETRY = ROOT / "research/results/CSCA-01/run_telemetry.jsonl"

RUNS = [
    ("PRIMARY", 12000, 32, "NORMAL", ART / "primary"),
    ("REPLICATION", 22000, 32, "NORMAL", ART / "replication"),
    ("NULL_DESTROY", 32000, 16, "DESTROY_CAUSAL_LINK", ART / "null_destroy"),
    ("NULL_CORRELATION", 33000, 16, "CORRELATION_ONLY", ART / "null_correlation"),
    ("NULL_PURE_NOISE", 34000, 16, "PURE_NOISE", ART / "null_pure_noise"),
    ("STRESS_HIGH_NOISE", 35000, 16, "HIGH_NOISE", ART / "stress_high_noise"),
]


def git_clean() -> bool:
    out = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    return not out.strip()


def main() -> int:
    if not STATE.exists():
        raise SystemExit("rd02 bootstrap state missing")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if not state.get("mechanism_test_authority"):
        raise SystemExit("compute governor did not authorize CSCA-01 mechanism test")
    if not git_clean():
        raise SystemExit("refuse experiment execution from dirty git tree; freeze implementation first")

    TELEMETRY.parent.mkdir(parents=True, exist_ok=True)
    if TELEMETRY.exists():
        TELEMETRY.unlink()

    run_py = ROOT / "experiments/csca_01/run.py"
    prereg = ROOT / "experiments/csca_01/PREREGISTRATION.md"
    overall = 0
    for run_id, seed_start, seed_count, mode, out in RUNS:
        dataset_hash = stable_json_sha256({
            "generator_sha256": sha256_file(run_py),
            "preregistration_sha256": sha256_file(prereg),
            "seed_start": seed_start,
            "seed_count": seed_count,
            "mode": mode,
        })
        command = [
            sys.executable,
            str(run_py),
            "--seed-start", str(seed_start),
            "--seed-count", str(seed_count),
            "--mode", mode,
            "--out", str(out),
        ]
        telemetry, proc = run_with_telemetry(
            root=ROOT,
            run_id=f"CSCA-01-{run_id}",
            command=command,
            dataset_hash=dataset_hash,
            seed=f"{seed_start}:{seed_start + seed_count - 1}",
            artifact_paths=(),
        )
        # Hash artifacts after the process has created them.
        summary = out / "summary.json"
        results = out / "seed_results.csv"
        hashes = {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in (summary, results)
            if path.exists()
        }
        telemetry = type(telemetry)(**{**asdict(telemetry), "artifact_hashes": hashes})
        append_telemetry(TELEMETRY, telemetry)
        (out / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
        (out / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
        overall = overall or proc.returncode
        print(f"{run_id}: exit={proc.returncode} wall={telemetry.wall_seconds:.3f}s")
        if proc.returncode != 0:
            break
    return int(overall)


if __name__ == "__main__":
    raise SystemExit(main())
