from __future__ import annotations

from cwc.benchmarks.causal_authority import generate_cohort
from experiments.cab_01_q1_r1.run import evaluate_surface_null


def test_r1_surface_null_uses_same_heldout_prior_and_structural_gate():
    cases = generate_cohort("T", 510811, 16)
    result = evaluate_surface_null(cases)
    assert result["unique_surface_signatures"] == 1
    assert result["structural_surface_null_pass"] is True
    assert result["heldout_predictive_null_pass"] is True
    assert result["surface_leakage_pass"] is True
    assert result["surface_only_accuracy"] <= result["heldout_majority_class_rate"] + 1e-12
