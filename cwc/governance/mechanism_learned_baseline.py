from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from cwc.governance.learned_baseline import ActionLinearModel, _fit_ridge


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _finite(name: str, value: float) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


@dataclass(frozen=True, slots=True)
class MechanismLearnedRouterConfig:
    feature_names: tuple[str, ...]
    action_ids: tuple[str, ...]
    ridge_lambda: float
    quality_weight: float
    cost_weight: float

    def __post_init__(self) -> None:
        features = tuple(str(x).strip() for x in self.feature_names)
        actions = tuple(sorted(str(x).strip() for x in self.action_ids))
        if not features or any(not x for x in features) or len(set(features)) != len(features):
            raise ValueError("feature_names must be non-empty and unique")
        if not actions or any(not x for x in actions) or len(set(actions)) != len(actions):
            raise ValueError("action_ids must be non-empty and unique")
        object.__setattr__(self, "feature_names", features)
        object.__setattr__(self, "action_ids", actions)
        ridge = _finite("ridge_lambda", self.ridge_lambda)
        if ridge <= 0:
            raise ValueError("ridge_lambda must be > 0")
        object.__setattr__(self, "ridge_lambda", ridge)
        quality = _finite("quality_weight", self.quality_weight)
        cost = _finite("cost_weight", self.cost_weight)
        if quality < 0 or cost < 0 or not (quality > 0 or cost > 0):
            raise ValueError("quality/cost weights must be nonnegative and not both zero")
        object.__setattr__(self, "quality_weight", quality)
        object.__setattr__(self, "cost_weight", cost)

    @property
    def feature_schema_digest(self) -> str:
        return _digest({"feature_names": self.feature_names})

    @property
    def training_algorithm_digest(self) -> str:
        return _digest({
            "algorithm": "PER_ACTION_RIDGE_COST_QUALITY_V1",
            "feature_schema_digest": self.feature_schema_digest,
            "action_ids": self.action_ids,
            "ridge_lambda": self.ridge_lambda,
            "quality_weight": self.quality_weight,
            "cost_weight": self.cost_weight,
            "risk_fields_permitted": False,
            "intercept_regularized": False,
            "tie_break": "LEXICOGRAPHIC_ACTION_ID",
        })


@dataclass(frozen=True, slots=True)
class MechanismCalibrationExample:
    task_id: str
    action_id: str
    features: tuple[float, ...]
    quality: float
    cost_usd: float

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.action_id.strip():
            raise ValueError("task_id and action_id are required")
        features = tuple(_finite("feature", value) for value in self.features)
        quality = _finite("quality", self.quality)
        cost = _finite("cost_usd", self.cost_usd)
        if not 0.0 <= quality <= 1.0:
            raise ValueError("quality must be in [0,1]")
        if cost < 0.0:
            raise ValueError("cost_usd must be >= 0")
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "quality", quality)
        object.__setattr__(self, "cost_usd", cost)


@dataclass(frozen=True, slots=True)
class FittedMechanismLearnedRouter:
    config: MechanismLearnedRouterConfig
    calibration_task_digest: str
    model_digest: str
    models: tuple[ActionLinearModel, ...]
    calibration_task_count: int

    def __post_init__(self) -> None:
        if len(self.calibration_task_digest) != 64 or len(self.model_digest) != 64:
            raise ValueError("calibration/model digests must be SHA-256")
        if self.calibration_task_count <= 0:
            raise ValueError("calibration_task_count must be > 0")
        if tuple(row.action_id for row in self.models) != self.config.action_ids:
            raise ValueError("fitted models must match frozen action_ids exactly")

    def predict_scores(self, features: tuple[float, ...]) -> tuple[tuple[str, float], ...]:
        if len(features) != len(self.config.feature_names):
            raise ValueError("feature length mismatch")
        xs = tuple(_finite("feature", value) for value in features)
        return tuple((row.action_id, row.predict(xs)) for row in self.models)

    def predict(self, features: tuple[float, ...]) -> str:
        scores = self.predict_scores(features)
        best = max(score for _, score in scores)
        return min(action for action, score in scores if abs(score - best) <= 1e-12)


def fit_mechanism_learned_router(
    config: MechanismLearnedRouterConfig,
    examples: list[MechanismCalibrationExample],
    *,
    forbidden_task_ids: tuple[str, ...] = (),
) -> FittedMechanismLearnedRouter:
    if not examples:
        raise ValueError("non-empty calibration population required")
    forbidden = {str(task).strip() for task in forbidden_task_ids if str(task).strip()}
    tasks = sorted({row.task_id for row in examples})
    if forbidden.intersection(tasks):
        raise ValueError("confirmatory/forbidden task leakage into mechanism B2 calibration")
    if any(len(row.features) != len(config.feature_names) for row in examples):
        raise ValueError("example feature length does not match frozen schema")
    if any(row.action_id not in config.action_ids for row in examples):
        raise ValueError("example action outside frozen action set")
    pairs = [(row.task_id, row.action_id) for row in examples]
    if len(pairs) != len(set(pairs)):
        raise ValueError("each calibration task/action pair must appear exactly once")
    expected = {(task, action) for task in tasks for action in config.action_ids}
    if set(pairs) != expected:
        missing = sorted(expected - set(pairs))
        raise ValueError(f"complete counterfactual calibration table required; missing={missing[:5]}")

    models: list[ActionLinearModel] = []
    for action in config.action_ids:
        action_rows = []
        for row in sorted((x for x in examples if x.action_id == action), key=lambda x: x.task_id):
            utility = config.quality_weight * row.quality - config.cost_weight * row.cost_usd
            action_rows.append((row.features, utility))
        intercept, coefficients = _fit_ridge(action_rows, config.ridge_lambda)
        models.append(ActionLinearModel(action, intercept, coefficients))

    task_digest = _digest(tasks)
    model_payload = {
        "training_algorithm_digest": config.training_algorithm_digest,
        "calibration_task_digest": task_digest,
        "models": [
            {"action_id": row.action_id, "intercept": row.intercept, "coefficients": row.coefficients}
            for row in models
        ],
    }
    return FittedMechanismLearnedRouter(
        config=config,
        calibration_task_digest=task_digest,
        model_digest=_digest(model_payload),
        models=tuple(models),
        calibration_task_count=len(tasks),
    )
