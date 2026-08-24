from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from cwc.governance.evidence_packaging_authority import (
    EvidencePackagingAuthorityError,
    build_evidence_packaging_authority,
)
from cwc.governance.product_evidence import (
    ProductEvidenceRecord,
    ProductEvidenceStage,
    require_stage,
)
from cwc.governance.product_qualification_pointer import (
    CANONICAL_POINTER_PATH,
    ProductQualificationPointerError,
    verify_product_qualification_pointer,
)

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "artifacts/dgc-product-v1/evidence_status.json"

FIELDS = (
    "claim_frozen",
    "metrics_frozen",
    "baselines_frozen",
    "harness_frozen",
    "statistical_plan_frozen",
    "synthetic_mechanism_supported",
    "external_real_workload_supported",
    "quality_noninferiority_supported",
    "catastrophic_regret_noninferiority_supported",
    "coverage_equivalence_supported",
    "physical_cost_accounting_verified",
    "net_cost_superiority_supported",
    "generalization_supported",
    "fault_tolerance_supported",
    "independent_replication_supported",
    "evidence_bundle_complete",
    "production_provider_trace_supported",
    "shadow_mode_qualified",
    "bounded_canary_qualified",
)


def load_record(path: Path = STATUS) -> ProductEvidenceRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [name for name in FIELDS if name not in data]
    if missing:
        raise ValueError(f"evidence status missing required fields: {missing}")
    non_bool = [name for name in FIELDS if not isinstance(data[name], bool)]
    if non_bool:
        raise ValueError(f"evidence status fields must be boolean: {non_bool}")
    return ProductEvidenceRecord(**{name: data[name] for name in FIELDS})


def _git_identity(root: Path) -> tuple[str, str]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip().lower()

    return run("rev-parse", "HEAD"), run("rev-parse", "HEAD^{tree}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-stage",
        choices=[x.name for x in ProductEvidenceStage],
        default=None,
    )
    parser.add_argument("--qualification-pointer", default=CANONICAL_POINTER_PATH)
    args = parser.parse_args()

    try:
        record = load_record()
    except Exception as exc:
        print(f"DGC-PRODUCT-GATE: FAIL evidence-status-invalid: {exc}")
        return 1

    print(f"DGC-PRODUCT-MIRROR-STAGE: {record.stage.name}")
    print(f"DGC-PRODUCT-MIRROR-QUALIFIED: {str(record.product_qualified).lower()}")
    print("DGC-PRODUCT-MIRROR-IS-AUTHORITY: false")
    print(f"DGC-PRODUCTION-CONTROL-AUTHORIZED: {str(record.production_control_authorized).lower()}")
    missing = record.missing_for_product_qualified()
    if missing:
        print("DGC-PRODUCT-MIRROR-MISSING: " + ",".join(missing))

    if args.require_stage == ProductEvidenceStage.PRODUCT_QUALIFIED.name:
        try:
            packaging_commit, packaging_tree = _git_identity(ROOT)
            verified = verify_product_qualification_pointer(
                repository_root=ROOT,
                pointer_path=Path(args.qualification_pointer),
            )
            packaging = build_evidence_packaging_authority(
                repository_root=ROOT,
                qualification=verified,
                packaging_commit=packaging_commit,
            )
        except (
            ProductQualificationPointerError,
            EvidencePackagingAuthorityError,
            subprocess.CalledProcessError,
            OSError,
        ) as exc:
            print(f"DGC-PRODUCT-GATE: FAIL terminal-qualification-or-packaging-replay: {exc}")
            return 1
        print("DGC-PRODUCT-AUTHORITY: GLOBAL_V5_POINTER_V3_PLUS_APPEND_ONLY_PACKAGING_V2")
        print("DGC-PRODUCT-QUALIFIED: true")
        print(f"DGC-PRODUCT-QUALIFICATION-POINTER: {verified.pointer_digest}")
        print(f"DGC-PRODUCT-GLOBAL-V5: {verified.global_v5_authority_digest}")
        print(f"DGC-PRODUCT-LEDGER-TIP: {verified.ledger_tip_receipt_digest}")
        print(f"DGC-QUALIFIED-EXECUTION-COMMIT: {verified.repo_commit}")
        print(f"DGC-QUALIFIED-EXECUTION-TREE: {verified.repo_tree}")
        print(f"DGC-EVIDENCE-PACKAGING-COMMIT: {packaging_commit}")
        print(f"DGC-EVIDENCE-PACKAGING-TREE: {packaging_tree}")
        print(f"DGC-EVIDENCE-PACKAGING-AUTHORITY: {packaging.authority_digest}")
        print("DGC-PRODUCT-GATE: PASS portable terminal qualification and append-only packaging replayed")
        return 0

    if args.require_stage is not None:
        required = ProductEvidenceStage[args.require_stage]
        try:
            require_stage(record, required)
        except RuntimeError as exc:
            print(f"DGC-PRODUCT-GATE: FAIL {exc}")
            return 1
    print("DGC-PRODUCT-GATE: PASS nonterminal evidence semantics validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
