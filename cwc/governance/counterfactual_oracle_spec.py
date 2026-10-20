from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import SupportsFloat, SupportsIndex, SupportsInt

SCHEMA = "DGC_COUNTERFACTUAL_ORACLE_SPEC_V1"
AGGREGATION = "REPLICATE_WISE_TASK_FRONTIER_V1"
ROUNDING = "CEIL_RESOURCES_FLOOR_VALUE_V1"


class CounterfactualOracleSpecError(ValueError):
    pass


def _int_arg(value: object) -> int:
    """``int(value)`` for an untyped decoded value; non-convertible types raise ``int``'s own TypeError."""
    if isinstance(value, (str, bytes, bytearray, memoryview, SupportsInt, SupportsIndex)):
        return int(value)
    raise TypeError(f"int() argument must be a string, a bytes-like object or a real number, not {type(value).__name__!r}")


def _float_arg(value: object) -> float:
    """``float(value)`` for an untyped decoded value; non-convertible types raise ``float``'s own TypeError."""
    if isinstance(value, (str, bytes, bytearray, memoryview, SupportsFloat, SupportsIndex)):
        return float(value)
    raise TypeError(f"float() argument must be a string or a real number, not {type(value).__name__!r}")


def _req(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise CounterfactualOracleSpecError(f"{name} required")
    return text


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise CounterfactualOracleSpecError(f"{name} must be lowercase SHA-256")
    return text


def _positive(name: str, value: object) -> float:
    try:
        result = _float_arg(value)
    except (TypeError, ValueError) as exc:
        raise CounterfactualOracleSpecError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or result <= 0:
        raise CounterfactualOracleSpecError(f"{name} must be finite and > 0")
    return result


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool):
        raise CounterfactualOracleSpecError(f"{name} must be an integer")
    try:
        result = _int_arg(value)
    except (TypeError, ValueError) as exc:
        raise CounterfactualOracleSpecError(f"{name} must be an integer") from exc
    if result <= 0:
        raise CounterfactualOracleSpecError(f"{name} must be > 0")
    return result


@dataclass(frozen=True, slots=True)
class CounterfactualOracleSpec:
    quantizer_implementation_sha256: str
    option_set_contract_sha256: str
    cost_usd_per_unit: float
    quality_per_value_unit: float
    latency_ms_per_unit: float
    regret_per_risk_unit: float
    max_cost_units_per_task: int
    max_latency_units_per_task: int
    max_risk_units_per_task: int
    aggregation: str = AGGREGATION
    rounding_mode: str = ROUNDING


def parse_counterfactual_oracle_spec(payload: Mapping[str, object]) -> CounterfactualOracleSpec:
    if payload.get("schema") != SCHEMA:
        raise CounterfactualOracleSpecError("unexpected counterfactual oracle spec schema")
    if _req("aggregation", payload.get("aggregation")) != AGGREGATION:
        raise CounterfactualOracleSpecError("unsupported counterfactual oracle aggregation")
    if _req("rounding_mode", payload.get("rounding_mode")) != ROUNDING:
        raise CounterfactualOracleSpecError("counterfactual oracle requires conservative resource/value rounding")
    return CounterfactualOracleSpec(
        quantizer_implementation_sha256=_sha(
            "quantizer_implementation_sha256", payload.get("quantizer_implementation_sha256")
        ),
        option_set_contract_sha256=_sha(
            "option_set_contract_sha256", payload.get("option_set_contract_sha256")
        ),
        cost_usd_per_unit=_positive("cost_usd_per_unit", payload.get("cost_usd_per_unit")),
        quality_per_value_unit=_positive("quality_per_value_unit", payload.get("quality_per_value_unit")),
        latency_ms_per_unit=_positive("latency_ms_per_unit", payload.get("latency_ms_per_unit")),
        regret_per_risk_unit=_positive("regret_per_risk_unit", payload.get("regret_per_risk_unit")),
        max_cost_units_per_task=_positive_int(
            "max_cost_units_per_task", payload.get("max_cost_units_per_task")
        ),
        max_latency_units_per_task=_positive_int(
            "max_latency_units_per_task", payload.get("max_latency_units_per_task")
        ),
        max_risk_units_per_task=_positive_int(
            "max_risk_units_per_task", payload.get("max_risk_units_per_task")
        ),
        aggregation=AGGREGATION,
        rounding_mode=ROUNDING,
    )
