#!/usr/bin/env python3
"""Independent verifier for sealed NPI-01 result.

Does not import scripts.npi_01_falsifier. Recomputes the exact polynomial
counterexample from serialized fractions and checks the frozen verdict boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path

EXPECTED = "NPI_01_FIRST_ORDER_CERTIFICATE_NOT_SUPPORTED"
EXPECTED_RADII = {
    Fraction(1, 1),
    Fraction(1, 10),
    Fraction(1, 100),
    Fraction(1, 10_000),
    Fraction(1, 100_000_000),
}


def frac(s: str) -> Fraction:
    return Fraction(s)


def verify(result_path: Path, verdict_path: Path) -> list[str]:
    errors: list[str] = []
    raw = json.loads(result_path.read_text(encoding="utf-8"))
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))

    if raw.get("verdict") != EXPECTED:
        errors.append("raw verdict mismatch")
    if verdict.get("verdict") != EXPECTED or verdict.get("status") != "NOT_SUPPORTED":
        errors.append("sealed verdict mismatch")
    if raw.get("mutation_kill_count") != 6 or raw.get("mutation_total") != 6:
        errors.append("mutation kill count mismatch")
    if set(frac(r["radius"]) for r in raw.get("radii", [])) != EXPECTED_RADII:
        errors.append("frozen radius set mismatch")

    cert = raw.get("local_certificate", {})
    if cert.get("margin") != "1/1":
        errors.append("baseline margin mismatch")
    if cert.get("jacobian") != [["1/1", "0/1"]]:
        errors.append("jacobian mismatch")
    if cert.get("nullspace_basis") != [["0/1", "1/1"]]:
        errors.append("nullspace mismatch")
    if cert.get("gradient") != ["0/1", "0/1"] or cert.get("score_squared") != "0/1":
        errors.append("first-order score mismatch")

    for row in raw.get("radii", []):
        r = frac(row["radius"])
        k = frac(row["k"])
        d = frac(row["distance"])
        u, v = (frac(x) for x in row["test_point"])
        if u != 0:
            errors.append(f"nonzero u at radius {r}")
        if not d < r or d != abs(v):
            errors.append(f"point not strictly inside radius {r}")
        if k * r * r != 8:
            errors.append(f"curvature scaling mismatch at radius {r}")
        if v != r / 2:
            errors.append(f"test point scaling mismatch at radius {r}")
        delta = Fraction(1) - k * v * v
        if delta != -1:
            errors.append(f"action did not reverse exactly at radius {r}")
        for field in ("observation_equal", "inside_radius", "baseline_margin_positive", "score_zero", "reversed_action", "nullspace_valid", "passed"):
            if row.get(field) is not True:
                errors.append(f"serialized predicate {field} false at radius {r}")

    return errors


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/npi-01"))
    args = parser.parse_args()
    result_path = args.artifact_dir / "raw_result.json"
    verdict_path = args.artifact_dir / "verdict.json"
    errors = verify(result_path, verdict_path)
    report = {
        "verdict": "PASS" if not errors else "FAIL",
        "errors": errors,
        "raw_result_sha256": checksum(result_path),
        "sealed_verdict_sha256": checksum(verdict_path),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
