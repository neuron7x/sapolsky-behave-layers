from __future__ import annotations

import pytest

from cwc.governance.external_source_authority import (
    ExternalSourceAuthority,
    ExternalSourceStage,
    promote_executed,
    promote_materialized_verified,
    promote_source_verified,
)

H = "a" * 64
J = "b" * 64
K = "c" * 64
L = "d" * 64
M = "e" * 64


def identified():
    return ExternalSourceAuthority("bench", ExternalSourceStage.IDENTIFIED, "rev-1", H)


def test_source_verified_does_not_imply_materialized():
    s = promote_source_verified(
        identified(), verification_method="UPSTREAM_GIT_OBJECTS", verification_evidence_digest=J
    )
    assert s.stage is ExternalSourceStage.SOURCE_VERIFIED
    assert s.materialized_tree_sha256 is None
    assert s.execution_population_digest is None


def test_constructor_rejects_materialization_claim_at_source_verified_stage():
    with pytest.raises(ValueError, match="cannot imply local materialization"):
        ExternalSourceAuthority(
            "bench", ExternalSourceStage.SOURCE_VERIFIED, "rev", H, "method", J, K, L
        )


def test_cannot_skip_source_verification_before_materialization():
    with pytest.raises(ValueError, match="SOURCE_VERIFIED"):
        promote_materialized_verified(
            identified(), materialized_tree_sha256=K, materialized_task_manifest_sha256=L
        )


def test_execution_requires_materialized_stage():
    s = promote_source_verified(
        identified(), verification_method="UPSTREAM", verification_evidence_digest=J
    )
    with pytest.raises(ValueError, match="MATERIALIZED_VERIFIED"):
        promote_executed(s, execution_population_digest=M)


def test_full_monotone_promotion_chain_is_hash_bound():
    a = identified()
    b = promote_source_verified(a, verification_method="UPSTREAM", verification_evidence_digest=J)
    c = promote_materialized_verified(
        b, materialized_tree_sha256=K, materialized_task_manifest_sha256=L
    )
    d = promote_executed(c, execution_population_digest=M)
    assert [a.stage, b.stage, c.stage, d.stage] == list(ExternalSourceStage)
    assert len({a.digest, b.digest, c.digest, d.digest}) == 4


def test_invalid_hashes_fail_closed():
    with pytest.raises(ValueError, match="SHA-256"):
        ExternalSourceAuthority("bench", ExternalSourceStage.IDENTIFIED, "rev", "not-a-sha")


def test_direct_executed_construction_requires_all_prior_evidence():
    with pytest.raises(ValueError, match="source_verification_method"):
        ExternalSourceAuthority("bench", ExternalSourceStage.EXECUTED, "rev", H)
