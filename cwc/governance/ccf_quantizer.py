from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR

from cwc.governance.counterfactual_oracle_spec import CounterfactualOracleSpec
from cwc.governance.counterfactual_frontier import CounterfactualOption


class CCFQuantizationError(ValueError):
    pass


def _decimal(name: str, value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CCFQuantizationError(f"{name} must be decimal-compatible") from exc
    if not result.is_finite():
        raise CCFQuantizationError(f"{name} must be finite")
    return result


def _ceil_units(value: Decimal, quantum: Decimal) -> int:
    return int((value / quantum).to_integral_value(rounding=ROUND_CEILING))


def _floor_units(value: Decimal, quantum: Decimal) -> int:
    return int((value / quantum).to_integral_value(rounding=ROUND_FLOOR))


@dataclass(frozen=True, slots=True)
class RawCounterfactualOption:
    task_id: str
    option_id: str
    cost_usd: float
    quality: float
    latency_ms: float
    catastrophic_regret: float


def quantize_counterfactual_option(
    raw: RawCounterfactualOption,
    *,
    spec: CounterfactualOracleSpec,
) -> CounterfactualOption:
    task = str(raw.task_id).strip()
    option = str(raw.option_id).strip()
    if not task or not option:
        raise CCFQuantizationError("task_id and option_id required")
    cost = _decimal("cost_usd", raw.cost_usd)
    quality = _decimal("quality", raw.quality)
    latency = _decimal("latency_ms", raw.latency_ms)
    regret = _decimal("catastrophic_regret", raw.catastrophic_regret)
    if cost < 0 or latency < 0:
        raise CCFQuantizationError("cost and latency must be >= 0")
    if not Decimal("0") <= quality <= Decimal("1"):
        raise CCFQuantizationError("quality must be in [0,1]")
    if not Decimal("0") <= regret <= Decimal("1"):
        raise CCFQuantizationError("catastrophic_regret must be in [0,1]")

    # Conservative by construction: resources/risk round upward, value rounds downward.
    return CounterfactualOption(
        task_id=task,
        option_id=option,
        cost_units=_ceil_units(cost, _decimal("cost_usd_per_unit", spec.cost_usd_per_unit)),
        value_units=_floor_units(quality, _decimal("quality_per_value_unit", spec.quality_per_value_unit)),
        latency_units=_ceil_units(latency, _decimal("latency_ms_per_unit", spec.latency_ms_per_unit)),
        risk_units=_ceil_units(regret, _decimal("regret_per_risk_unit", spec.regret_per_risk_unit)),
    )
