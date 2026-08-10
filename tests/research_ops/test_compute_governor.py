from __future__ import annotations

from cwc.research_ops.compute_governor import ComputeGovernor, ComputeRequest


def req(stage: str, **kwargs):
    base = dict(
        compute_request_id=f"R-{stage}",
        hypothesis_id="H",
        experiment_id="E",
        stage=stage,
        scientific_question="Q",
        kill_condition="FAIL if null matches target",
        why_small_scale_is_insufficient="Reason",
        expected_information_gain=1.0,
        estimated_cost_units=2.0,
    )
    base.update(kwargs)
    return ComputeRequest(**base)


def test_c2_cannot_bypass_c0_c1() -> None:
    decision = ComputeGovernor.evaluate(req("C2", baseline_completed=True))
    assert not decision.approved
    assert decision.reason == "REJECT_C0_C1_NOT_PASSED"


def test_c3_requires_all_scale_predicates() -> None:
    blocked = ComputeGovernor.evaluate(req("C3", c0_pass=True, c1_pass=True))
    assert not blocked.approved
    allowed = ComputeGovernor.evaluate(req(
        "C3",
        c0_pass=True,
        c1_pass=True,
        mechanism_survived_nulls=True,
        signal_replicated_across_seeds=True,
        ood_test_justifies_scale=True,
        scaling_question_is_explicit=True,
    ))
    assert allowed.approved
