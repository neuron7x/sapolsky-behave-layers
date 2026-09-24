import pytest

from cwc.governance.generalization_evidence import (
    GeneralizationAxis,
    GeneralizationAxisResult,
    certify_generalization,
)


def _row(axis, *, policy="dgc-frozen", retuned=False, cost=True):
    return GeneralizationAxisResult(
        axis=axis,
        frozen_policy_digest=policy,
        evaluation_manifest_digest=f"manifest-{axis.value}",
        policy_retuned=retuned,
        quality_noninferiority_supported=True,
        catastrophic_regret_noninferiority_supported=True,
        coverage_supported=True,
        cost_effect_direction_positive=cost,
    )


def test_all_five_axes_same_frozen_policy_support_generalization():
    cert = certify_generalization(tuple(_row(axis) for axis in GeneralizationAxis))
    assert cert.supported


def test_missing_axis_fails_closed():
    with pytest.raises(ValueError):
        certify_generalization(tuple(_row(axis) for axis in list(GeneralizationAxis)[:-1]))


def test_policy_retuning_invalidates_generalization_support():
    rows = tuple(
        _row(axis, retuned=(axis is GeneralizationAxis.CHANGED_ECONOMICS))
        for axis in GeneralizationAxis
    )
    assert not certify_generalization(rows).supported


def test_different_policy_digest_across_axes_fails_closed():
    rows = tuple(
        _row(axis, policy="other" if axis is GeneralizationAxis.UNSEEN_DOMAIN else "dgc-frozen")
        for axis in GeneralizationAxis
    )
    with pytest.raises(ValueError):
        certify_generalization(rows)


def test_effect_direction_reversal_blocks_generalization():
    rows = tuple(
        _row(axis, cost=(axis is not GeneralizationAxis.UNSEEN_MODEL_PROVIDER))
        for axis in GeneralizationAxis
    )
    assert not certify_generalization(rows).supported
