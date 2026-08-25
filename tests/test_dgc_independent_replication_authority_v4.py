from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import cwc.governance.independent_replication_authority_v4 as mod
from cwc.governance.independent_replication_authority_v4 import (
    IndependentReplicationAuthorityV4Error,
    build_independent_replication_authority_v4,
    theorem_identity_digest,
    verify_independent_replication_authority_v4_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes


@dataclass(frozen=True)
class FakeV3:
    authority_digest: str = "1" * 64
    replication_package_digest: str = "2" * 64
    primary_p9_scientific_authority_digest: str = "3" * 64
    primary_anytime_p9_authority_digest: str = "4" * 64
    primary_generalization_authority_digest: str = "5" * 64
    replica_p9_scientific_authority_digest: str = "6" * 64
    replica_anytime_p9_authority_digest: str = "7" * 64
    statistical_plan_digest: str = "8" * 64
    methodology_identity_matched: bool = True
    fresh_execution_verified: bool = True
    replica_exact_panel_supported: bool = True
    replica_anytime_average_conditional_mean_supported: bool = True
    replica_scientific_p9_supported: bool = True
    signed_independence_attested: bool = True
    social_independence_machine_proven: bool = False
    independent_replication_supported: bool = True


def _build(monkeypatch) -> object:
    monkeypatch.setattr(mod, "build_independent_replication_authority_v3", lambda **kwargs: FakeV3())
    return build_independent_replication_authority_v4(
        primary_p9_scientific_authority_path=Path("p"),
        primary_anytime_p9_authority_path=Path("a"),
        primary_ccf_oracle_audit_authority_path=Path("c"),
        primary_generalization_authority_path=Path("g"),
        replica_p9_scientific_authority_path=Path("rp"),
        replica_anytime_p9_authority_path=Path("ra"),
        replica_ccf_oracle_audit_authority_path=Path("rc"),
        replica_execution_authority_path=Path("re"),
        replica_execution_bundle_root=Path("reb"),
        replica_physical_cost_bundle_root=Path("rpc"),
        replica_confirmatory_root_authority_path=Path("rr"),
        harness_freeze_path=Path("h"),
        execution_manifest_freeze_path=Path("ef"),
        materialization_reference_path=Path("mr"),
        source_registry_path=Path("sr"),
        ccf_spec_authority_path=Path("cs"),
        replica_ccf_evidence_bundle_root=Path("rce"),
        repository_root=Path("."),
        attestation_path=Path("att"),
        signature_path=Path("sig"),
        allowed_signers_path=Path("allow"),
    )


def _write(tmp_path: Path, doc: dict[str, object]) -> Path:
    path = tmp_path / "replication-v4.json"
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return path


def _redigest(doc: dict[str, object]) -> None:
    keys = (
        "replication_scope", "v3_raw_replication_authority_digest", "replication_package_digest",
        "primary_p9_scientific_authority_digest", "primary_anytime_p9_authority_digest",
        "primary_generalization_authority_digest", "replica_p9_scientific_authority_digest",
        "replica_anytime_p9_authority_digest", "statistical_plan_digest", "theorem_identity_digest",
        "methodology_identity_matched", "fresh_execution_verified", "replica_exact_panel_supported",
        "replica_anytime_average_conditional_mean_supported", "replica_scientific_p9_supported",
        "signed_independence_attested", "social_independence_machine_proven", "independent_replication_supported",
    )
    doc["authority_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in keys}))


def test_v4_wraps_fresh_signed_replication_with_current_v5_theorem(monkeypatch, tmp_path: Path):
    authority = _build(monkeypatch)
    assert authority.theorem_identity_digest == theorem_identity_digest()
    assert authority.independent_replication_supported is True
    verified = verify_independent_replication_authority_v4_document(_write(tmp_path, authority.document))
    assert verified["theorem_identity_digest"] == theorem_identity_digest()


def test_recomputed_self_consistent_theorem_substitution_is_rejected(monkeypatch, tmp_path: Path):
    authority = _build(monkeypatch)
    doc = authority.document
    doc["theorem_identity_digest"] = "9" * 64
    _redigest(doc)
    with pytest.raises(IndependentReplicationAuthorityV4Error, match="current V5"):
        verify_independent_replication_authority_v4_document(_write(tmp_path, doc))


def test_social_independence_may_not_be_machine_claimed(monkeypatch, tmp_path: Path):
    authority = _build(monkeypatch)
    doc = authority.document
    doc["social_independence_machine_proven"] = True
    doc["independent_replication_supported"] = True
    _redigest(doc)
    with pytest.raises(IndependentReplicationAuthorityV4Error, match="not derived"):
        verify_independent_replication_authority_v4_document(_write(tmp_path, doc))
