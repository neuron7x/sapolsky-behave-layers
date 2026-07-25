from __future__ import annotations

import json
import os
from pathlib import Path

from cwc.evidence.intake import audit_tree, classify_path

ROOT = Path(__file__).resolve().parents[1]


def test_path_classification_is_conservative() -> None:
    assert classify_path("Особисті практики/note.md") == "restricted"
    assert classify_path("export/conversations.json") == "restricted"
    assert classify_path("project/node_modules/x.js") == "vendor"
    assert classify_path("project/dist-runtime/x.js") == "vendor"
    assert classify_path("05_ARCHIVE/data.zip") == "archive"
    assert classify_path("01_RESEARCH/result.json") == "candidate"


def test_audit_is_complete_deterministic_and_duplicate_aware(tmp_path: Path) -> None:
    (tmp_path / "research").mkdir()
    (tmp_path / "research/a.txt").write_bytes(b"evidence")
    (tmp_path / "research/b.txt").write_bytes(b"evidence")
    (tmp_path / "private").mkdir()
    (tmp_path / "private/note.txt").write_bytes(b"not exported")
    records: list[dict[str, object]] = []

    first = audit_tree(tmp_path, record=records.append)
    second = audit_tree(tmp_path)
    assert first == second
    assert first["complete"] is True
    assert first["file_count"] == first["hashed_file_count"] == 3
    assert first["duplicate_file_count"] == 1
    assert first["duplicate_reclaimable_bytes"] == len(b"evidence")
    assert first["category_file_count"] == {"candidate": 2, "restricted": 1}
    assert len(first["corpus_sha256"]) == 64
    assert len(records) == 3


def test_content_or_path_tamper_changes_corpus_root(tmp_path: Path) -> None:
    target = tmp_path / "evidence.json"
    target.write_text('{"value": 1}', encoding="utf-8")
    original = audit_tree(tmp_path)["corpus_sha256"]
    target.write_text('{"value": 2}', encoding="utf-8")
    changed_content = audit_tree(tmp_path)["corpus_sha256"]
    target.rename(tmp_path / "renamed.json")
    changed_path = audit_tree(tmp_path)["corpus_sha256"]
    assert len({original, changed_content, changed_path}) == 3


def test_symlinks_are_quarantined_and_never_followed(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    summary = audit_tree(tmp_path)
    assert summary["file_count"] == 0
    assert summary["byte_count"] == 0
    assert summary["symlink_count"] == 1


def test_hardlinks_are_duplicates_but_not_reclaimable_storage(tmp_path: Path) -> None:
    original = tmp_path / "original.bin"
    linked = tmp_path / "linked.bin"
    original.write_bytes(b"same inode")
    os.link(original, linked)
    summary = audit_tree(tmp_path)
    assert summary["duplicate_file_count"] == 1
    assert summary["duplicate_reclaimable_bytes"] == 0


def test_committed_data_baseline_is_complete_and_aggregate_only() -> None:
    baseline = json.loads(
        (ROOT / "engineering/data_corpus_baseline.json").read_text(encoding="utf-8")
    )
    assert baseline["complete"] is True
    assert baseline["file_count"] == baseline["hashed_file_count"]
    assert baseline["error_count"] == 0
    assert sum(baseline["category_file_count"].values()) == baseline["file_count"]
    assert sum(baseline["category_byte_count"].values()) == baseline["byte_count"]
    assert baseline["category_file_count"]["restricted"] > 0
    assert "paths" not in baseline
