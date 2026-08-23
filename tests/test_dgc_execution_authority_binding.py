import pytest

from cwc.governance.confirmatory_generation import (
    ConfirmatoryCompletionCertificate,
    ConfirmatoryGenerationRoot,
)
from cwc.governance.execution_authority_binding import promote_executed_from_confirmatory
from cwc.governance.external_source_authority import ExternalSourceAuthority, ExternalSourceStage


def source(stage=ExternalSourceStage.MATERIALIZED_VERIFIED):
    return ExternalSourceAuthority(
        family_id="FAM",
        stage=stage,
        upstream_revision="rev",
        upstream_identity_digest="a" * 64,
        source_verification_method="method",
        source_verification_evidence_digest="b" * 64,
        materialized_tree_sha256="c" * 64 if stage >= ExternalSourceStage.MATERIALIZED_VERIFIED else None,
        materialized_task_manifest_sha256="d" * 64 if stage >= ExternalSourceStage.MATERIALIZED_VERIFIED else None,
    )


def fixture():
    authority = source()
    root = ConfirmatoryGenerationRoot(
        generation_id="g",
        family_id="FAM",
        repo_commit_oid="a" * 40,
        repo_tree_oid="b" * 40,
        source_authority_digest=authority.digest,
        materialized_tree_sha256="c" * 64,
        task_manifest_sha256="d" * 64,
        comparison_frame_digest="e" * 64,
        baseline_panel_digest="f" * 64,
        statistical_plan_digest="1" * 64,
        trial_sizing_digest="2" * 64,
        distributed_spec_digest="3" * 64,
        policy_bindings=(),
        expected_work_units=8,
        root_digest="4" * 64,
    )
    completion = ConfirmatoryCompletionCertificate(
        generation_root_digest=root.root_digest,
        distributed_spec_digest=root.distributed_spec_digest,
        result_population_digest="5" * 64,
        audit_root_digest="6" * 64,
        expected_work_units=8,
        committed_work_units=8,
        total_cost_usd=1.0,
        execution_population_digest="7" * 64,
        complete=True,
    )
    return authority, root, completion


def test_promotes_exact_generation():
    authority, root, completion = fixture()
    promoted = promote_executed_from_confirmatory(authority, root=root, completion=completion)
    assert promoted.stage is ExternalSourceStage.EXECUTED
    assert promoted.execution_population_digest == "7" * 64


def test_family_mismatch_rejected():
    authority, root, completion = fixture()
    object.__setattr__(root, "family_id", "OTHER")
    with pytest.raises(ValueError, match="family"):
        promote_executed_from_confirmatory(authority, root=root, completion=completion)


def test_authority_digest_mismatch_rejected():
    authority, root, completion = fixture()
    object.__setattr__(root, "source_authority_digest", "9" * 64)
    with pytest.raises(ValueError, match="digest"):
        promote_executed_from_confirmatory(authority, root=root, completion=completion)


def test_foreign_or_incomplete_completion_rejected():
    authority, root, completion = fixture()
    object.__setattr__(completion, "generation_root_digest", "9" * 64)
    with pytest.raises(ValueError, match="different"):
        promote_executed_from_confirmatory(authority, root=root, completion=completion)

    authority, root, completion = fixture()
    object.__setattr__(completion, "complete", False)
    with pytest.raises(ValueError, match="complete"):
        promote_executed_from_confirmatory(authority, root=root, completion=completion)


def test_stage_skipping_rejected():
    authority = source(ExternalSourceStage.SOURCE_VERIFIED)
    _, root, completion = fixture()
    object.__setattr__(root, "source_authority_digest", authority.digest)
    with pytest.raises(ValueError, match="MATERIALIZED_VERIFIED"):
        promote_executed_from_confirmatory(authority, root=root, completion=completion)
