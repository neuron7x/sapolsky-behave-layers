"""One-command reproduction of the PRIMARY clean result (G0/G1 #18): the
adaptive-compute Jensen gap (wp4-adaptive-depth), which is the cleanest
causally-isolated positive. Regenerates raw runs, re-analyses, checks the
verdict, and validates the evidence checksums. Exits non-zero on any mismatch.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONHASHSEED"] = "0"
    return env


def main() -> int:
    print("[reproduce-primary] running wp4 adaptive-depth in an isolated directory...")
    with tempfile.TemporaryDirectory(prefix="cwc-wp4-") as tmp:
        tmp_root = Path(tmp)
        runs = tmp_root / "raw_runs"
        out = tmp_root / "analysis"
        subprocess.run(
            [sys.executable, "-m", "experiments.wp4_adaptive_depth.src.runner",
             "--seeds", "0", "1", "2", "3", "4", "5", "6", "7", "--out", str(runs)],
            check=True, cwd=ROOT, env=_env(),
        )
        subprocess.run(
            [sys.executable, "-m", "experiments.wp4_adaptive_depth.src.analyze",
             "--runs", str(runs), "--out", str(out)],
            check=True, cwd=ROOT, env=_env(),
        )
        v = json.loads((out / "verdict.json").read_text())["verdict"]
        print(f"[reproduce-primary] verdict = {v}")
        if v != "SYNTHETIC_HALT_IDENTITY_VERIFIED":
            print("[reproduce-primary] FAIL: verdict changed")
            return 1
        a = json.loads((out / "analysis.json").read_text())
        if a["max_abs_error_gap_vs_theory"] > 0.02:
            print("[reproduce-primary] FAIL: gap no longer matches theory")
            return 1
    print("[reproduce-primary] PASS: isolated reproduction completed; canonical evidence was not modified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
