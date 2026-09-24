from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.calibration_variance import CalibrationObservation
from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan
from cwc.governance.mechanism_trial_sizing import (
    MechanismTrialSizingError,
    freeze_mechanism_trial_sizing,
    verify_mechanism_trial_sizing_document,
)


def _observations(*, comparisons: int = 8):
    rows = []
    for index in range(comparisons):
        comparison = f"cmp-{index:02d}"
        for task_index in range(4):
            task = f"task-{task_index}"
            center = 0.01 * task_index
            rows.append(CalibrationObservation(comparison, task, 0, center))
            rows.append(CalibrationObservation(comparison, task, 1, center + 0.01))
    return rows


def _effects(*, comparisons: int = 8):
    return {f"cmp-{index:02d}": 0.50 for index in range(comparisons)}


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_mechanism_sizing_freezes_eight_comparisons_and_global_max(tmp_path: Path):
    plan = MechanismStatisticalPlan(min_trials_per_task=2, max_trials_per_task=20)
    receipt = freeze_mechanism_trial_sizing(
        observations=_observations(),
        effects_of_interest=_effects(),
        confirmatory_task_count=40,
        plan=plan,
    )
    assert len(receipt.comparisons) == 8
    assert receipt.required_trials_per_task == max(
        row.required_trials_per_task for row in receipt.comparisons
    )
    assert 2 <= receipt.required_trials_per_task <= 20
    assert all(row.per_claim_alpha == pytest.approx(plan.per_claim_alpha) for row in receipt.comparisons)
    out = _write(tmp_path / "mechanism-sizing.json", receipt.document)
    verified = verify_mechanism_trial_sizing_document(out, plan=plan)
    assert verified["planning_only"] is True
    assert verified["calibration_only"] is True
    assert verified["confirmatory_outcomes_observed"] is False
    assert verified["product_promotion_authorized"] is False


def test_missing_baseline_endpoint_comparison_is_rejected():
    plan = MechanismStatisticalPlan(min_trials_per_task=2, max_trials_per_task=20)
    with pytest.raises(MechanismTrialSizingError, match="exactly 8"):
        freeze_mechanism_trial_sizing(
            observations=_observations(comparisons=7),
            effects_of_interest=_effects(comparisons=7),
            confirmatory_task_count=40,
            plan=plan,
        )


def test_comparison_design_mismatch_is_rejected():
    plan = MechanismStatisticalPlan(min_trials_per_task=2, max_trials_per_task=20)
    rows = _observations()
    rows = [
        row for row in rows
        if not (row.comparison_id == "cmp-07" and row.task_id == "task-3")
    ]
    with pytest.raises((MechanismTrialSizingError, ValueError), match="identical|balanced"):
        freeze_mechanism_trial_sizing(
            observations=rows,
            effects_of_interest=_effects(),
            confirmatory_task_count=40,
            plan=plan,
        )


def test_effect_population_must_match_exactly():
    plan = MechanismStatisticalPlan(min_trials_per_task=2, max_trials_per_task=20)
    effects = _effects()
    effects.pop("cmp-07")
    with pytest.raises(MechanismTrialSizingError, match="match mechanism calibration"):
        freeze_mechanism_trial_sizing(
            observations=_observations(),
            effects_of_interest=effects,
            confirmatory_task_count=40,
            plan=plan,
        )


def test_task_heterogeneity_that_repeats_cannot_fix_fails_closed():
    plan = MechanismStatisticalPlan(min_trials_per_task=2, max_trials_per_task=20)
    rows = []
    for index in range(8):
        comparison = f"cmp-{index:02d}"
        for task, value in (("a", 0.0), ("b", 5.0), ("c", 10.0), ("d", 15.0)):
            rows.append(CalibrationObservation(comparison, task, 0, value))
            rows.append(CalibrationObservation(comparison, task, 1, value))
    with pytest.raises(MechanismTrialSizingError, match="UNDERPOWERED_TASK_HETEROGENEITY"):
        freeze_mechanism_trial_sizing(
            observations=rows,
            effects_of_interest={f"cmp-{i:02d}": 0.05 for i in range(8)},
            confirmatory_task_count=10,
            plan=plan,
        )


def test_tampered_receipt_digest_is_rejected(tmp_path: Path):
    plan = MechanismStatisticalPlan(min_trials_per_task=2, max_trials_per_task=20)
    receipt = freeze_mechanism_trial_sizing(
        observations=_observations(),
        effects_of_interest=_effects(),
        confirmatory_task_count=40,
        plan=plan,
    )
    doc = receipt.document
    doc["required_trials_per_task"] += 1
    out = _write(tmp_path / "tampered.json", doc)
    with pytest.raises(MechanismTrialSizingError, match="global mechanism repeat count|digest mismatch"):
        verify_mechanism_trial_sizing_document(out, plan=plan)


def test_authority_flags_are_fail_closed(tmp_path: Path):
    plan = MechanismStatisticalPlan(min_trials_per_task=2, max_trials_per_task=20)
    receipt = freeze_mechanism_trial_sizing(
        observations=_observations(),
        effects_of_interest=_effects(),
        confirmatory_task_count=40,
        plan=plan,
    )
    doc = receipt.document
    doc["product_promotion_authorized"] = True
    out = _write(tmp_path / "illegal.json", doc)
    with pytest.raises(MechanismTrialSizingError, match="authority boundary"):
        verify_mechanism_trial_sizing_document(out, plan=plan)
