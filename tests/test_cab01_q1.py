from __future__ import annotations

from cwc.benchmarks.causal_authority import (
    ABSTAIN_STATE,
    INTERVENTION_SCOPE,
    INTERVENTION_STATE,
    QUERY_STATE,
    REJECT_STATE,
    ROBUST_SCOPE,
    ROBUST_STATE,
    analytic_oracle,
    decisions_equal,
    generate_case,
    generate_cohort,
    pareto_dominates,
    policy_decision_relevant,
    policy_full_model_maximin,
    score_policy,
    surface_signature,
    validate_f11_triads,
)


def test_frozen_family_state_binding():
    expected = {
        "F0": ROBUST_STATE,
        "F1": QUERY_STATE,
        "F2": ABSTAIN_STATE,
        "F3": ABSTAIN_STATE,
        "F4": ROBUST_STATE,
        "F5": INTERVENTION_STATE,
        "F6": REJECT_STATE,
        "F7": REJECT_STATE,
        "F8": QUERY_STATE,
        "F9": QUERY_STATE,
        "F10": ABSTAIN_STATE,
    }
    for i, (family, state) in enumerate(expected.items()):
        case = generate_case(family, "T", 1000 + i)
        assert case.expected_state == state
        a_state, a = analytic_oracle(case.task)
        assert a_state == state
        assert decisions_equal(a, case.construction_label)
        assert decisions_equal(policy_decision_relevant(case.task), case.construction_label)


def test_f11_triads_are_surface_preserving_and_state_flipping():
    cases = [generate_case("F11", "T", 12345, variant=v) for v in ("A", "Q", "B")]
    passed, errors = validate_f11_triads(cases)
    assert passed, errors
    assert len({surface_signature(c.task) for c in cases}) == 1
    assert {c.construction_label.kind for c in cases} == {"ACT", "QUERY", "ABSTAIN"}


def test_f8_full_model_and_decision_relevant_policies_separate():
    case = generate_case("F8", "T", 818181)
    legacy = policy_full_model_maximin(case.task)
    focused = policy_decision_relevant(case.task)
    assert legacy.kind == "QUERY"
    assert focused.kind == "QUERY"
    assert legacy.query_id == "Q000"
    assert focused.query_id == "Q001"


def test_high_aleatoric_uncertainty_does_not_force_decision_query():
    case = generate_case("F4", "T", 404040)
    out = policy_decision_relevant(case.task)
    assert out.kind == "ACT"
    assert out.authority_scope == ROBUST_SCOPE


def test_intervention_support_is_scoped_not_causal_truth():
    case = generate_case("F5", "T", 505050)
    out = policy_decision_relevant(case.task)
    assert out.kind == "ACT"
    assert out.authority_scope == INTERVENTION_SCOPE
    assert out.action_id == "A001"


def test_observed_falsifiers_preempt_action_and_query():
    for family in ("F6", "F7"):
        case = generate_case(family, "T", 606060 + int(family[1:]))
        out = policy_decision_relevant(case.task)
        assert out.kind == "REJECT_MODEL"
        assert decisions_equal(out, case.construction_label)


def test_generation_is_deterministic():
    a = generate_cohort("PRIMARY", 310811, 8)
    b = generate_cohort("PRIMARY", 310811, 8)
    assert a == b


def test_expected_cohort_shape():
    cases = generate_cohort("PRIMARY", 310811, 4)
    assert len(cases) == 11 * 4 + 3 * 4
    assert sum(c.family == "F11" for c in cases) == 12


def test_decision_relevant_policy_is_exact_on_small_cohort():
    cases = generate_cohort("T", 999, 8)
    outs = [policy_decision_relevant(c.task) for c in cases]
    metrics = score_policy(cases, outs)
    assert metrics["terminal_accuracy"] == 1.0
    assert metrics["false_causal_authority_rate"] == 0.0
    assert metrics["wrong_irreversible_action_rate"] == 0.0


def test_pareto_comparator_respects_cost_orientation():
    better = {
        "false_causal_authority_rate": 0.0,
        "wrong_irreversible_action_rate": 0.0,
        "correct_robust_action_rate": 1.0,
        "necessary_query_recall": 1.0,
        "unnecessary_query_cost": 0.0,
        "no_information_abstention_accuracy": 1.0,
        "model_assumption_rejection_precision": 1.0,
        "post_hoc_abstention_rate": 0.0,
        "total_query_cost": 0.0,
        "coverage": 1.0,
    }
    worse = dict(better)
    worse["wrong_irreversible_action_rate"] = 0.1
    assert pareto_dominates(better, worse)
    assert not pareto_dominates(worse, better)
