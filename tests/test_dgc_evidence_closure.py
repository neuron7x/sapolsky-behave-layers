from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from cwc.governance.evidence_closure import (
    ClosureError,
    EvidenceArtifact,
    EvidenceClosureLedger,
    STAGES,
    StageExecution,
)

COMMIT = "1" * 40
TREE = "2" * 40


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ledger(tmp_path: Path) -> EvidenceClosureLedger:
    return EvidenceClosureLedger(
        repository_root=tmp_path,
        ledger_path=tmp_path / "ledger.json",
        generation_id="gen-001",
        repo_commit=COMMIT,
        repo_tree=TREE,
    )


def _ok_runner(argv, cwd, env):
    return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")


def test_stage_topology_freezes_fault_matrix_pre_b2_and_requires_fault_support_pre_replication() -> None:
    assert STAGES == (
        "SOURCE_VERIFIED",
        "MATERIALIZED_VERIFIED",
        "EXECUTION_MANIFESTS_FROZEN",
        "CCF_SPEC_FROZEN",
        "GENERALIZATION_REGISTRY_FROZEN",
        "FAULT_INJECTION_SPEC_FROZEN",
        "B2_FITTED",
        "HARNESS_FROZEN",
        "TRIAL_SIZED",
        "GENERATION_ROOT_FROZEN",
        "CONFIRMATORY_EXECUTED",
        "P9_SUPPORTED",
        "GENERALIZATION_SUPPORTED",
        "FAULT_TOLERANCE_SUPPORTED",
        "INDEPENDENT_REPLICATION_SUPPORTED",
        "P19_SEALED",
        "PRODUCT_QUALIFIED",
    )


def test_stage_skip_is_rejected(tmp_path: Path) -> None:
    evidence = tmp_path / "e.json"
    evidence.write_text("{}")
    ledger = _ledger(tmp_path)
    with pytest.raises(ClosureError, match="stage skip rejected"):
        ledger.advance(
            StageExecution(
                stage="MATERIALIZED_VERIFIED",
                commands=(),
                evidence=(EvidenceArtifact("e.json", _digest(evidence)),),
            ),
            runner=_ok_runner,
        )


def test_unbound_or_missing_evidence_fails_closed(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(ClosureError, match="missing regular evidence artifact"):
        ledger.advance(
            StageExecution(
                stage="SOURCE_VERIFIED",
                commands=(),
                evidence=(EvidenceArtifact("missing.json", "0" * 64),),
            ),
            runner=_ok_runner,
        )


def test_symlink_evidence_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("source")
    link = tmp_path / "source-link.json"
    link.symlink_to(target)
    ledger = _ledger(tmp_path)
    with pytest.raises(ClosureError, match="missing regular evidence artifact"):
        ledger.advance(
            StageExecution(
                stage="SOURCE_VERIFIED",
                commands=(),
                evidence=(EvidenceArtifact("source-link.json", _digest(target)),),
            ),
            runner=_ok_runner,
        )


def test_command_failure_does_not_advance(tmp_path: Path) -> None:
    evidence = tmp_path / "source.json"
    evidence.write_text("source")
    ledger = _ledger(tmp_path)

    def failed(argv, cwd, env):
        return subprocess.CompletedProcess(argv, 17, stdout="", stderr="boom")

    with pytest.raises(ClosureError, match="stage command failed"):
        ledger.advance(
            StageExecution(
                stage="SOURCE_VERIFIED",
                commands=(("python", "gate.py"),),
                evidence=(EvidenceArtifact("source.json", _digest(evidence)),),
            ),
            runner=failed,
        )
    assert ledger.next_stage() == "SOURCE_VERIFIED"
    assert not (tmp_path / "ledger.json").exists()


def test_digest_bound_ordered_receipt_chain(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for index, stage in enumerate(STAGES[:7]):
        path = tmp_path / f"e{index}.json"
        path.write_text(json.dumps({"stage": stage}))
        receipt = ledger.advance(
            StageExecution(
                stage=stage,
                commands=(("gate", stage),),
                evidence=(EvidenceArtifact(path.name, _digest(path)),),
            ),
            runner=_ok_runner,
        )
        assert receipt["stage"] == stage
    state = ledger.load()
    assert state["completed_stages"] == list(STAGES[:7])
    assert state["product_qualified"] is False
    assert ledger.next_stage() == STAGES[7]


def test_tampering_is_detected(tmp_path: Path) -> None:
    evidence = tmp_path / "source.json"
    evidence.write_text("source")
    ledger = _ledger(tmp_path)
    ledger.advance(
        StageExecution(
            stage="SOURCE_VERIFIED",
            commands=(),
            evidence=(EvidenceArtifact("source.json", _digest(evidence)),),
        ),
        runner=_ok_runner,
    )
    state = json.loads((tmp_path / "ledger.json").read_text())
    state["receipts"][0]["stage"] = "MATERIALIZED_VERIFIED"
    (tmp_path / "ledger.json").write_text(json.dumps(state))
    with pytest.raises(ClosureError):
        ledger.load()


def test_generation_id_path_traversal_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ClosureError, match="safe 1-128 character slug"):
        EvidenceClosureLedger(
            repository_root=tmp_path,
            ledger_path=tmp_path / "ledger.json",
            generation_id="../escape",
            repo_commit=COMMIT,
            repo_tree=TREE,
        )