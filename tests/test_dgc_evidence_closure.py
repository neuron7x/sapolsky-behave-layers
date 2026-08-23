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
    with pytest.raises(ClosureError, match="missing evidence artifact"):
        ledger.advance(
            StageExecution(
                stage="SOURCE_VERIFIED",
                commands=(),
                evidence=(EvidenceArtifact("missing.json", "0" * 64),),
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
    for index, stage in enumerate(STAGES[:3]):
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
    assert state["completed_stages"] == list(STAGES[:3])
    assert state["product_qualified"] is False
    assert ledger.next_stage() == STAGES[3]


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
