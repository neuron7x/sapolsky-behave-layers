from __future__ import annotations

from pathlib import Path

from cwc.research_ops.provenance import freeze_local_source, sha256_file


def test_snapshot_only_source_is_quarantined(tmp_path: Path) -> None:
    src = tmp_path / "paper.txt"
    src.write_text("v1", encoding="utf-8")
    rec = freeze_local_source(
        source_path=src,
        raw_root=tmp_path / "raw",
        metadata={
            "source_id": "S",
            "canonical_title": "Paper",
            "publication_status": "PREPRINT",
            "version": "v1",
            "retrieved_at": "2026-08-10",
            "primary_source": True,
        },
        primary_source_bytes=False,
    )
    assert rec.gate_status == "QUARANTINED"
    assert sha256_file(Path(rec.raw_path)) == rec.content_sha256


def test_changed_bytes_create_revision_event(tmp_path: Path) -> None:
    src = tmp_path / "paper.txt"
    metadata = {
        "source_id": "S",
        "canonical_title": "Paper",
        "publication_status": "PREPRINT",
        "version": "v1",
        "retrieved_at": "2026-08-10",
        "primary_source": True,
    }
    src.write_text("first", encoding="utf-8")
    first = freeze_local_source(source_path=src, raw_root=tmp_path / "raw", metadata=metadata, primary_source_bytes=True)
    src.write_text("second", encoding="utf-8")
    second = freeze_local_source(source_path=src, raw_root=tmp_path / "raw", metadata=metadata, primary_source_bytes=True)
    assert first.gate_status == "SOURCE_VERIFIED"
    assert second.gate_status == "NEW_REVISION"
    assert second.revision_of == first.content_sha256
