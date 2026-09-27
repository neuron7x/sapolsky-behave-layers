from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from scripts import architecture_gate, build_sbom, complexity_gate, hermeticity_gate, inference_integrity_gate

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/dgc-04-software-triage"
EXPERIMENT_ID = "DGC-04-SOFTWARE-TRIAGE"
ORDER = ("A", "H", "C", "S", "I")


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    faults: tuple[str, ...]
    changed_domains: tuple[str, ...]


TASKS = (
    Task("CLEAN", (), ORDER),
    Task("A", ("A",), ("A",)),
    Task("H", ("H",), ("H",)),
    Task("C", ("C",), ("C",)),
    Task("S", ("S",), ("S",)),
    Task("I", ("I",), ("I",)),
    Task("A+H", ("A", "H"), ("A", "H")),
    Task("C+S", ("C", "S"), ("C", "S")),
    Task("H+I", ("H", "I"), ("H", "I")),
    Task("A+C+S", ("A", "C", "S"), ("A", "C", "S")),
    Task("ALL", ORDER, ORDER),
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_fixture(destination: Path) -> None:
    for directory in ("cwc", "nanochat", "experiments/common", "scripts", "engineering", "docs/security"):
        source = ROOT / directory
        if source.exists():
            shutil.copytree(source, destination / directory)
    shutil.copy2(ROOT / "uv.lock", destination / "uv.lock")
    shutil.copy2(ROOT / "Makefile.cwc", destination / "Makefile.cwc")


def _inject(root: Path, code: str) -> None:
    if code == "A":
        path = root / "cwc/instrumentation/breach.py"
        path.write_text("import cwc.plasticity.optimizer\n", encoding="utf-8")
    elif code == "H":
        path = root / "scripts/reproduce_primary.py"
        path.write_text(path.read_text(encoding="utf-8") + "\nimport requests\n", encoding="utf-8")
    elif code == "C":
        path = root / complexity_gate.CONTRACT
        data = json.loads(path.read_text(encoding="utf-8"))
        data["budgets"][0]["max_cyclomatic"] = 0
        path.write_text(json.dumps(data), encoding="utf-8")
    elif code == "S":
        path = root / build_sbom.DEFAULT_OUTPUT
        data = json.loads(path.read_text(encoding="utf-8"))
        data["components"][0]["version"] = "0.0.0-dgc04-corrupted"
        path.write_text(json.dumps(data), encoding="utf-8")
    elif code == "I":
        path = root / "nanochat/engine.py"
        text = path.read_text(encoding="utf-8")
        mutated = text.replace("validate_logits(logits)", "pass  # DGC04 validation bypass")
        if mutated == text:
            raise RuntimeError("inference mutation anchor missing")
        path.write_text(mutated, encoding="utf-8")
    else:
        raise KeyError(code)


Validator = Callable[[Path], list[str]]
VALIDATORS: dict[str, Validator] = {
    "A": architecture_gate.validate,
    "H": hermeticity_gate.validate,
    "C": complexity_gate.validate,
    "S": build_sbom.validate,
    "I": inference_integrity_gate.validate,
}


def _run_validator(code: str, root: Path) -> tuple[bool, int, int]:
    start = time.perf_counter_ns()
    errors = VALIDATORS[code](root)
    elapsed = time.perf_counter_ns() - start
    return bool(errors), len(errors), elapsed


def _execute(policy: str, task: Task, root: Path) -> dict[str, object]:
    if policy == "B0_FULL":
        schedule = list(ORDER)
        stop_on_detection = False
    elif policy == "B1_PATH_ROUTER":
        schedule = [code for code in ORDER if code in task.changed_domains]
        stop_on_detection = False
    elif policy == "B2_DGC":
        schedule = [code for code in ORDER if code in task.changed_domains]
        stop_on_detection = True
    else:
        raise KeyError(policy)

    calls: list[dict[str, object]] = []
    detected_any = False
    for code in schedule:
        detected, error_count, elapsed_ns = _run_validator(code, root)
        calls.append({
            "diagnostic": code,
            "detected": detected,
            "error_count": error_count,
            "elapsed_ns": elapsed_ns,
        })
        if detected:
            detected_any = True
            if stop_on_detection:
                break

    action = "RELEASE_DENY" if detected_any else "RELEASE_PASS"
    truth = "RELEASE_DENY" if task.faults else "RELEASE_PASS"
    return {
        "policy": policy,
        "task_id": task.task_id,
        "truth": truth,
        "action": action,
        "correct": action == truth,
        "false_pass": action == "RELEASE_PASS" and truth == "RELEASE_DENY",
        "validator_calls": len(calls),
        "validator_elapsed_ns": sum(int(c["elapsed_ns"]) for c in calls),
        "first_detected": next((str(c["diagnostic"]) for c in calls if c["detected"]), None),
        "calls": calls,
    }


def run() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for task in TASKS:
        with tempfile.TemporaryDirectory(prefix=f"dgc04-{task.task_id.replace('+','_')}-") as tmp:
            root = Path(tmp)
            _copy_fixture(root)
            for fault in task.faults:
                _inject(root, fault)
            for policy in ("B0_FULL", "B1_PATH_ROUTER", "B2_DGC"):
                rows.append(_execute(policy, task, root))

    summaries: dict[str, dict[str, object]] = {}
    for policy in ("B0_FULL", "B1_PATH_ROUTER", "B2_DGC"):
        selected = [row for row in rows if row["policy"] == policy]
        summaries[policy] = {
            "tasks": len(selected),
            "decision_accuracy": sum(bool(row["correct"]) for row in selected) / len(selected),
            "false_pass_count": sum(bool(row["false_pass"]) for row in selected),
            "validator_calls": sum(int(row["validator_calls"]) for row in selected),
            "validator_elapsed_ns": sum(int(row["validator_elapsed_ns"]) for row in selected),
            "task_coverage": len({str(row["task_id"]) for row in selected}) / len(TASKS),
        }
    b0, b1, b2 = summaries["B0_FULL"], summaries["B1_PATH_ROUTER"], summaries["B2_DGC"]
    b2["call_savings_vs_b0"] = 1.0 - int(b2["validator_calls"]) / int(b0["validator_calls"])
    b2["call_savings_vs_b1"] = 1.0 - int(b2["validator_calls"]) / int(b1["validator_calls"])
    b2["wall_time_savings_vs_b0"] = 1.0 - int(b2["validator_elapsed_ns"]) / int(b0["validator_elapsed_ns"])
    b2["wall_time_savings_vs_b1"] = 1.0 - int(b2["validator_elapsed_ns"]) / int(b1["validator_elapsed_ns"])

    failing_b2 = [row for row in rows if row["policy"] == "B2_DGC" and row["truth"] == "RELEASE_DENY"]
    each_failing_task_has_detection = all(row["first_detected"] is not None for row in failing_b2)
    passed = (
        b2["decision_accuracy"] == 1.0
        and b2["false_pass_count"] == 0
        and int(b2["validator_calls"]) < int(b1["validator_calls"]) < int(b0["validator_calls"])
        and b2["task_coverage"] == 1.0
        and each_failing_task_has_detection
    )
    verdict = "SOFTWARE_TRIAGE_SUPPORTED_NARROW" if passed else "SOFTWARE_TRIAGE_NOT_SUPPORTED"
    out = {
        "experiment": EXPERIMENT_ID,
        "status": verdict,
        "preregistration_sha256": _sha256(ROOT / "experiments/dgc_04_software_triage/PREREGISTRATION.md"),
        "pre_execution_amendment_sha256": _sha256(ROOT / "experiments/dgc_04_software_triage/PRE_EXECUTION_AMENDMENT_001.md"),
        "task_count": len(TASKS),
        "diagnostic_order": list(ORDER),
        "summaries": summaries,
        "rows": rows,
        "authority": {
            "real_repository_validators": True,
            "real_disposable_fault_mutations": True,
            "llm_api_savings_claim": False,
            "client_verified": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": verdict, "summaries": summaries}, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    run()
