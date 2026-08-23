from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SyntheticFinancialTheorem:
    reference_expected_cost: float
    dgc_core_expected_cost: float
    core_savings: float
    threshold: float
    max_overhead_for_threshold: float
    max_overhead_fraction_of_reference: float
    quality_delta: float


def synthetic_financial_theorem(*, threshold: float = 0.30) -> SyntheticFinancialTheorem:
    """Closed-form DGC-01 financial result under the frozen A-E generator."""
    if not 0.0 <= threshold < 1.0:
        raise ValueError("threshold must be in [0,1)")
    mean_cost = {
        "A": (0.08 + 0.12) / 2.0,
        "B": (0.025 + 0.045) / 2.0,
        "C": (0.08 + 0.12) / 2.0,
        "D": (0.08 + 0.12) / 2.0,
        "E": (0.055 + 0.06) / 2.0,
    }
    min_expected_regret = {
        "B": min(0.10 * 0.95, (1.0 - 0.16) * 0.14),
        "C": min(0.44 * 0.80, (1.0 - 0.56) * 0.80),
        "E": min(0.045 * 1.40, (1.0 - 0.05) * 0.15),
    }
    max_diagnostic_cost = {"B": 0.045, "C": 0.12, "E": 0.06}
    if not all(min_expected_regret[r] > max_diagnostic_cost[r] for r in ("B", "C", "E")):
        raise RuntimeError("frozen workload no longer proves positive VOC in B/C/E")
    reference = sum(mean_cost.values()) / 5.0
    dgc_core = sum(mean_cost[r] for r in ("B", "C", "E")) / 5.0
    savings = 1.0 - dgc_core / reference
    max_overhead = (1.0 - threshold) * reference - dgc_core
    return SyntheticFinancialTheorem(
        reference_expected_cost=reference,
        dgc_core_expected_cost=dgc_core,
        core_savings=savings,
        threshold=threshold,
        max_overhead_for_threshold=max_overhead,
        max_overhead_fraction_of_reference=max_overhead / reference,
        quality_delta=0.0,
    )


def savings_with_mean_overhead(overhead: float) -> float:
    if overhead < 0:
        raise ValueError("overhead must be non-negative")
    t = synthetic_financial_theorem()
    return 1.0 - (t.dgc_core_expected_cost + overhead) / t.reference_expected_cost
