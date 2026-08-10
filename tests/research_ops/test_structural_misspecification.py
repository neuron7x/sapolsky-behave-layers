from experiments.csca_02_ua.common import evaluate_raw_case, generate_case


def test_shared_wrong_edge_can_have_low_model_disagreement_but_bad_intervention_adequacy():
    raw = evaluate_raw_case(generate_case(41000, "M11_SHARED_MODEL_CLASS_MISSPECIFICATION"))
    assert raw.provisional_candidate == "C"
    assert raw.intervention_nrmse > 0.5


def test_missing_true_edge_is_detectable_by_intervention_mismatch():
    raw = evaluate_raw_case(generate_case(31000, "M2_MISSING_TRUE_EDGE"))
    assert raw.intervention_nrmse > 0.5
