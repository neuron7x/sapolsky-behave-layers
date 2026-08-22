"""Verify DGC post-synthetic evidence boundaries without converting blockers to PASS."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_ok(directory: Path, errors: list[str]) -> None:
    manifest = directory / "manifest.json"
    if not manifest.is_file():
        errors.append(f"missing manifest: {directory.relative_to(ROOT)}")
        return
    data = json.loads(manifest.read_text())
    for name, expected in data.items():
        path = directory / name
        if not path.is_file() or _sha(path) != expected:
            errors.append(f"hash mismatch: {path.relative_to(ROOT)}")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    d3 = root / "artifacts/dgc-03-local-model"
    d4 = root / "artifacts/dgc-04-software-triage"
    d5 = root / "artifacts/dgc-05-triage-ood"
    live = root / "artifacts/dgc-live-provider-status"
    required = [
        d3 / "verdict.json", d3 / "oracle_feasibility.json", d4 / "verdict.json", d5 / "verdict.json",
        live / "status.json", root / "experiments/dgc_06_llmrouterbench/PREREGISTRATION.md",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing DGC real-world authority: {path.relative_to(root)}")
    if errors:
        return errors

    v3 = json.loads((d3 / "verdict.json").read_text())
    if v3["verdict"]["local_model_threshold"] != "LOCAL_MODEL_30PCT_NOT_SUPPORTED":
        errors.append("DGC-03 negative local-model result was altered")
    o3 = json.loads((d3 / "oracle_feasibility.json").read_text())
    if o3.get("verdict") != "LOCAL_MODEL_30PCT_ORACLE_INFEASIBLE" or o3.get("thirty_percent_feasible") is not False:
        errors.append("DGC-03 oracle feasibility boundary changed")
    for cohort in ("PRIMARY", "REPLICATION"):
        if float(o3["cohorts"][cohort]["max_logical_flop_savings_zero_route_overhead"]) >= 0.30:
            errors.append(f"DGC-03 oracle ceiling unexpectedly clears 30% in {cohort}")

    v4 = json.loads((d4 / "verdict.json").read_text())
    if v4.get("status") != "SOFTWARE_TRIAGE_SUPPORTED_NARROW":
        errors.append("DGC-04 narrow software-triage support missing")
    b2, b1, b0 = v4["summaries"]["B2_DGC"], v4["summaries"]["B1_PATH_ROUTER"], v4["summaries"]["B0_FULL"]
    if not (b2["decision_accuracy"] == 1.0 and b2["false_pass_count"] == 0 and b2["validator_calls"] < b1["validator_calls"] < b0["validator_calls"]):
        errors.append("DGC-04 release-triage gate inconsistent")

    v5 = json.loads((d5 / "verdict.json").read_text())
    if v5.get("known_combination_status") != "TRIAGE_COMBINATORIAL_OOD_SUPPORTED":
        errors.append("DGC-05 combinatorial OOD support missing")
    if v5.get("unknown_domain_status") != "UNKNOWN_DOMAIN_FAIL_CLOSED":
        errors.append("DGC-05 unknown-domain fail-closed gate missing")
    b2, b1, b0 = v5["summaries"]["B2_DGC"], v5["summaries"]["B1_PATH_ROUTER"], v5["summaries"]["B0_FULL"]
    if not (b2["decision_accuracy"] == 1.0 and b2["false_pass_count"] == 0 and b2["validator_calls"] < b1["validator_calls"] < b0["validator_calls"]):
        errors.append("DGC-05 OOD triage gate inconsistent")

    lv = json.loads((live / "status.json").read_text())
    if lv.get("client_verified") is not False or lv.get("commercial_claim_allowed") is not False:
        errors.append("live/client authority illegally promoted")
    if int(lv.get("client_trace_count", -1)) != 0:
        errors.append("unexpected client traces without client evidence bundle")

    for directory in (d3, d4, d5, live):
        _manifest_ok(directory, errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print("DGC-REALWORLD-GATE: FAIL", error)
        return 1
    print("DGC-REALWORLD-GATE: PASS_BOUNDARIES (local30=NOT_SUPPORTED; software=SUPPORTED_NARROW; ood=SUPPORTED_NARROW; live/client=BLOCKED)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
