from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterable

from cwc.governance.learned_baseline import (
    CalibrationExample,
    LearnedRouterConfig,
    fit_learned_router,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _sha(name: str, value: str) -> str:
    value = str(value).strip()
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class B2FitReceipt:
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
    confirmatory_execution_authorized: bool = False


def fit_b2_with_receipt(
    *,
    config: LearnedRouterConfig,
    examples: Iterable[CalibrationExample],
    forbidden_task_ids: Iterable[str],
    expected_feature_schema_digest: str,
    expected_training_algorithm_digest: str,
) -> B2FitReceipt:
    schema = _sha("expected_feature_schema_digest", expected_feature_schema_digest)
    algorithm = _sha("expected_training_algorithm_digest", expected_training_algorithm_digest)
    if config.feature_schema_digest != schema:
        raise ValueError("B2 feature schema digest mismatch")
    if config.training_algorithm_digest != algorithm:
        raise ValueError("B2 training algorithm digest mismatch")

    rows = tuple(examples)
    forbidden = tuple(sorted({str(task).strip() for task in forbidden_task_ids if str(task).strip()}))
    input_rows = tuple(
        sorted(
            (
                example.task_id,
                example.action_id,
                example.features,
                example.quality,
                example.cost_usd,
                example.catastrophic_regret,
            )
            for example in rows
        )
    )
    calibration_input_digest = _digest(input_rows)
    forbidden_digest = _digest(forbidden)
    fitted = fit_learned_router(config, list(rows), forbidden_task_ids=forbidden)
    models = tuple(
        {
            "action_id": model.action_id,
            "intercept": model.intercept,
            "coefficients": model.coefficients,
        }
        for model in fitted.models
    )
    payload = {
        "schema": "DGC_B2_FIT_RECEIPT_V1",
        "feature_schema_digest": schema,
        "training_algorithm_digest": algorithm,
        "calibration_task_digest": fitted.calibration_task_digest,
        "fitted_model_digest": fitted.model_digest,
        "calibration_task_count": fitted.calibration_task_count,
        "calibration_input_digest": calibration_input_digest,
        "forbidden_task_manifest_digest": forbidden_digest,
        "model_rows": models,
        "confirmatory_execution_authorized": False,
    }
    return B2FitReceipt(
        schema=payload["schema"],
        feature_schema_digest=schema,
        training_algorithm_digest=algorithm,
        calibration_task_digest=fitted.calibration_task_digest,
        fitted_model_digest=fitted.model_digest,
        calibration_task_count=fitted.calibration_task_count,
        calibration_input_digest=calibration_input_digest,
        forbidden_task_manifest_digest=forbidden_digest,
        model_rows=models,
        receipt_digest=_digest(payload),
        confirmatory_execution_authorized=False,
    )
