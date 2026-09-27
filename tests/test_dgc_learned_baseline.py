import random
import pytest
from cwc.governance.learned_baseline import CalibrationExample, LearnedRouterConfig, fit_learned_router


def config():
    return LearnedRouterConfig(
        feature_names=("difficulty",),
        action_ids=("cheap", "deep"),
        ridge_lambda=0.1,
        quality_weight=1.0,
        cost_weight=0.2,
        regret_weight=1.0,
    )


def population():
    rows=[]
    for i,difficulty in enumerate((0.0,0.2,0.8,1.0)):
        task=f"c{i}"
        rows.append(CalibrationExample(task,"cheap",(difficulty,),quality=1.0-0.6*difficulty,cost_usd=0.1,catastrophic_regret=0.4*difficulty))
        rows.append(CalibrationExample(task,"deep",(difficulty,),quality=0.75+0.2*difficulty,cost_usd=0.8,catastrophic_regret=0.02))
    return rows


def test_fit_is_deterministic_under_row_shuffle():
    rows=population()
    first=fit_learned_router(config(),rows)
    random.Random(7).shuffle(rows)
    second=fit_learned_router(config(),rows)
    assert first.model_digest==second.model_digest
    assert first.calibration_task_digest==second.calibration_task_digest


def test_router_learns_cheap_easy_deep_hard():
    fitted=fit_learned_router(config(),population())
    assert fitted.predict((0.0,))=="cheap"
    assert fitted.predict((1.0,))=="deep"


def test_confirmatory_leakage_rejected():
    with pytest.raises(ValueError,match="leakage"):
        fit_learned_router(config(),population(),forbidden_task_ids=("c2",))


def test_missing_counterfactual_action_rejected():
    rows=population()[:-1]
    with pytest.raises(ValueError,match="complete counterfactual"):
        fit_learned_router(config(),rows)


def test_duplicate_task_action_rejected():
    rows=population()
    rows.append(rows[0])
    with pytest.raises(ValueError,match="exactly once"):
        fit_learned_router(config(),rows)


def test_invalid_feature_shape_and_nonfinite_values_rejected():
    rows=population()
    rows[0]=CalibrationExample("c0","cheap",(0.0,1.0),quality=.9,cost_usd=.1,catastrophic_regret=0)
    with pytest.raises(ValueError,match="feature length"):
        fit_learned_router(config(),rows)
    with pytest.raises(ValueError,match="finite"):
        CalibrationExample("x","cheap",(float("nan"),),quality=.9,cost_usd=.1,catastrophic_regret=0)
