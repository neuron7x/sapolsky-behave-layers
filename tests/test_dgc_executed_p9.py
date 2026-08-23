import pytest

from cwc.governance.baseline_panel import REQUIRED_BASELINES
from cwc.governance.executed_p9 import ExecutedPairedBaselineEvidence, certify_executed_p9
from cwc.governance.external_source_authority import ExternalSourceAuthority, ExternalSourceStage
from cwc.governance.pareto import PairedBaselineEvidence


def authority(stage=ExternalSourceStage.EXECUTED, execution_digest="a" * 64):
    return ExternalSourceAuthority(
        family_id="FAM",
        stage=stage,
        upstream_revision="rev",
        upstream_identity_digest="1" * 64,
        source_verification_method="method",
        source_verification_evidence_digest="2" * 64,
        materialized_tree_sha256="3" * 64 if stage >= ExternalSourceStage.MATERIALIZED_VERIFIED else None,
        materialized_task_manifest_sha256="4" * 64 if stage >= ExternalSourceStage.MATERIALIZED_VERIFIED else None,
        execution_population_digest=execution_digest if stage >= ExternalSourceStage.EXECUTED else None,
    )


def row(baseline_id, execution_digest="a" * 64, task_digest="b" * 64):
    evidence = PairedBaselineEvidence(
        baseline_id=baseline_id,
        paired_task_digest=task_digest,
        coverage=1.0,
        baseline_minus_dgc_cost=(2.0, 2.0, 2.0, 2.0),
        dgc_minus_baseline_quality=(0.0, 0.0, 0.0, 0.0),
        baseline_minus_dgc_catastrophic_regret=(0.0, 0.0, 0.0, 0.0),
        cost_gain_support=(-2.0, 2.0),
        quality_gain_support=(-1.0, 1.0),
        catastrophic_gain_support=(-1.0, 1.0),
    )
    return ExecutedPairedBaselineEvidence(execution_digest, evidence)


def rows():
    return [row(kind.value) for kind in REQUIRED_BASELINES]


def test_good_exact_b0_b3_population_is_bound():
    certificate = certify_executed_p9(
        authority(),
        rows(),
        alpha=0.05,
        quality_noninferiority_margin=1.0,
        catastrophic_noninferiority_margin=1.0,
    )
    assert certificate.execution_population_digest == "a" * 64
    assert len(certificate.evidence_population_digest) == 64
    assert len(certificate.certificate_digest) == 64


def test_nonexecuted_authority_rejected():
    with pytest.raises(ValueError, match="EXECUTED"):
        certify_executed_p9(authority(ExternalSourceStage.MATERIALIZED_VERIFIED, None), rows())


def test_foreign_execution_population_rejected():
    evidence = rows()
    evidence[0] = row(REQUIRED_BASELINES[0].value, execution_digest="c" * 64)
    with pytest.raises(ValueError, match="different execution"):
        certify_executed_p9(authority(), evidence)


def test_missing_baseline_rejected():
    with pytest.raises(ValueError, match="B0-B3"):
        certify_executed_p9(authority(), rows()[:-1])


def test_semantic_task_digest_rejected():
    with pytest.raises(ValueError, match="SHA-256"):
        row(REQUIRED_BASELINES[0].value, task_digest="tasks-v1")
