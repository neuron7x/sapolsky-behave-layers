from __future__ import annotations

import json
from pathlib import Path

from scripts.technical_quality_gate import verify


def _fixture(tmp_path: Path) -> None:
    (tmp_path / "engineering").mkdir()
    (tmp_path / "docs/vnv").mkdir(parents=True)
    (tmp_path / "proof.txt").write_text("evidence", encoding="utf-8")
    rows = [
        f"| TQ-{number:03d} | {'DONE' if number == 1 else 'OPEN'} | Area | Test |"
        for number in range(1, 101)
    ]
    (tmp_path / "docs/vnv/TECHNICAL_QUALITY_100.md").write_text(
        "\n".join(rows), encoding="utf-8"
    )
    (tmp_path / "engineering/technical_quality_evidence.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ledger": "docs/vnv/TECHNICAL_QUALITY_100.md",
                "evidence": {"TQ-001": ["proof.txt"]},
            }
        ),
        encoding="utf-8",
    )


def test_repository_quality_ledger_is_consistent() -> None:
    assert verify() == []


def test_gate_rejects_missing_evidence(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "proof.txt").unlink()
    assert verify(tmp_path) == ["TQ-001 evidence is missing: 'proof.txt'"]


def test_gate_rejects_done_state_without_mapping(tmp_path: Path) -> None:
    _fixture(tmp_path)
    ledger = tmp_path / "docs/vnv/TECHNICAL_QUALITY_100.md"
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace(
            "| TQ-002 | OPEN |", "| TQ-002 | DONE |"
        ),
        encoding="utf-8",
    )
    assert "DONE/evidence mismatch" in verify(tmp_path)[0]


def test_gate_rejects_renumbered_or_missing_tasks(tmp_path: Path) -> None:
    _fixture(tmp_path)
    ledger = tmp_path / "docs/vnv/TECHNICAL_QUALITY_100.md"
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace("TQ-100", "TQ-999"),
        encoding="utf-8",
    )
    assert verify(tmp_path)[0] == "ledger IDs must be exactly TQ-001..TQ-100 in order"
