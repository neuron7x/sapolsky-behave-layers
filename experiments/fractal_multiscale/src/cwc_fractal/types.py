from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Scale(StrEnum):
    MICRO = "micro"
    MESO = "meso"
    MACRO = "macro"


SCALE_ORDER: tuple[Scale, ...] = (Scale.MICRO, Scale.MESO, Scale.MACRO)


class FractalValidationError(ValueError):
    """Raised when a multiscale comparison would be semantically invalid."""


@dataclass(frozen=True)
class ScaleObservation:
    timestamp: int
    scale: Scale
    features: dict[str, float]
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.features:
            raise FractalValidationError("features cannot be empty")
        if any(not isinstance(value, int | float) for value in self.features.values()):
            raise FractalValidationError("all feature values must be numeric")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "scale": self.scale.value,
            "features": dict(sorted(self.features.items())),
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class FeatureMapping:
    source_scale: Scale
    target_scale: Scale
    pairs: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if self.source_scale == self.target_scale:
            raise FractalValidationError("feature mapping must connect different scales")
        if not self.pairs:
            raise FractalValidationError("feature mapping pairs cannot be empty")

    def mapped_values(
        self,
        source: ScaleObservation,
        target: ScaleObservation,
    ) -> tuple[list[float], list[float]]:
        if source.scale != self.source_scale or target.scale != self.target_scale:
            raise FractalValidationError("observation scales do not match feature mapping")
        left: list[float] = []
        right: list[float] = []
        missing: list[str] = []
        for source_name, target_name in self.pairs:
            if source_name not in source.features:
                missing.append(f"{source.scale.value}.{source_name}")
            if target_name not in target.features:
                missing.append(f"{target.scale.value}.{target_name}")
            if missing:
                continue
            left.append(float(source.features[source_name]))
            right.append(float(target.features[target_name]))
        if missing:
            raise FractalValidationError(f"feature mapping missing fields: {missing}")
        return left, right


@dataclass(frozen=True)
class CausalWindow:
    end_timestamp: int
    observations: tuple[ScaleObservation, ...]

    def __post_init__(self) -> None:
        future = [
            item.timestamp
            for item in self.observations
            if item.timestamp > self.end_timestamp
        ]
        if future:
            raise FractalValidationError(f"causal window contains future observations: {future}")

    def by_scale(self, scale: Scale) -> tuple[ScaleObservation, ...]:
        return tuple(item for item in self.observations if item.scale == scale)

    def latest(self, scale: Scale) -> ScaleObservation:
        values = self.by_scale(scale)
        if not values:
            raise FractalValidationError(f"missing observation for scale={scale.value}")
        return max(values, key=lambda item: item.timestamp)
