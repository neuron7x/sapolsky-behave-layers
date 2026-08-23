from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.evidence_closure import (
    ClosureError,
    EvidenceArtifact,
    EvidenceClosureLedger,
    StageExecution,
    sha256_file,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.qualification_closure import close_execution_manifests_frozen

COMMIT = "a" * 40
TREE = "b" * 40


def _ledger(repo: Path) -> tuple[EvidenceClosureLedger, Path, str]:
    ledger = EvidenceClosureLedger(
        repository_root=repo,
        ledger_path=repo / "eval_bundle" / "ledger.json",
        generation_id="g1",
        repo_commit=COMMIT,
        repo_tree=TREE,
    )
    source = repo / "source.json"
    source.write_text("source", encoding="utf-8")
    ledger.advance(StageExecution(
        stage="SOURCE_VERIFIED", commands=(),
        evidence=(EvidenceArtifact("source.json", sha256_file(source)),),
    ))
    reference_payload = {
        "schema": "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2",
        "repository_commit": COMMIT,
        "repository_tree": TREE,
    }
    reference_digest = sha256_bytes(canonical_json_bytes(reference_payload))
    reference = repo / "eval_bundle" / "materialization-reference.json"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_text(json.dumps({**reference_payload, "reference_digest": reference_digest}), encoding="utf-8")
    ledger.advance(StageExecution(
        stage="MATERIALIZED_VERIFIED", commands=(),
        evidence=(EvidenceArtifact("eval_bundle/materialization-reference.json", sha256_file(reference)),),
    ))
    return ledger, reference, reference_digest


def _freeze(repo: Path, reference_digest: str, *, reference_path: str = "eval_bundle/materialization-reference.json") -> Path:
    payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "repository_commit": COMMIT,
        "repository_tree": TREE,
        "materialization_reference_path": reference_path,
        "materialization_reference_digest": reference_digest,
        "materialized_tree_sha256": "1" * 64,
        "task_manifest_digest": "2" * 64,
        "statistical_plan_digest": "3" * 64,
        "statistical_plan": {},
        "components": [],
        "governance_policies": [],
        "prebaseline_comparison_digest": "4" * 64,
    }
    doc = {
        "schema": "DGC_EXECUTION_MANIFEST_FREEZE_V1",
        **payload,
        "freeze_digest": sha256_bytes(canonical_json_bytes(payload)),
        "baseline_panel_bound": False,
        "harness_frozen": False,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    }
    path = repo / "eval_bundle" / "execution-freeze.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_execution_manifest_freeze_advances_only_from_exact_materialization_subject(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger, _, reference_digest = _ledger(repo)
    receipt = close_execution_manifests_frozen(
        ledger,
        freeze_path=_freeze(repo, reference_digest),
        identity_checker=lambda _: None,
    )
    assert receipt["stage"] == "EXECUTION_MANIFESTS_FROZEN"
    assert ledger.next_stage() == "B2_FITTED"


def test_execution_freeze_cannot_rebind_to_another_materialization_reference(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger, _, reference_digest = _ledger(repo)
    with pytest.raises(ClosureError, match="different materialization subject"):
        close_execution_manifests_frozen(
            ledger,
            freeze_path=_freeze(repo, reference_digest, reference_path="eval_bundle/other.json"),
            identity_checker=lambda _: None,
        )
    assert ledger.next_stage() == "EXECUTION_MANIFESTS_FROZEN"


def test_prior_materialization_reference_tamper_blocks_next_stage(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger, reference, reference_digest = _ledger(repo)
    reference.write_text("tampered", encoding="utf-8")
    with pytest.raises(ClosureError, match="prior materialization reference"):
        close_execution_manifests_frozen(
            ledger,
            freeze_path=_freeze(repo, reference_digest),
            identity_checker=lambda _: None,
        )
    assert ledger.next_stage() == "EXECUTION_MANIFESTS_FROZEN"
