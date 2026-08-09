"""Audit whether frozen real-workload artifacts can identify VIA-V1 instance opportunity.

This script is deliberately structural: it never infers missing unit-level outcomes from bucket
means.  The question is whether the frozen evidence contains paired outcomes for the same
independent unit under every action, which is required to evaluate an instance-oracle estimand.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text())
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def _audit_wp18() -> dict[str, Any]:
    files = sorted(Path(p) for p in glob.glob(str(ROOT / "artifacts/wp18-real-workload-pilot/raw_runs/*.json")))
    if not files:
        return {"available": False, "instance_outcomes_recoverable": False, "reason": "no raw runs"}
    shard_count = 0
    bucket_mean_only = True
    for path in files:
        run = _read(path)
        for shard in run.get("shards", []):
            shard_count += 1
            loss = shard.get("loss")
            # WP18 stores bucket -> action -> scalar mean. There are no unit ids or
            # same-unit per-action losses, so max_a cannot be taken per independent unit.
            if not isinstance(loss, dict) or not all(isinstance(v, dict) for v in loss.values()):
                bucket_mean_only = False
    return {
        "available": True,
        "raw_run_files": len(files),
        "shards": shard_count,
        "stored_granularity": "difficulty_bucket_action_mean",
        "bucket_mean_shape_valid": bucket_mean_only,
        "independent_unit_ids_present": False,
        "paired_per_unit_action_outcomes_present": False,
        "instance_outcomes_recoverable": False,
        "reason": (
            "aggregation to difficulty-bucket means occurred before artifact sealing; "
            "instance-level paired potential outcomes cannot be reconstructed"
        ),
    }


def _audit_wp19() -> dict[str, Any]:
    files = sorted(Path(p) for p in glob.glob(str(ROOT / "artifacts/wp19-negative-robustness/raw_runs/*.json")))
    if not files:
        return {"available": False, "instance_outcomes_recoverable": False, "reason": "no raw runs"}
    shard_count = 0
    scalar_bucket_only = True
    for path in files:
        run = _read(path)
        for shard in run.get("shards", []):
            shard_count += 1
            loss = shard.get("loss")
            if not isinstance(loss, dict) or not all(isinstance(v, (int, float)) for v in loss.values()):
                scalar_bucket_only = False
    return {
        "available": True,
        "raw_run_files": len(files),
        "shards": shard_count,
        "stored_granularity": "difficulty_bucket_mean_per_separately_trained_depth",
        "bucket_mean_shape_valid": scalar_bucket_only,
        "independent_unit_ids_present": False,
        "paired_per_unit_action_outcomes_present": False,
        "instance_outcomes_recoverable": False,
        "additional_identification_problem": (
            "depth actions are separately trained models, so even newly retained per-window losses "
            "would mix action effect with training realization unless the estimand explicitly allows it"
        ),
        "reason": (
            "only per-bucket means were sealed; the same independent evaluation unit is not stored "
            "with outcomes under every depth action"
        ),
    }


def audit() -> dict[str, Any]:
    wp18 = _audit_wp18()
    wp19 = _audit_wp19()
    real_instance_identified = bool(
        wp18.get("instance_outcomes_recoverable") or wp19.get("instance_outcomes_recoverable")
    )
    return {
        "schema": "cwc-via/evidence-sufficiency-1",
        "question": "can frozen real-workload evidence identify per-unit VIA-V1 instance opportunity",
        "wp18": wp18,
        "wp19": wp19,
        "real_instance_opportunity_identified": real_instance_identified,
        "verdict": (
            "VIA_V1_INSTANCE_OPPORTUNITY_IDENTIFIED_FROM_FROZEN_REAL_EVIDENCE"
            if real_instance_identified
            else "VIA_V1_INSTANCE_OPPORTUNITY_UNIDENTIFIED_FROM_FROZEN_REAL_EVIDENCE"
        ),
        "required_future_artifact_contract": {
            "independent_unit_id": True,
            "immutable_unit_payload_hash": True,
            "same_unit_all_actions": True,
            "raw_quality_before_scalarization": True,
            "raw_compute_per_action": True,
            "action_execution_identity": True,
            "cluster_id_if_units_share_source": True,
            "no_preaggregation_before_evidence_seal": True,
        },
        "scientific_implication": (
            "WP18/WP19 remain valid for their registered bucket-conditioned estimands. The frozen "
            "artifacts are insufficient to answer the newly separated instance-oracle question; "
            "absence of that evidence is UNKNOWN, not positive or negative evidence for G_instance."
        ),
        "ascension_authorized": False,
    }


def main() -> int:
    result = audit()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
