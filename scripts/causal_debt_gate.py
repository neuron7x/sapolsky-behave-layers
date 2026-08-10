"""Fail-closed governance gate for the deferred causal-credit research branch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "docs/acts/CWC_CDL_01.md",
    "docs/acts/CWC_CDL_02.md",
    "cwc/memory/causal_debt.py",
    "cwc/replay/scheduler.py",
    "experiments/causal_debt_v1/PREREGISTRATION.md",
    "experiments/causal_debt_v1/protocol.json",
    "experiments/causal_debt_v2/PREREGISTRATION.md",
    "experiments/causal_debt_v2/protocol.json",
    "artifacts/causal-debt-v1/verdict.json",
    "artifacts/causal-debt-v2/verdict.json",
    "artifacts/causal-debt-program/verdict.json",
    "artifacts/causal-debt-program/EXECUTION_REPORT.md",
]


def _read(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text())
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected object")
    return obj


def _verify_sumfile(directory: Path) -> list[str]:
    errors: list[str] = []
    sums = directory / "SHA256SUMS"
    if not sums.exists():
        return [f"missing checksum ledger: {sums.relative_to(ROOT)}"]
    for line in sums.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append(f"malformed checksum line in {sums.relative_to(ROOT)}")
            continue
        expected, rel = parts[0], parts[1].strip().lstrip("*")
        target = directory / rel
        if not target.is_file():
            errors.append(f"checksum target missing: {target.relative_to(ROOT)}")
            continue
        got = hashlib.sha256(target.read_bytes()).hexdigest()
        if got != expected:
            errors.append(f"checksum mismatch: {target.relative_to(ROOT)}")
    return errors


def audit_documents(v1: dict[str, Any], v2: dict[str, Any], program: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if v1.get("verdict") != "CAUSAL_DEBT_CONTROL_NOT_QUALIFIED":
        errors.append("V1 negative verdict changed or missing")
    if v1.get("scientific_pass") is not False:
        errors.append("V1 must not carry scientific PASS")
    if v1.get("via_ascension_authorized", v1.get("via_ascension_authority")) is True:
        errors.append("V1 must not authorize VIA ascension")
    if v1.get("biological_claim_authorized") is not False:
        errors.append("V1 must not authorize a biological claim")

    allowed = {"CAUSAL_DEBT_V2_CONTROL_QUALIFIED", "CAUSAL_DEBT_V2_CONTROL_NOT_QUALIFIED"}
    if v2.get("verdict") not in allowed:
        errors.append("V2 verdict is outside the closed vocabulary")
    if v2.get("parent_verdict") != v1.get("verdict"):
        errors.append("V2 is not bound to the V1 negative parent")
    if v2.get("scientific_pass") is not False:
        errors.append("V2 synthetic control must not be scientific PASS")
    if v2.get("via_ascension_authorized") is not False:
        errors.append("V2 must not authorize VIA ascension")
    if v2.get("biological_claim_authorized") is not False:
        errors.append("V2 must not authorize a biological claim")
    if v2.get("scope") != "synthetic SCM control only":
        errors.append("V2 scope must remain synthetic SCM control only")

    checks = v2.get("checks")
    if v2.get("verdict") == "CAUSAL_DEBT_V2_CONTROL_QUALIFIED":
        if v2.get("control_qualification") is not True:
            errors.append("qualified V2 verdict missing control_qualification=true")
        if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
            errors.append("qualified V2 verdict contains a failed preregistered check")
    else:
        if v2.get("control_qualification") is not False:
            errors.append("negative V2 verdict must set control_qualification=false")

    if program is not None:
        if program.get("verdict") != "DEFERRED_CAUSAL_CREDIT_SYNTHETIC_CONTROL_ESTABLISHED_REAL_MODEL_UNTESTED":
            errors.append("program boundary verdict changed or missing")
        required_false = (
            "mechanism_attribution_confirmatory",
            "stress_sweep_confirmatory",
            "real_model_tested",
            "biological_claim_authorized",
            "via_ascension_authorized",
            "physical_compute_claim_authorized",
        )
        for key in required_false:
            if program.get(key) is not False:
                errors.append(f"program boundary requires {key}=false")
        if program.get("core_implemented") is not True or program.get("v1_negative_preserved") is not True or program.get("v2_control_qualified") is not True:
            errors.append("program summary lost a binding core/V1/V2 state")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).is_file():
            errors.append(f"missing causal-debt file: {rel}")
    if errors:
        return errors
    try:
        v1 = _read(root / "artifacts/causal-debt-v1/verdict.json")
        v2 = _read(root / "artifacts/causal-debt-v2/verdict.json")
        program = _read(root / "artifacts/causal-debt-program/verdict.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"invalid causal-debt verdict: {exc}"]
    errors.extend(audit_documents(v1, v2, program))
    for name in ("causal-debt-v1", "causal-debt-v2", "causal-debt-v2-ablation", "causal-debt-v2-stress", "causal-debt-program"):
        directory = root / "artifacts" / name
        if directory.exists():
            errors.extend(_verify_sumfile(directory))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"CAUSAL-DEBT-GATE-FAIL: {error}")
        return 1
    print("CAUSAL-DEBT-GATE: PASS (V1 negative preserved; V2 synthetic control bounded; no ascension)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
