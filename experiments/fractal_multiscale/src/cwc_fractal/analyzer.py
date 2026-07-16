from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .metrics import FractalMetrics, compute_fractal_metrics, cosine_similarity, zscore
from .types import SCALE_ORDER, CausalWindow, FeatureMapping, FractalValidationError, Scale


@dataclass(frozen=True)
class ScaleReport:
    scale: Scale
    feature_metrics: dict[str, FractalMetrics]
    aggregate_pressure: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "scale": self.scale.value,
            "aggregate_pressure": self.aggregate_pressure,
            "feature_metrics": {
                name: metrics.to_dict() for name, metrics in sorted(self.feature_metrics.items())
            },
        }


@dataclass(frozen=True)
class CrossScaleReport:
    source_scale: Scale
    target_scale: Scale
    coherence: float
    mapped_pairs: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_scale": self.source_scale.value,
            "target_scale": self.target_scale.value,
            "coherence": self.coherence,
            "mapped_pairs": [list(pair) for pair in self.mapped_pairs],
        }


@dataclass(frozen=True)
class BoundaryReport:
    distance: float
    active: bool
    drivers: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "distance": self.distance,
            "active": self.active,
            "drivers": dict(sorted(self.drivers.items())),
        }


@dataclass(frozen=True)
class FractalCognitionReport:
    status: str
    end_timestamp: int
    scale_reports: dict[Scale, ScaleReport]
    cross_scale_reports: tuple[CrossScaleReport, ...]
    boundary: BoundaryReport
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "end_timestamp": self.end_timestamp,
            "scale_reports": {
                scale.value: report.to_dict() for scale, report in self.scale_reports.items()
            },
            "cross_scale_reports": [report.to_dict() for report in self.cross_scale_reports],
            "boundary": self.boundary.to_dict(),
            "warnings": list(self.warnings),
            "interpretation": "multiscale_diagnostic_not_capability_claim",
        }


class FractalMultiscaleAnalyzer:
    def __init__(
        self,
        *,
        mappings: tuple[FeatureMapping, ...],
        boundary_threshold: float = 0.75,
    ) -> None:
        if not mappings:
            raise FractalValidationError("at least one explicit feature mapping is required")
        if not 0.0 < boundary_threshold < 10.0:
            raise FractalValidationError("boundary_threshold must be positive and finite")
        self.mappings = mappings
        self.boundary_threshold = boundary_threshold

    def analyze(self, window: CausalWindow) -> FractalCognitionReport:
        scale_reports = {
            scale: self._scale_report(scale, window)
            for scale in SCALE_ORDER
            if window.by_scale(scale)
        }
        cross_scale_reports = tuple(
            self._cross_scale_report(mapping, window) for mapping in self.mappings
        )
        boundary = self._boundary_report(scale_reports, cross_scale_reports)
        warnings: list[str] = []
        if set(scale_reports) != set(SCALE_ORDER):
            missing = sorted({scale.value for scale in SCALE_ORDER if scale not in scale_reports})
            warnings.append(f"missing_scales={missing}")
        status = "ok" if not warnings else "partial"
        return FractalCognitionReport(
            status=status,
            end_timestamp=window.end_timestamp,
            scale_reports=scale_reports,
            cross_scale_reports=cross_scale_reports,
            boundary=boundary,
            warnings=tuple(warnings),
        )

    def _scale_report(self, scale: Scale, window: CausalWindow) -> ScaleReport:
        observations = window.by_scale(scale)
        feature_names = sorted({name for item in observations for name in item.features})
        metrics: dict[str, FractalMetrics] = {}
        latest_values: list[float] = []
        for name in feature_names:
            values = [item.features[name] for item in observations if name in item.features]
            if len(values) >= 2:
                metrics[name] = compute_fractal_metrics(values)
                latest_values.append(float(values[-1]))
        if len(latest_values) >= 2:
            aggregate_pressure = sum(abs(value) for value in zscore(latest_values)) / len(
                latest_values
            )
        else:
            aggregate_pressure = 0.0
        return ScaleReport(
            scale=scale,
            feature_metrics=metrics,
            aggregate_pressure=aggregate_pressure,
        )

    def _cross_scale_report(
        self,
        mapping: FeatureMapping,
        window: CausalWindow,
    ) -> CrossScaleReport:
        source = window.latest(mapping.source_scale)
        target = window.latest(mapping.target_scale)
        left, right = mapping.mapped_values(source, target)
        return CrossScaleReport(
            source_scale=mapping.source_scale,
            target_scale=mapping.target_scale,
            coherence=cosine_similarity(left, right),
            mapped_pairs=mapping.pairs,
        )

    def _boundary_report(
        self,
        scale_reports: dict[Scale, ScaleReport],
        cross_scale_reports: tuple[CrossScaleReport, ...],
    ) -> BoundaryReport:
        drivers: dict[str, float] = {}
        for scale, scale_report in scale_reports.items():
            drivers[f"{scale.value}.pressure"] = scale_report.aggregate_pressure
            for feature, metrics in scale_report.feature_metrics.items():
                drivers[f"{scale.value}.{feature}.roughness"] = metrics.roughness
        for cross_report in cross_scale_reports:
            key = (
                f"{cross_report.source_scale.value}"
                f"->{cross_report.target_scale.value}.coherence"
            )
            drivers[key] = abs(cross_report.coherence)
        pressure = sum(drivers.values()) / max(len(drivers), 1)
        distance = max(0.0, self.boundary_threshold - pressure)
        return BoundaryReport(distance=distance, active=distance == 0.0, drivers=drivers)
