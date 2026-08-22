import pytest

from cwc.governance.independent_replication import (
    IndependentReplicationResult,
    ReplicationPackage,
    certify_independent_replication,
)


def _package() -> ReplicationPackage:
    return ReplicationPackage(
        repo_commit="commit",
        environment_digest="env",
        preregistration_digest="prereg",
        task_manifest_digest="tasks",
        model_manifest_digest="models",
        scorer_digest="scorer",
        policy_digest="policy",
        baseline_panel_digest="baselines",
        statistical_plan_digest="stats",
    )


def _result(package: ReplicationPackage, **overrides) -> IndependentReplicationResult:
    data = dict(
        package_digest=package.digest,
        replicator_identity_digest="external-org",
        replicator_attestation_digest="attestation",
        raw_result_digest="raw",
        statistical_report_digest="report",
        methodology_unchanged=True,
        quality_concordant=True,
        cost_direction_concordant=True,
        regret_concordant=True,
        independent_from_author=True,
    )
    data.update(overrides)
    return IndependentReplicationResult(**data)


def test_package_digest_is_deterministic():
    assert _package().digest == _package().digest
    assert len(_package().digest) == 64


def test_concordant_independent_replay_passes():
    package = _package()
    assert certify_independent_replication(package, _result(package)) == "report"


def test_self_replication_does_not_satisfy_independent_gate():
    package = _package()
    with pytest.raises(ValueError):
        certify_independent_replication(package, _result(package, independent_from_author=False))


def test_methodology_change_requires_new_generation():
    package = _package()
    with pytest.raises(ValueError):
        certify_independent_replication(package, _result(package, methodology_unchanged=False))


def test_nonconcordant_effect_fails():
    package = _package()
    with pytest.raises(RuntimeError):
        certify_independent_replication(package, _result(package, cost_direction_concordant=False))


def test_result_for_different_package_fails():
    package = _package()
    result = _result(package, package_digest="different")
    with pytest.raises(ValueError):
        certify_independent_replication(package, result)
