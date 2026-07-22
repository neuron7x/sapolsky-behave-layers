"""WP16 clean-room reproduction report (Act CWC-ASCEND-2026-01, G0/G1).

Runs the FULL canonical gate set with a caller-supplied python interpreter (intended: a freshly
built clean-room venv, NOT the author's .venv) and emits a machine-readable reproduction report:
host, GPU, driver, CUDA, PyTorch, seeds, per-gate exit code + wall time, and pytest skip counts
WITH reason codes. Any skipped hardware gate is recorded as NOT_MEASURED -- never PASS (Act WP16
acceptance). Exits non-zero if any non-hardware gate fails.

Usage: PYTHONPATH=. python scripts/wp16_reproduction_report.py --py /path/to/cleanroom/bin/python
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/wp16-cleanroom-release"

# Canonical gates. kind: "plain" (exit code is the verdict) or "pytest" (also parse skips/reasons).
GATES = [
    ("lint", "plain", ["-m", "ruff", "check", "."]),
    ("typecheck", "plain", ["-m", "mypy", "--config-file", "mypy.ini",
        "cwc/", "experiments/common/value_information.py",
        "experiments/common/adaptive_value_theory.py",
        "experiments/common/neuron_information_budget.py",
        "experiments/common/coherence_audit.py",
        "experiments/common/value_of_information_rate.py",
        "experiments/common/identifiability_inference.py",
        "scripts/instrumentation_smoke.py", "scripts/instrumentation_audit.py",
        "scripts/export_cwc_instrumentation_bundle.py", "scripts/mutation_probe.py"]),
    # GLOB, never a hard-coded file list (that is the fractal drift defect) -- mirror Makefile.cwc
    # `test`: tests/test_instrumentation_*.py + tests/test_evidence_validation.py.
    ("test", "pytest", ["-m", "pytest", "-q", "-rs", "-m", "not slow and not mutation",
        *sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_instrumentation_*.py")),
        "tests/test_evidence_validation.py"]),
    # coverage gate (Makefile.cwc `coverage`): 95% floor, CPU-tolerant.
    ("coverage", "pytest", ["-m", "pytest", "-q", "-rs", "-m", "not slow and not mutation",
        *sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_instrumentation_*.py")),
        "experiments/wp3_plasticity_v1/tests/",
        "--cov=cwc", "--cov-branch", "--cov-report=term-missing", "--cov-fail-under=95"]),
    ("mutation", "plain", ["scripts/mutation_probe.py"]),
    ("validate-evidence", "plain", ["scripts/validate_evidence.py"]),
    ("doc-gate", "plain", ["scripts/doc_status_gate.py"]),
    ("reproduce-primary", "plain", ["scripts/reproduce_primary.py"]),
]


def _run(py: str, args: list[str]) -> tuple[int, str, float]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONHASHSEED"] = "0"
    t0 = time.monotonic()
    r = subprocess.run([py, *args], cwd=ROOT, env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr, time.monotonic() - t0


def _pytest_out(py: str) -> tuple[int, str, float]:
    # experiment-tests: glob every experiments/*/tests (mirrors Makefile.cwc), excluding fractal.
    dirs = sorted(str(p) for p in (ROOT / "experiments").glob("*/tests")
                  if "fractal_multiscale" not in str(p) and "__pycache__" not in str(p))
    return _run(py, ["-m", "pytest", "-q", "-rs", *dirs])


def _skips(text: str) -> dict[str, Any]:
    m = re.search(r"(\d+) skipped", text)
    n = int(m.group(1)) if m else 0
    reasons = sorted(set(re.findall(r"SKIPPED \[\d+\] (.+?):\d+: (.+)", text)))
    hw = re.compile(r"cuda|gpu|nvml|pynvml|\bpower\b|energy|device|hardware", re.IGNORECASE)
    cuda = [r for r in reasons if hw.search(r[1])]
    return {"skipped": n, "reasons": [f"{f}: {why}" for f, why in reasons],
            "hardware_skips_not_measured": [f"{f}: {why}" for f, why in cuda]}


def _hw() -> dict[str, Any]:
    gpu = subprocess.run(["bash", "-c",
        "nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null"],
        capture_output=True, text=True).stdout.strip()
    return {"platform": platform.platform(), "machine": platform.machine(),
            "python": platform.python_version(), "gpu": gpu or "none/no-nvidia-smi"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--py", required=True, help="clean-room venv python")
    args = ap.parse_args()
    py = args.py

    torch_info = subprocess.run([py, "-c",
        "import torch,sys;print(torch.__version__);print(torch.cuda.is_available());"
        "print(torch.version.cuda)"], capture_output=True, text=True).stdout.split()
    tver, tcuda, tcudaver = (torch_info + ["?", "?", "?"])[:3]

    gates: list[dict[str, Any]] = []
    overall_ok = True
    for name, kind, spec in GATES:
        rc, out, dt = _run(py, spec)
        row: dict[str, Any] = {"gate": name, "exit_code": rc, "seconds": round(dt, 1),
                               "result": "PASS" if rc == 0 else "FAIL"}
        if kind == "pytest":
            row["pytest"] = _skips(out)
        gates.append(row)
        overall_ok = overall_ok and rc == 0

    rc, out, dt = _pytest_out(py)
    et = {"gate": "experiment-tests", "exit_code": rc, "seconds": round(dt, 1),
          "result": "PASS" if rc == 0 else "FAIL", "pytest": _skips(out)}
    gates.append(et)
    overall_ok = overall_ok and rc == 0

    # merge test-gate skips into a single hardware NOT_MEASURED list
    hw_not_measured = sorted({s for g in gates if "pytest" in g
                              for s in g["pytest"]["hardware_skips_not_measured"]})

    report = {
        "experiment": "wp16_cleanroom_release",
        "act": "CWC-ASCEND-2026-01 / WP16 G0-G1",
        "verdict": "CLEANROOM_REPRODUCTION_PASS" if overall_ok else "CLEANROOM_REPRODUCTION_FAIL",
        "interpreter": py,
        "note": "Full canonical gate set re-run in a FRESH venv built from uv.lock --frozen "
                "(independent of the author's .venv). Hardware-gated tests are NOT_MEASURED, "
                "never PASS. This closes the Act's audit boundary (capsule lacked exact .venv).",
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     capture_output=True, text=True).stdout.strip(),
        "host": _hw(),
        "torch": {"version": tver, "cuda_available": tcuda, "cuda_version": tcudaver},
        "seeds": {"PYTHONHASHSEED": "0"},
        "gates": gates,
        "hardware_not_measured": hw_not_measured,
        "second_independent_host": "NOT_MEASURED (single-host environment; Act WP16 3rd env "
                                   "requires an independent runner/host not available here)",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reproduction_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"WP16 reproduction: {report['verdict']}")
    for g in gates:
        extra = f" skipped={g['pytest']['skipped']}" if "pytest" in g else ""
        print(f"  {g['gate']:<20} {g['result']:<5} {g['seconds']:>6}s{extra}")
    if hw_not_measured:
        print("  hardware NOT_MEASURED:")
        for s in hw_not_measured:
            print(f"    - {s}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
