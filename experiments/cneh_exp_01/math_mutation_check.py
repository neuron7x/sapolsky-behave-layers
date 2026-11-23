"""Seven fixed numerical-qualification mutants using the existing mutation runner.

Requires the locked optional NumPy/SciPy runtime and an explicit pinned PR44
reference. Only unittest assertion failures count as kills. Original sources,
including PR44 and CWC, are never edited; every execution uses a fresh copy.
"""
from __future__ import annotations

import argparse
import difflib
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.cneh_exp_01 import math_qualification as qualification
from experiments.cneh_exp_01.mutation_check import (
    canonical, classify, execute, materialize, sha, valid_summary, write_new,
)

SOURCE = "experiments/cneh_exp_01/math_qualification.py"
TEST_SOURCE = "tests/cneh_math/qualification_cases.py"
CATALOG = (
    ("hankel_stability_guard_omitted",
     'if not np.allclose(values, expected, atol=self.numerics["absolute_tolerance"],',
     'if False and not np.allclose(values, expected, atol=self.numerics["absolute_tolerance"],'),
    ("fisher_stability_guard_omitted",
     'if (minimum <= 0 or not math.isfinite(minimum) or not math.isfinite(condition)',
     'if False and (minimum <= 0 or not math.isfinite(minimum) or not math.isfinite(condition)'),
    ("training_leakage_guard_omitted",
     'if set(units).intersection(training_unit_ids):',
     'if False and set(units).intersection(training_unit_ids):'),
    ("randomized_fixture_guard_omitted",
     'if (len(units) != 4 or len(set(units)) != 4 or set(units) != set(assignments)',
     'if False and (len(units) != 4 or len(set(units)) != 4 or set(units) != set(assignments)'),
    ("report_semantic_guard_omitted", 'if canonical(observed) != canonical(expected):',
     'if False and canonical(observed) != canonical(expected):'),
    ("parameter_information_wrong_scale", 'return result\n\n    def local_identifiability',
     'return result * 2\n\n    def local_identifiability'),
    ("do_replacement_ignored", '            y = x if model == "causal" else u\n            law =',
     '            y = u\n            law ='),
)


def snapshot(reference: Path) -> dict[str, bytes]:
    paths = [HERE / name for name in (
        "math_qualification.py", "math_qualification_contract.json", "math_mutation_check.py",
        "mutation_check.py", "run.py", "bnsyn-requirements.lock")]
    paths += [REPO / "cwc/__init__.py", *sorted((REPO / "cwc/causal").glob("*.py"))]
    paths += [REPO / TEST_SOURCE]
    data = {}
    for path in [*paths, reference]:
        if path.is_symlink() or not path.is_file():
            raise ValueError("mutation inputs must be regular nonsymlink files")
    for path in paths:
        data[path.relative_to(REPO).as_posix()] = path.read_bytes()
    # The shared unittest runner discovers a named suite directly under tests/.
    data["tests/qualification_cases.py"] = data.pop(TEST_SOURCE)
    data["external/pr44-reference.py"] = reference.read_bytes()
    return data


def run_copy(data: dict[str, bytes], destination: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="cneh-math-mutation-") as directory:
        root = Path(directory)
        materialize(root, data)
        previous = os.environ.get("CNEH_PR44_REFERENCE")
        os.environ["CNEH_PR44_REFERENCE"] = str(root / "external/pr44-reference.py")
        try:
            return execute(root, "qualification_cases.py", destination, 60.0, site_packages=True)
        finally:
            if previous is None:
                os.environ.pop("CNEH_PR44_REFERENCE", None)
            else:
                os.environ["CNEH_PR44_REFERENCE"] = previous


def calibrate(out: Path, reference: Path) -> dict:
    qualification.QualificationBridge(reference)  # Pin runtime, reference and CWC before execution.
    data = snapshot(reference)
    manifest = {name: sha(value) for name, value in data.items()}
    out.mkdir(parents=True, exist_ok=False)
    write_new(out / "source_manifest.json", canonical(manifest))
    write_new(out / "catalog.json", canonical(CATALOG))
    report = {"schema": "cneh-math-mutation-v1", "status": "NOT_RUN", "killed": 0,
              "total": len(CATALOG), "minimum_baseline_tests": 14,
              "authority": "ANALYTIC_TEST_CALIBRATION_ONLY", "scientific_promotion_authorized": False,
              "source_sha256": manifest, "source_tree_sha256": sha(canonical(manifest)),
              "catalog_sha256": sha(canonical(CATALOG)), "test_source_path": TEST_SOURCE,
              "runtime": {"python": sys.version, "numpy": qualification.np.__version__,
                          "scipy": qualification.scipy.__version__}, "mutants": []}
    baseline_dir = out / "baseline"
    baseline_dir.mkdir()
    baseline = run_copy(data, baseline_dir)
    write_new(baseline_dir / "result.json", canonical(baseline))
    report["baseline"] = baseline
    passed = (valid_summary(baseline) and baseline["exit_code"] == 0
              and baseline["unittest"]["successful"] and not baseline["unittest"]["failure_test_ids"]
              and baseline["unittest"]["tests_run"] >= report["minimum_baseline_tests"])
    if not passed:
        report["status"] = "BASELINE_FAIL"
    else:
        original = data[SOURCE].decode()
        for name, before, after in CATALOG:
            directory = out / name
            directory.mkdir()
            record = {"id": name, "before": before, "after": after, "source_sha256": sha(data[SOURCE]),
                      "anchor_occurrences": original.count(before), "status": "INVALID_MUTANT"}
            if record["anchor_occurrences"] != 1:
                record["reason"] = "replacement must match exactly once"
            else:
                modified = original.replace(before, after, 1)
                patch = "".join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                                                    fromfile=SOURCE, tofile=SOURCE))
                write_new(directory / "mutation.patch", patch.encode())
                record.update(patch_sha256=sha(patch.encode()), mutated_source_sha256=sha(modified.encode()))
                result = run_copy({**data, SOURCE: modified.encode()}, directory)
                record.update(result)
                record["status"] = classify(result, baseline_count=baseline["unittest"]["tests_run"])
            write_new(directory / "result.json", canonical(record))
            report["mutants"].append(record)
        report["killed"] = sum(row["status"] == "KILLED" for row in report["mutants"])
        report["status"] = "PASS" if report["killed"] == report["total"] else "FAIL"
    report["source_unchanged_during_run"] = snapshot(reference) == data
    if not report["source_unchanged_during_run"]:
        report["status"] = "SOURCE_DRIFT"
    write_new(out / "report.json", canonical(report))
    files = sorted(path for path in out.rglob("*") if path.is_file())
    write_new(out / "SHA256SUMS", "".join(
        f"{sha(path.read_bytes())}  {path.relative_to(out).as_posix()}\n" for path in files).encode())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = calibrate(args.out, args.reference)
    except (OSError, ValueError) as error:
        print(canonical({"status": "INVALID", "error": str(error)}).decode(), end="")
        return 1
    print(f'{report["status"]}: {report["killed"]}/{report["total"]} numerical mutants killed')
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
