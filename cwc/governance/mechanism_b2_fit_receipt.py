from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterable

from cwc.governance.mechanism_learned_baseline import (
    MechanismCalibrationExample,
    MechanismLearnedRouterConfig,
    fit_mechanism_learned_router,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "DGC_MECHANISM_B2_FIT_RECEIPT_V1"


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _sha(name: str, value: str) -> str:
    text = str(value).strip()
    if _SHA256_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return text


@dataclass(frozen=True, slots=True)
class MechanismB2FitReceipt:
    schema: str
    feature_schema_digest: str
    training_algorithm_digest: str
    calibration_task_digest: str
    fitted_model_digest: str
    calibration_task_count: int
    calibration_input_digest: str
    forbidden_task_manifest_digest: str
    model_rows: tuple[dict, ...]
    receipt_digest: str
    risk_fields_consumed: bool = False
    mechanism_execution_authorized: bool = False
    product_promotion_authorized: bool = False


def fit_mechanism_b2_with_receipt(
    *,
    config: MechanismLearnedRouterConfig,
    examples: Iterable[MechanismCalibrationExample],
    forbidden_task_ids: Iterable[str],
    expected_feature_schema_digest: str,
    expected_training_algorithm_digest: str,
) -> MechanismB2FitReceipt:
    schema = _sha("expected_feature_schema_digest", expected_feature_schema_digest)
    algorithm = _sha("expected_training_algorithm_digest", expected_training_algorithm_digest)
    if config.feature_schema_digest != schema:
        raise ValueError("mechanism B2 feature schema digest mismatch")
    if config.training_algorithm_digest != algorithm:
        raise ValueError("mechanism B2 training algorithm digest mismatch")
    rows = tuple(examples)
    forbidden = tuple(sorted({str(task).strip() for task in forbidden_task_ids if str(task).strip()}))
    input_rows = tuple(sorted(
        (row.task_id, row.action_id, row.features, row.quality, row.cost_usd)
        for row in rows
    ))
    fitted = fit_mechanism_learned_router(
        config,
        list(rows),
        forbidden_task_ids=forbidden,
    )
    model_rows = tuple(
        {
            "action_id": row.action_id,
            "intercept": row.intercept,
            "coefficients": row.coefficients,
        }
        for row in fitted.models
    )
    payload = {
        "schema": SCHEMA,
        "feature_schema_digest": schema,
        "training_algorithm_digest": algorithm,
        "calibration_task_digest": fitted.calibration_task_digest,
        "fitted_model_digest": fitted.model_digest,
        "calibration_task_count": fitted.calibration_task_count,
        "calibration_input_digest": _digest(input_rows),
        "forbidden_task_manifest_digest": _digest(forbidden),
        "model_rows": model_rows,
        "risk_fields_consumed": False,
        "mechanism_execution_authorized": False,
        "product_promotion_authorized": False,
    }
    return MechanismB2FitReceipt(
        **payload,
        receipt_digest=_digest(payload),
    )
