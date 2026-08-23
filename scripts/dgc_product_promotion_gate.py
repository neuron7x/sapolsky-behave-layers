from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.governance.product_evidence import (
    ProductEvidenceRecord,
    ProductEvidenceStage,
    require_stage,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-stage",
        choices=[x.name for x in ProductEvidenceStage],
        default=None,
    )
    args = parser.parse_args()

    try:
        record = load_record()
    except Exception as exc:
        print(f"DGC-PRODUCT-GATE: FAIL evidence-status-invalid: {exc}")
        return 1

    print(f"DGC-PRODUCT-STAGE: {record.stage.name}")
    print(f"DGC-PRODUCT-QUALIFIED: {str(record.product_qualified).lower()}")
    print(f"DGC-PRODUCTION-CONTROL-AUTHORIZED: {str(record.production_control_authorized).lower()}")
    missing = record.missing_for_product_qualified()
    if missing:
        print("DGC-PRODUCT-MISSING: " + ",".join(missing))

    if args.require_stage is not None:
        required = ProductEvidenceStage[args.require_stage]
        try:
            require_stage(record, required)
        except RuntimeError as exc:
            print(f"DGC-PRODUCT-GATE: FAIL {exc}")
            return 1
    print("DGC-PRODUCT-GATE: PASS evidence semantics validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
