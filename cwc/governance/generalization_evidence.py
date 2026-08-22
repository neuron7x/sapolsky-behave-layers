from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GeneralizationAxis(str, Enum):
    UNSEEN_TASKS = "G1_UNSEEN_TASKS"
    UNSEEN_DOMAIN = "G2_UNSEEN_DOMAIN"
    UNSEEN_MODEL_PROVIDER = "G3_UNSEEN_MODEL_PROVIDER"
    CHANGED_ECONOMICS = "G4_CHANGED_ECONOMICS"
    PERTURBATION_SHIFT = "G5_PERTURBATION_SHIFT"


REQUIRED_AXES = tuple(GeneralizationAxis)


@dataclass(frozen=True, slots=True)
class GeneralizationAxisResult:
    axis: GeneralizationAxis
    frozen_policy_digest: str
    evaluation_manifest_digest: str
    policy_retuned: bool
    quality_noninferiority_supported: bool
    catastrophic_regret_noninferiority_supported: bool
    coverage_supported: bool
    cost_effect_direction_positive: bool

    def __post_init__(self) -> None:
        if not self.frozen_policy_digest.strip() or not self.evaluation_manifest_digest.strip():
            raise ValueError("policy and evaluation manifest digests required")

    @property
    def supported(self) -> bool:
        return all((
            not self.policy_retuned,
            self.quality_noninferiority_supported,
            self.catastrophic_regret_noninferiority_supported,
            self.coverage_supported,
            self.cost_effect_direction_positive,
        ))


@dataclass(frozen=True, slots=True)
class GeneralizationCertificate:
    frozen_policy_digest: str
    results: tuple[GeneralizationAxisResult, ...]
    supported: bool


def certify_generalization(results: tuple[GeneralizationAxisResult, ...]) -> GeneralizationCertificate:
    axes = [row.axis for row in results]
    if len(axes) != len(set(axes)) or set(axes) != set(REQUIRED_AXES):
        raise ValueError("generalization evidence must contain exactly G1-G5")
    policies = {row.frozen_policy_digest for row in results}
    if len(policies) != 1:
        raise ValueError("all generalization axes must use the exact same frozen DGC policy")
    supported = all(row.supported for row in results)
    return GeneralizationCertificate(
        frozen_policy_digest=next(iter(policies)),
        results=tuple(sorted(results, key=lambda row: row.axis.value)),
        supported=supported,
    )
