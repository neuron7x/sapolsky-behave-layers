"""Validate DGC financial evidence authority without over-promoting synthetic results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV_ARTIFACT = ROOT / "artifacts/dgc-02-finance-dev"
CONFIRM_ARTIFACT = ROOT / "artifacts/dgc-02-finance-confirmatory"
CONFIRM_PREREG_COMMIT = "8e6db42fcb1a12dcf7e3fca54f695e6b05a06e70"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_manifest(artifact: Path, errors: list[str], label: str) -> None:
    manifest_path = artifact / "manifest.json"
    if not manifest_path.is_file():
        errors.append(f"missing {label} manifest")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        path = artifact / name
        if not path.is_file() or _sha256(path) != expected:
            errors.append(f"{label} artifact hash mismatch: {name}")
    if not (artifact / "SHA256SUMS").is_file():
        errors.append(f"missing {label} SHA256SUMS")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    dev = root / "artifacts/dgc-02-finance-dev"
    confirm = root / "artifacts/dgc-02-finance-confirmatory"
    required = (
        dev / "verdict.json", dev / "manifest.json",
        confirm / "verdict.json", confirm / "manifest.json",
        root / "experiments/dgc_02_finance/PREREGISTRATION.md",
        root / "experiments/dgc_02_finance/PREREGISTRATION_CONFIRMATORY.md",
        root / "docs/DGC_FINANCIAL_VERIFICATION_CONTRACT.md",
        root / "docs/DGC_SYNTHETIC_FINANCIAL_THEOREM.md",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing financial authority artifact: {path.relative_to(root)}")
    if errors:
        return errors

    dev_v = json.loads((dev / "verdict.json").read_text(encoding="utf-8"))
    if dev_v.get("status") != "DEVELOPMENT_ONLY_NON_PROMOTING": errors.append("financial development authority changed")
    if dev_v.get("claim_promotion") != "PROHIBITED": errors.append("financial development evidence illegally permits claim promotion")
    if dev_v.get("commercial_claim_allowed") is not False: errors.append("financial development evidence illegally permits commercial claim")
    if float(dev_v.get("threshold", -1)) != 0.30: errors.append("30% development verification threshold drifted")
    primary = dev_v.get("zero_unmetered_overhead_ceiling", {})
    reported_met = dev_v.get("development_threshold_status") == "DEVELOPMENT_THRESHOLD_MET"
    recomputed_met = float(primary.get("savings_lcb", float("-inf"))) >= 0.30 and float(primary.get("quality_lcb", float("-inf"))) >= 0.0
    if reported_met != recomputed_met: errors.append("financial development threshold status inconsistent with evidence")
    if float(primary.get("mean_governance_overhead", -1)) != 0.0: errors.append("development primary result is not marked zero-unmetered-overhead ceiling")
    sweep = dev_v.get("overhead_sensitivity", [])
    if not sweep or not any(not bool(row.get("threshold_met")) for row in sweep): errors.append("development overhead sensitivity lacks a failing regime")

    conf_v = json.loads((confirm / "verdict.json").read_text(encoding="utf-8"))
    if conf_v.get("authority") != "PROSPECTIVE_SYNTHETIC_CONFIRMATION": errors.append("confirmatory financial authority changed")
    if conf_v.get("preregistration_commit") != CONFIRM_PREREG_COMMIT: errors.append("confirmatory result is not bound to frozen preregistration commit")
    if conf_v.get("status") != "SYNTHETIC_CONFIRMATORY_THRESHOLD_MET": errors.append("prospective synthetic 30% threshold was not met")
    if int(conf_v.get("tasks", -1)) != 100_000 or float(conf_v.get("coverage", -1)) != 1.0: errors.append("confirmatory task coverage changed")
    if int(conf_v.get("seed_offset", -1)) != 200_000_000: errors.append("confirmatory seed cohort changed")
    if float(conf_v.get("synthetic_governance_overhead", -1)) != 0.0125: errors.append("confirmatory overhead stress changed")
    if float(conf_v.get("threshold", -1)) != 0.30: errors.append("30% confirmatory threshold drifted")
    f = conf_v.get("financial_gate", {})
    if float(f.get("savings_lcb", float("-inf"))) < 0.30: errors.append("confirmatory savings lower bound below target")
    if float(f.get("quality_lcb", float("-inf"))) < 0.0: errors.append("confirmatory quality non-inferiority failed")
    if conf_v.get("client_verified") is not False: errors.append("synthetic evidence illegally marks client_verified")
    if conf_v.get("commercial_claim_allowed") is not False: errors.append("synthetic evidence illegally permits commercial claim")
    if conf_v.get("general_superiority_claim_allowed") is not False: errors.append("synthetic evidence illegally permits general-superiority claim")

    _validate_manifest(dev, errors, "development")
    _validate_manifest(confirm, errors, "confirmatory")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors: print(f"DGC-FINANCE-GATE: FAIL {error}")
        return 1
    dev = json.loads((DEV_ARTIFACT / "verdict.json").read_text(encoding="utf-8"))
    conf = json.loads((CONFIRM_ARTIFACT / "verdict.json").read_text(encoding="utf-8"))
    dp = dev["zero_unmetered_overhead_ceiling"]
    cp = conf["financial_gate"]
    print("DGC-FINANCE-GATE: PASS " f"(dev LCB={dp['savings_lcb']:.6f}; confirm savings={cp['net_inference_savings']:.6f}; " f"confirm LCB={cp['savings_lcb']:.6f}; quality_lcb={cp['quality_lcb']:.6f}; " "client_verified=false; commercial_claim_allowed=false)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
