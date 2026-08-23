from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum


class BaselineKind(str, Enum):
    FIXED_COMPUTE = "B0_FIXED_COMPUTE"
    UNCERTAINTY_ROUTER = "B1_UNCERTAINTY_ROUTER"
    LEARNED_COST_QUALITY_ROUTER = "B2_LEARNED_COST_QUALITY_ROUTER"
    SEQUENTIAL_VERIFICATION = "B3_SEQUENTIAL_VERIFICATION"


REQUIRED_BASELINES = tuple(BaselineKind)


def _req(name: str, value: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} required")
    return value


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class BaselinePolicySpec:
    kind: BaselineKind
    implementation_version: str
    feature_schema_digest: str
    policy_config_digest: str
    training_algorithm_digest: str | None = None
    calibration_task_digest: str | None = None
    fitted_model_digest: str | None = None

    def __post_init__(self) -> None:
        for name in ("implementation_version", "feature_schema_digest", "policy_config_digest"):
            object.__setattr__(self, name, _req(name, getattr(self, name)))
        if self.kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER:
            if not self.training_algorithm_digest or not self.training_algorithm_digest.strip():
                raise ValueError("learned router requires frozen training_algorithm_digest")
        elif any((self.training_algorithm_digest, self.calibration_task_digest, self.fitted_model_digest)):
            raise ValueError("only learned baseline may carry training/calibration/model digests")

    @property
    def executable_frozen(self) -> bool:
        if self.kind is not BaselineKind.LEARNED_COST_QUALITY_ROUTER:
            return True
        return bool(self.training_algorithm_digest and self.calibration_task_digest and self.fitted_model_digest)

    @property
    def digest(self) -> str:
        return _digest({
            "kind": self.kind.value,
            "implementation_version": self.implementation_version,
            "feature_schema_digest": self.feature_schema_digest,
            "policy_config_digest": self.policy_config_digest,
            "training_algorithm_digest": self.training_algorithm_digest,
            "calibration_task_digest": self.calibration_task_digest,
            "fitted_model_digest": self.fitted_model_digest,
        })


@dataclass(frozen=True, slots=True)
class BaselinePanelSeal:
    specs: tuple[BaselinePolicySpec, ...]

    def __post_init__(self) -> None:
        kinds = [spec.kind for spec in self.specs]
        if len(kinds) != len(set(kinds)):
            raise ValueError("baseline kinds must be unique")
        if set(kinds) != set(REQUIRED_BASELINES):
            missing = sorted(kind.value for kind in set(REQUIRED_BASELINES) - set(kinds))
            extra = sorted(kind.value for kind in set(kinds) - set(REQUIRED_BASELINES))
            raise ValueError(f"baseline panel must contain exactly B0-B3; missing={missing}; extra={extra}")

    @property
    def executable_frozen(self) -> bool:
        return all(spec.executable_frozen for spec in self.specs)

    @property
    def digest(self) -> str:
        return _digest([(spec.kind.value, spec.digest) for spec in sorted(self.specs, key=lambda s: s.kind.value)])


def freeze_learned_baseline_fit(
    spec: BaselinePolicySpec, *, calibration_task_digest: str, fitted_model_digest: str
) -> BaselinePolicySpec:
    if spec.kind is not BaselineKind.LEARNED_COST_QUALITY_ROUTER:
        raise ValueError("only learned baseline can be fitted")
    return BaselinePolicySpec(
        kind=spec.kind,
        implementation_version=spec.implementation_version,
        feature_schema_digest=spec.feature_schema_digest,
        policy_config_digest=spec.policy_config_digest,
        training_algorithm_digest=spec.training_algorithm_digest,
        calibration_task_digest=_req("calibration_task_digest", calibration_task_digest),
        fitted_model_digest=_req("fitted_model_digest", fitted_model_digest),
    )


def bind_verified_learned_router_fit(
    spec: BaselinePolicySpec,
    *,
    feature_schema_digest: str,
    training_algorithm_digest: str,
    calibration_task_digest: str,
    fitted_model_digest: str,
) -> BaselinePolicySpec:
    """Bind an executable B2 fit only when frozen pre-fit identities match.

    The function deliberately receives plain digests rather than importing the learned
    router implementation. This keeps the baseline-panel contract independent while
    preventing a fitted model from being attached to a different feature schema or
    training algorithm after calibration outcomes are known.
    """
    if spec.kind is not BaselineKind.LEARNED_COST_QUALITY_ROUTER:
        raise ValueError("only B2 learned baseline may bind a fitted router")
    observed_schema = _req("feature_schema_digest", feature_schema_digest)
    observed_algorithm = _req("training_algorithm_digest", training_algorithm_digest)
    if spec.feature_schema_digest != observed_schema:
        raise ValueError("B2 feature schema digest mismatch")
    if spec.training_algorithm_digest != observed_algorithm:
        raise ValueError("B2 training algorithm digest mismatch")
    return freeze_learned_baseline_fit(
        spec,
        calibration_task_digest=calibration_task_digest,
        fitted_model_digest=fitted_model_digest,
    )
