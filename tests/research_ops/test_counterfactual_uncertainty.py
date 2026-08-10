from experiments.csca_02_ua.common import evaluate_raw_case, generate_case


def test_correct_structure_has_resolved_a_credit():
    raw = evaluate_raw_case(generate_case(31000, "M0_CORRECT_STRUCTURE"))
    assert raw.provisional_candidate == "A"
    assert raw.credit_intervals["A"]["lower"] > raw.credit_intervals["C"]["upper"]


def test_uncertainty_surfaces_are_separate():
    raw = evaluate_raw_case(generate_case(31001, "M1_SPURIOUS_EDGE"))
    assert set(raw.epistemic_uncertainty) == {
        "parameter_data", "model_family", "structural_intervention_nrmse", "context_ood_surprisal"
    }
