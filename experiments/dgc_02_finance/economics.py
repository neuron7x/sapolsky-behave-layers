from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValueBasedCommercialCase:
    decision_volume: float
    baseline_cost_per_decision: float
    dgc_cost_per_decision: float
    verified_client_savings: float
    contractual_share: float
    value_based_fee: float
    annualized_fee: float


def value_based_case(
    *,
    decision_volume: float,
    baseline_cost_per_decision: float,
    dgc_cost_per_decision: float,
    contractual_share: float,
    periods_per_year: float = 12.0,
    client_verified: bool,
    quality_gate_passed: bool,
) -> ValueBasedCommercialCase:
    values = {
        "decision_volume": float(decision_volume),
        "baseline_cost_per_decision": float(baseline_cost_per_decision),
        "dgc_cost_per_decision": float(dgc_cost_per_decision),
        "contractual_share": float(contractual_share),
        "periods_per_year": float(periods_per_year),
    }
    if any(v < 0 for v in values.values()):
        raise ValueError("commercial inputs must be non-negative")
    if not 0.0 <= values["contractual_share"] <= 1.0:
        raise ValueError("contractual_share must be in [0,1]")
    if not client_verified or not quality_gate_passed:
        raise RuntimeError("COMMERCIAL_PRICING_NOT_AUTHORIZED")
    saving_per_decision = max(0.0, values["baseline_cost_per_decision"] - values["dgc_cost_per_decision"])
    verified_savings = values["decision_volume"] * saving_per_decision
    fee = values["contractual_share"] * verified_savings
    return ValueBasedCommercialCase(
        decision_volume=values["decision_volume"],
        baseline_cost_per_decision=values["baseline_cost_per_decision"],
        dgc_cost_per_decision=values["dgc_cost_per_decision"],
        verified_client_savings=verified_savings,
        contractual_share=values["contractual_share"],
        value_based_fee=fee,
        annualized_fee=fee * values["periods_per_year"],
    )
