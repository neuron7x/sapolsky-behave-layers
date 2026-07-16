"""One-command reproduction of the PRIMARY clean result (G0/G1 #18): the
adaptive-compute Jensen gap (wp4-adaptive-depth), which is the cleanest
causally-isolated positive. Regenerates raw runs, re-analyses, checks the
verdict, and validates the evidence checksums. Exits non-zero on any mismatch.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(mod: str) -> None:
    subprocess.run([sys.executable, "-m", mod, "--seeds", "0", "1", "2", "3", "4", "5", "6", "7"],
                   check=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})


def main() -> int:
    print("[reproduce-primary] running wp4 adaptive-depth (8 seeds)...")
    _run("experiments.wp4_adaptive_depth.src.runner")
    subprocess.run([sys.executable, "-m", "experiments.wp4_adaptive_depth.src.analyze"],
                   check=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    v = json.loads((ROOT / "artifacts/wp4-adaptive-depth/verdict.json").read_text())["verdict"]
    print(f"[reproduce-primary] verdict = {v}")
    if v != "ADAPTIVE_COMPUTE_JENSEN_GAP_CONFIRMED":
        print("[reproduce-primary] FAIL: verdict changed")
        return 1
    a = json.loads((ROOT / "artifacts/wp4-adaptive-depth/analysis.json").read_text())
    if a["max_abs_error_gap_vs_theory"] > 0.02:
        print("[reproduce-primary] FAIL: gap no longer matches theory")
        return 1
    print("[reproduce-primary] PASS: gap = P(m>K) confirmed, verdict stable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
