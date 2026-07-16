from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .types import FeatureMapping, FractalValidationError, Scale


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FractalValidationError("protocol must be a mapping")
    return payload


def validate_protocol(protocol_path: Path, schema_path: Path) -> list[str]:
    protocol = load_yaml(protocol_path)
    schema = load_yaml(schema_path)
    validator = Draft202012Validator(schema)
    errors = [error.message for error in sorted(validator.iter_errors(protocol), key=str)]
    if errors:
        return errors

    semantic_errors: list[str] = []
    if protocol["status"] != "frozen":
        semantic_errors.append("protocol must be frozen before confirmatory analysis")
    if set(protocol["scales"]) != {"micro", "meso", "macro"}:
        semantic_errors.append("protocol must include exactly micro, meso and macro scales")

    seen_edges: set[tuple[str, str]] = set()
    for mapping in protocol["feature_mappings"]:
        source = mapping["source_scale"]
        target = mapping["target_scale"]
        if source == target:
            semantic_errors.append(f"self-scale mapping is forbidden: {source}->{target}")
        seen_edges.add((source, target))
    required_edges = {("micro", "meso"), ("meso", "macro")}
    if not required_edges.issubset(seen_edges):
        missing_edges = sorted(required_edges - seen_edges)
        semantic_errors.append(f"missing required cross-scale edges: {missing_edges}")

    gates = protocol["acceptance_gates"]
    if gates["require_all_scales"] is not True:
        semantic_errors.append("acceptance_gates.require_all_scales must be true")
    if gates["require_semantic_mappings"] is not True:
        semantic_errors.append("acceptance_gates.require_semantic_mappings must be true")
    if gates["require_null_model_separation"] is not True:
        semantic_errors.append("acceptance_gates.require_null_model_separation must be true")
    return semantic_errors


def mappings_from_protocol(protocol: dict[str, Any]) -> tuple[FeatureMapping, ...]:
    mappings: list[FeatureMapping] = []
    for item in protocol["feature_mappings"]:
        mappings.append(
            FeatureMapping(
                source_scale=Scale(item["source_scale"]),
                target_scale=Scale(item["target_scale"]),
                pairs=tuple((str(left), str(right)) for left, right in item["pairs"]),
            )
        )
    return tuple(mappings)
