from __future__ import annotations

import pytest

from cwc.governance.drift_sensitivity import DriftDirection, certify_drift_detection_sensitivity


def test_large_upward_shift_has_high_certified_detection_power():
    c=certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.5,tolerance=.05,alternative_mean=.9,direction=DriftDirection.UP,horizon=200,alpha=.05,minimum_required_power=.95)
    assert c.detection_power_lower_bound > .99 and c.deployment_guard_satisfied


def test_large_downward_shift_is_symmetric():
    up=certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.5,tolerance=.05,alternative_mean=.9,direction="UP",horizon=200,alpha=.05,minimum_required_power=.95)
    down=certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.5,tolerance=.05,alternative_mean=.1,direction="DOWN",horizon=200,alpha=.05,minimum_required_power=.95)
    assert down.detection_power_lower_bound == pytest.approx(up.detection_power_lower_bound)


def test_shift_too_small_for_horizon_fails_deployment_guard():
    c=certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.5,tolerance=.05,alternative_mean=.6,direction="UP",horizon=200,alpha=.05,minimum_required_power=.8)
    assert c.detection_power_lower_bound == 0.0 and not c.deployment_guard_satisfied


def test_wrong_direction_or_invalid_band_fails_closed():
    with pytest.raises(ValueError): certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.5,tolerance=.05,alternative_mean=.4,direction="UP",horizon=100)
    with pytest.raises(ValueError): certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.95,tolerance=.1,alternative_mean=.5,direction="DOWN",horizon=100)
