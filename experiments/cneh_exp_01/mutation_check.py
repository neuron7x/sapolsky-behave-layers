"""Fixed engineering mutation calibration; not scientific validation.

Each mutant runs the existing tests in a fresh, isolated copy. Only assertion
failures count as kills. Import/runtime errors, timeouts, source drift, missing
tests, skips, invalid substitutions and survivors make the command fail closed.
The catalog is deliberately finite and does not claim exhaustive mutation coverage.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PACKAGE = Path("experiments/cneh_exp_01")

# One exact source replacement per entry. An upstream source change requires
# reviewing the scientific/engineering meaning of the replacement, not guessing.
CATALOG = (
    {"id": "runner_rounded_trace", "file": "run.py", "test": "test_cneh_exp_01.py",
     "before": "return digest(canonical([[v.hex() for v in row] for row in actions_states]))",
     "after": "return digest(canonical([[round(v, 12) for v in row] for row in actions_states]))"},
    {"id": "runner_memory_envelope_omitted", "file": "run.py", "test": "test_cneh_exp_01.py",
     "before": '                 CONTROLLER_MEMORY_PROXY_BYTES <= budget["controller_memory_proxy_bytes_max"] and\n',
     "after": ""},
    {"id": "runner_sidecar_semantics_omitted", "file": "run.py", "test": "test_cneh_exp_01.py",
     "before": "if canonical(actual_artifact) != canonical(expected_artifact):",
     "after": "if False and canonical(actual_artifact) != canonical(expected_artifact):"},
    {"id": "runner_actuator_bound_omitted", "file": "run.py", "test": "test_cneh_exp_01.py",
     "before": 'if max(abs(u0), abs(u1)) > p["actuator_bound"]:',
     "after": 'if False and max(abs(u0), abs(u1)) > p["actuator_bound"]:'},
    {"id": "replication_commitment_binding_omitted", "file": "replication.py",
     "test": "test_cneh_exp_01_replication.py",
     "before": 'if not hmac.compare_digest(observed, commitment["commitment_sha256"]):',
     "after": 'if False and not hmac.compare_digest(observed, commitment["commitment_sha256"]):'},
    {"id": "replication_independence_overclaim", "file": "replication.py",
     "test": "test_cneh_exp_01_replication.py",
     "before": '"independent_blind_replication": False',
     "after": '"independent_blind_replication": True'},
    {"id": "fisher_wrong_variance_scaling", "file": "estimators.py",
     "test": "test_cneh_exp_01_estimators.py",
     "before": "math.fsum(row[a] * row[b] for row in j) / variance",
     "after": "math.fsum(row[a] * row[b] for row in j) * variance"},
    {"id": "gramian_missing_final_observation", "file": "estimators.py",
     "test": "test_cneh_exp_01_estimators.py",
     "before": "for t in range(horizon):", "after": "for t in range(horizon - 1):"},
    {"id": "pid_nats_mislabeled_as_bits", "file": "estimators.py",
     "test": "test_cneh_exp_01_estimators.py",
     "before": "math.log2((v / py[y]) / ps[s])",
     "after": "math.log((v / py[y]) / ps[s])"},
    {"id": "hardware_emulator_parity_omitted", "file": "hardware.py",
     "test": "test_cneh_exp_01_hardware.py",
     "before": 'if any(trace_by_seed_arm[s, "COUPLED"] != trace_by_seed_arm[s, "CENTRAL_EMULATOR"] for s in plan["seeds"]):',
     "after": 'if False and any(trace_by_seed_arm[s, "COUPLED"] != trace_by_seed_arm[s, "CENTRAL_EMULATOR"] for s in plan["seeds"]):'},
    {"id": "hardware_unmeasured_cost_overclaim", "file": "hardware.py",
     "test": "test_cneh_exp_01_hardware.py",
     "before": '"cost_status": "COST_INSTRUMENT_INVALID"',
     "after": '"cost_status": "COST_INSTRUMENT_VALID"'},
)

# Structured unittest outcomes avoid interpreting a traceback or a nonzero
# interpreter exit as a successful kill. The full standard runner log is retained.
TEST_RUNNER = """import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
suite = unittest.defaultTestLoader.discover('tests', pattern=sys.argv[1])
result = unittest.TextTestRunner(verbosity=2).run(suite)
summary = {
    'tests_run': result.testsRun,
    'failure_test_ids': [test.id() for test, _ in result.failures],
    'error_test_ids': [test.id() for test, _ in result.errors],
    'skipped': len(result.skipped),
    'expected_failures': len(result.expectedFailures),
    'unexpected_successes': len(result.unexpectedSuccesses),
    'successful': result.wasSuccessful(),
}
with Path(sys.argv[2]).open('x', encoding='utf-8') as stream:
    json.dump(summary, stream, sort_keys=True)
    stream.write('\\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
"""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)


def source_snapshot() -> dict[str, bytes]:
    """Read only this package and the four test suites exercised by the catalog."""
    paths = [p for p in HERE.iterdir()
             if p.suffix in (".py", ".json", ".md", ".lock")]
    paths.extend(REPO / "tests" / name for name in sorted({m["test"] for m in CATALOG}))
    result = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"source must be a regular nonsymlink file: {path.name}")
        result[path.relative_to(REPO).as_posix()] = path.read_bytes()
    return result


def materialize(root: Path, snapshot: dict[str, bytes]) -> None:
    for relative, data in snapshot.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        write_new(path, data)


def execute(root: Path, test_file: str, destination: Path, timeout: float, *,
            site_packages: bool = False) -> dict[str, Any]:
    summary_path = root / "unittest-result.json"
    flags = ["-I"] + ([] if site_packages else ["-S"])
    command = [sys.executable, *flags, "-c", TEST_RUNNER, test_file, str(summary_path)]
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            # The child can exit between timeout detection and killpg. It is
            # still classified as timed out; collect its streams below.
            pass
        stdout, stderr = process.communicate()
    write_new(destination / "stdout.log", stdout.encode())
    write_new(destination / "stderr.log", stderr.encode())
    summary = None
    summary_error = None
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as error:
            summary_error = str(error)
    return {"command": command, "working_directory": str(root),
            "exit_code": process.returncode, "timed_out": timed_out,
            "elapsed_seconds": time.perf_counter() - started,
            "unittest": summary, "summary_error": summary_error,
            "stdout_sha256": sha(stdout.encode()), "stderr_sha256": sha(stderr.encode())}


def valid_summary(run: dict[str, Any]) -> bool:
    result = run["unittest"]
    if run["timed_out"] or run["summary_error"] is not None or type(result) is not dict:
        return False
    fields = {"tests_run", "failure_test_ids", "error_test_ids", "skipped",
              "expected_failures", "unexpected_successes", "successful"}
    return (set(result) == fields and type(result["tests_run"]) is int
            and result["tests_run"] > 0 and type(result["successful"]) is bool
            and all(type(result[k]) is list and all(type(x) is str for x in result[k])
                    for k in ("failure_test_ids", "error_test_ids"))
            and all(type(result[k]) is int and result[k] == 0
                    for k in ("skipped", "expected_failures", "unexpected_successes"))
            and not result["error_test_ids"])


def classify(run: dict[str, Any], *, baseline_count: int) -> str:
    if not valid_summary(run) or run["unittest"]["tests_run"] != baseline_count:
        return "INVALID_MUTANT"
    result = run["unittest"]
    if run["exit_code"] == 1 and result["failure_test_ids"] and not result["successful"]:
        return "KILLED"
    if run["exit_code"] == 0 and not result["failure_test_ids"] and result["successful"]:
        return "SURVIVED"
    return "INVALID_MUTANT"


def calibrate(out: Path, timeout: float = 60.0) -> dict[str, Any]:
    if not 0 < timeout <= 120:
        raise ValueError("per-process timeout must be in (0,120] seconds")
    snapshot = source_snapshot()
    manifest = {name: sha(data) for name, data in snapshot.items()}
    out.mkdir(parents=True, exist_ok=False)
    write_new(out / "source_manifest.json", canonical(manifest))
    write_new(out / "catalog.json", canonical(CATALOG))
    report: dict[str, Any] = {
        "schema": "cneh-targeted-mutation-v1", "status": "NOT_RUN",
        "authority": "ENGINEERING_TEST_CALIBRATION_ONLY",
        "scientific_promotion_authorized": False,
        "source_tree_sha256": sha(canonical(manifest)), "source_sha256": manifest,
        "catalog_sha256": sha(canonical(CATALOG)),
        "timeout_seconds": timeout, "baselines": [], "mutants": [],
        "killed": 0, "total": len(CATALOG),
    }
    baselines = {}
    for test_file in sorted({m["test"] for m in CATALOG}):
        destination = out / ("baseline-" + Path(test_file).stem)
        destination.mkdir()
        with tempfile.TemporaryDirectory(prefix="cneh-mutation-baseline-") as directory:
            root = Path(directory)
            materialize(root, snapshot)
            result = execute(root, test_file, destination, timeout)
        passed = (valid_summary(result) and result["exit_code"] == 0
                  and result["unittest"]["successful"]
                  and not result["unittest"]["failure_test_ids"])
        result.update({"test": test_file, "status": "PASS" if passed else "FAIL"})
        write_new(destination / "result.json", canonical(result))
        report["baselines"].append(result)
        if passed:
            baselines[test_file] = result["unittest"]["tests_run"]
    if len(baselines) != len({m["test"] for m in CATALOG}):
        report["status"] = "BASELINE_FAIL"
    else:
        for mutation in CATALOG:
            destination = out / mutation["id"]
            destination.mkdir()
            relative = (PACKAGE / mutation["file"]).as_posix()
            before = snapshot[relative].decode("utf-8")
            record = {**mutation, "source_sha256": sha(snapshot[relative]),
                      "anchor_occurrences": before.count(mutation["before"])}
            if record["anchor_occurrences"] != 1:
                record.update({"status": "INVALID_MUTANT", "reason": "replacement must match exactly once"})
            else:
                after = before.replace(mutation["before"], mutation["after"], 1)
                patch = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                    fromfile=relative, tofile=relative))
                write_new(destination / "mutation.patch", patch.encode())
                record.update({"patch_sha256": sha(patch.encode()),
                               "mutated_source_sha256": sha(after.encode())})
                with tempfile.TemporaryDirectory(prefix="cneh-mutation-") as directory:
                    root = Path(directory)
                    modified = {**snapshot, relative: after.encode()}
                    materialize(root, modified)
                    result = execute(root, mutation["test"], destination, timeout)
                record.update(result)
                record["status"] = classify(result, baseline_count=baselines[mutation["test"]])
            write_new(destination / "result.json", canonical(record))
            report["mutants"].append(record)
        report["killed"] = sum(m["status"] == "KILLED" for m in report["mutants"])
        report["status"] = "PASS" if report["killed"] == report["total"] else "FAIL"
    current = {name: sha(data) for name, data in source_snapshot().items()}
    report["source_unchanged_during_run"] = current == manifest
    if current != manifest:
        report["status"] = "SOURCE_DRIFT"
    write_new(out / "report.json", canonical(report))
    files = sorted(path for path in out.rglob("*") if path.is_file())
    write_new(out / "SHA256SUMS", "".join(
        f"{sha(path.read_bytes())}  {path.relative_to(out).as_posix()}\n" for path in files).encode())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = calibrate(args.out)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "INVALID", "error": str(error)}))
        return 1
    print(f'{report["status"]}: {report["killed"]}/{report["total"]} targeted mutants killed')
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
