import pytest

from cwc.governance.baseline_panel import (
    BaselineKind,
    BaselinePanelSeal,
    BaselinePolicySpec,
    bind_verified_learned_router_fit,
    freeze_learned_baseline_fit,
)


def _static(kind: BaselineKind) -> BaselinePolicySpec:
    return BaselinePolicySpec(
        kind=kind,
        implementation_version="v1",
        feature_schema_digest="features",
        policy_config_digest=f"config-{kind.value}",
    )


def _learned() -> BaselinePolicySpec:
    return BaselinePolicySpec(
        kind=BaselineKind.LEARNED_COST_QUALITY_ROUTER,
        implementation_version="v1",
        feature_schema_digest="features",
        policy_config_digest="config-b2",
        training_algorithm_digest="ridge-cost-quality-router-v1",
    )


def test_panel_is_not_executable_frozen_before_learned_fit():
    panel = BaselinePanelSeal((
        _static(BaselineKind.FIXED_COMPUTE),
        _static(BaselineKind.UNCERTAINTY_ROUTER),
        _learned(),
        _static(BaselineKind.SEQUENTIAL_VERIFICATION),
    ))
    assert not panel.executable_frozen


def test_panel_becomes_frozen_only_after_calibration_fit_digest_exists():
    learned = freeze_learned_baseline_fit(
        _learned(), calibration_task_digest="cal-tasks", fitted_model_digest="model-fit"
    )
    panel = BaselinePanelSeal((
        _static(BaselineKind.FIXED_COMPUTE),
        _static(BaselineKind.UNCERTAINTY_ROUTER),
        learned,
        _static(BaselineKind.SEQUENTIAL_VERIFICATION),
    ))
    assert panel.executable_frozen
    assert len(panel.digest) == 64


def test_verified_fit_binding_rejects_schema_or_algorithm_substitution():
    with pytest.raises(ValueError, match="feature schema"):
        bind_verified_learned_router_fit(
            _learned(),
            feature_schema_digest="different-features",
            training_algorithm_digest="ridge-cost-quality-router-v1",
            calibration_task_digest="cal",
            fitted_model_digest="model",
        )
    with pytest.raises(ValueError, match="training algorithm"):
        bind_verified_learned_router_fit(
            _learned(),
            feature_schema_digest="features",
            training_algorithm_digest="different-algorithm",
            calibration_task_digest="cal",
            fitted_model_digest="model",
        )


def test_verified_fit_binding_accepts_exact_pre_fit_identities():
    fitted = bind_verified_learned_router_fit(
        _learned(),
        feature_schema_digest="features",
        training_algorithm_digest="ridge-cost-quality-router-v1",
        calibration_task_digest="cal",
        fitted_model_digest="model",
    )
    assert fitted.executable_frozen
    assert fitted.calibration_task_digest == "cal"
    assert fitted.fitted_model_digest == "model"


def test_missing_baseline_fails_closed():
    with pytest.raises(ValueError):
        BaselinePanelSeal((
            _static(BaselineKind.FIXED_COMPUTE),
            _static(BaselineKind.UNCERTAINTY_ROUTER),
            _learned(),
        ))


def test_duplicate_baseline_fails_closed():
    with pytest.raises(ValueError):
        BaselinePanelSeal((
            _static(BaselineKind.FIXED_COMPUTE),
            _static(BaselineKind.FIXED_COMPUTE),
            _learned(),
            _static(BaselineKind.SEQUENTIAL_VERIFICATION),
        ))


def test_learned_baseline_requires_training_algorithm():
    with pytest.raises(ValueError):
        BaselinePolicySpec(
            kind=BaselineKind.LEARNED_COST_QUALITY_ROUTER,
            implementation_version="v1",
            feature_schema_digest="features",
            policy_config_digest="config",
        )


def test_static_baseline_cannot_fake_fitted_model_authority():
    with pytest.raises(ValueError):
        BaselinePolicySpec(
            kind=BaselineKind.FIXED_COMPUTE,
            implementation_version="v1",
            feature_schema_digest="features",
            policy_config_digest="config",
            fitted_model_digest="fake",
        )
