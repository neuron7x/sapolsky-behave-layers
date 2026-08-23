from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class LearnedRouterConfig:
    feature_names: tuple[str, ...]
    action_ids: tuple[str, ...]
    ridge_lambda: float
    quality_weight: float
    cost_weight: float
    regret_weight: float

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
        weights = []
        for name in ("quality_weight", "cost_weight", "regret_weight"):
            value = _finite(name, getattr(self, name))
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
            object.__setattr__(self, name, value)
            weights.append(value)
        if not any(value > 0 for value in weights):
            raise ValueError("at least one utility weight must be > 0")

    @property
    def feature_schema_digest(self) -> str:
        return _digest({"feature_names": self.feature_names})

    @property
    def training_algorithm_digest(self) -> str:
        return _digest(
            {
                "algorithm": "PER_ACTION_RIDGE_UTILITY_V1",
                "feature_schema_digest": self.feature_schema_digest,
                "action_ids": self.action_ids,
                "ridge_lambda": self.ridge_lambda,
                "quality_weight": self.quality_weight,
                "cost_weight": self.cost_weight,
                "regret_weight": self.regret_weight,
                "intercept_regularized": False,
                "tie_break": "LEXICOGRAPHIC_ACTION_ID",
            }
        )


@dataclass(frozen=True, slots=True)
class CalibrationExample:
    task_id: str
    action_id: str
    features: tuple[float, ...]
    quality: float
    cost_usd: float
    catastrophic_regret: float

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.action_id.strip():
            raise ValueError("task_id and action_id are required")
        features = tuple(_finite("feature", value) for value in self.features)
        object.__setattr__(self, "features", features)
        quality = _finite("quality", self.quality)
        regret = _finite("catastrophic_regret", self.catastrophic_regret)
        cost = _finite("cost_usd", self.cost_usd)
        if not 0 <= quality <= 1:
            raise ValueError("quality must be in [0,1]")
        if not 0 <= regret <= 1:
            raise ValueError("catastrophic_regret must be in [0,1]")
        if cost < 0:
            raise ValueError("cost_usd must be >= 0")
        object.__setattr__(self, "quality", quality)
        object.__setattr__(self, "catastrophic_regret", regret)
        object.__setattr__(self, "cost_usd", cost)


@dataclass(frozen=True, slots=True)
class ActionLinearModel:
    action_id: str
    intercept: float
    coefficients: tuple[float, ...]

    def predict(self, features: tuple[float, ...]) -> float:
        if len(features) != len(self.coefficients):
            raise ValueError("feature length mismatch")
        return self.intercept + math.fsum(c * float(x) for c, x in zip(self.coefficients, features, strict=True))


@dataclass(frozen=True, slots=True)
class FittedLearnedRouter:
    config: LearnedRouterConfig
    calibration_task_digest: str
    model_digest: str
    models: tuple[ActionLinearModel, ...]
    calibration_task_count: int

    def __post_init__(self) -> None:
        if len(self.calibration_task_digest.strip()) < 16 or len(self.model_digest.strip()) < 16:
            raise ValueError("calibration/model digests must be non-trivial")
        if self.calibration_task_count <= 0:
            raise ValueError("calibration_task_count must be > 0")
        actions = tuple(model.action_id for model in self.models)
        if actions != self.config.action_ids:
            raise ValueError("fitted models must match frozen action_ids exactly")

    def predict_scores(self, features: tuple[float, ...]) -> tuple[tuple[str, float], ...]:
        if len(features) != len(self.config.feature_names):
            raise ValueError("feature length mismatch")
        xs = tuple(_finite("feature", value) for value in features)
        return tuple((model.action_id, model.predict(xs)) for model in self.models)

    def predict(self, features: tuple[float, ...]) -> str:
        scores = self.predict_scores(features)
        best = max(score for _, score in scores)
        return min(action for action, score in scores if abs(score - best) <= 1e-12)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    augmented = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) <= 1e-14:
            raise ValueError("singular calibration design even after ridge regularization")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        augmented[col] = [value / scale for value in augmented[col]]
        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            if abs(factor) <= 1e-18:
                continue
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[col], strict=True)]
    return [augmented[i][-1] for i in range(n)]


def _fit_ridge(rows: list[tuple[tuple[float, ...], float]], ridge_lambda: float) -> tuple[float, tuple[float, ...]]:
    width = len(rows[0][0])
    dim = width + 1
    xtx = [[0.0 for _ in range(dim)] for _ in range(dim)]
    xty = [0.0 for _ in range(dim)]
    for features, target in rows:
        design = (1.0,) + features
        for i in range(dim):
            xty[i] += design[i] * target
            for j in range(dim):
                xtx[i][j] += design[i] * design[j]
    for i in range(1, dim):
        xtx[i][i] += ridge_lambda
    beta = _solve_linear_system(xtx, xty)
    return beta[0], tuple(beta[1:])


def fit_learned_router(
    config: LearnedRouterConfig,
    examples: list[CalibrationExample],
    *,
    forbidden_task_ids: tuple[str, ...] = (),
) -> FittedLearnedRouter:
    if not examples:
        raise ValueError("non-empty calibration population required")
    forbidden = {str(task).strip() for task in forbidden_task_ids if str(task).strip()}
    tasks = sorted({example.task_id for example in examples})
    if forbidden.intersection(tasks):
        raise ValueError("confirmatory/forbidden task leakage into B2 calibration")
    if any(len(example.features) != len(config.feature_names) for example in examples):
        raise ValueError("example feature length does not match frozen schema")
    if any(example.action_id not in config.action_ids for example in examples):
        raise ValueError("example action outside frozen action set")

    pairs = [(example.task_id, example.action_id) for example in examples]
    if len(pairs) != len(set(pairs)):
        raise ValueError("each calibration task/action pair must appear exactly once")
    expected_pairs = {(task, action) for task in tasks for action in config.action_ids}
    if set(pairs) != expected_pairs:
        missing = sorted(expected_pairs - set(pairs))
        raise ValueError(f"complete counterfactual calibration table required; missing={missing[:5]}")

    models = []
    for action in config.action_ids:
        action_rows = []
        for example in sorted((x for x in examples if x.action_id == action), key=lambda x: x.task_id):
            utility = (
                config.quality_weight * example.quality
                - config.cost_weight * example.cost_usd
                - config.regret_weight * example.catastrophic_regret
            )
            action_rows.append((example.features, utility))
        intercept, coefficients = _fit_ridge(action_rows, config.ridge_lambda)
        models.append(ActionLinearModel(action, intercept, coefficients))

    task_digest = _digest(tasks)
    model_payload = {
        "config_training_algorithm_digest": config.training_algorithm_digest,
        "calibration_task_digest": task_digest,
        "models": [
            {"action_id": model.action_id, "intercept": model.intercept, "coefficients": model.coefficients}
            for model in models
        ],
    }
    return FittedLearnedRouter(
        config=config,
        calibration_task_digest=task_digest,
        model_digest=_digest(model_payload),
        models=tuple(models),
        calibration_task_count=len(tasks),
    )
