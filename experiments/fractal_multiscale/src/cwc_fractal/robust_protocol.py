from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .protocol import mappings_from_protocol
from .types import FeatureMapping, FractalValidationError


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FractalValidationError("protocol must be a mapping")
    return payload


def validate_robust_protocol(protocol_path: Path, schema_path: Path) -> list[str]:
    protocol = load_yaml(protocol_path)
    schema = load_yaml(schema_path)
    validator = Draft202012Validator(schema)
    errors = [error.message for error in sorted(validator.iter_errors(protocol), key=str)]
    if errors:
        return errors
    semantic: list[str] = []
    if set(protocol["scales"]) != {"micro", "meso", "macro"}:
        semantic.append("protocol must contain exactly micro, meso and macro")
    edges = {
        (item["source_scale"], item["target_scale"]) for item in protocol["feature_mappings"]
    }
    required = {("micro", "meso"), ("meso", "macro")}
    missing = required - edges
    if missing:
        semantic.append(f"missing required edges: {sorted(missing)}")
    if any(source == target for source, target in edges):
        semantic.append("self-scale mapping is forbidden")
    required_nulls = {
        "within_stratum_shuffle_target",
        "circular_shift_target",
        "block_permutation_target",
    }
    if set(protocol["null_models"]) != required_nulls:
        semantic.append("robust protocol must freeze exactly the three required null families")
    gates = protocol["acceptance_gates"]
    if gates["require_all_scales"] is not True or gates["require_all_edges"] is not True:
        semantic.append("all scales and all required edges must be fail-closed")
    if gates["require_synthetic_control_calibration"] is not True:
        semantic.append("synthetic control calibration must be mandatory")
    return semantic


def robust_mappings(protocol: dict[str, Any]) -> tuple[FeatureMapping, ...]:
    return mappings_from_protocol(protocol)
