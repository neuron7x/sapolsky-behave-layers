"""python -m pytest tests/test_instrumentation_writer.py -v"""

import contextlib
import json
import math
from pathlib import Path

import pytest

from cwc.instrumentation.writer import InstrumentationWriter


def test_metrics_are_buffered_not_written_immediately(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path, buffer_size=10)
    writer.write_metric({"step": 0})
    metrics_path = tmp_path / "metrics.jsonl"
    assert not metrics_path.exists() or metrics_path.read_text() == ""


def test_metrics_flush_on_buffer_size(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path, buffer_size=2)
    writer.write_metric({"step": 0})
    writer.write_metric({"step": 1})  # triggers flush
    metrics_path = tmp_path / "metrics.jsonl"
    lines = metrics_path.read_text().splitlines()
    assert len(lines) == 2


def test_close_flushes_remaining_buffer(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path, buffer_size=100)
    writer.write_metric({"step": 0})
    writer.close()
    lines = (tmp_path / "metrics.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"step": 0}


def test_writing_after_close_raises(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.close()
    with pytest.raises(RuntimeError):
        writer.write_metric({"step": 0})


def test_summary_is_valid_json_and_atomic(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    path = writer.write_summary({"schema_version": "1.0.0"})
    assert path.exists()
    assert not (tmp_path / ".summary.json.tmp").exists()
    data = json.loads(path.read_text())
    assert data["schema_version"] == "1.0.0"


def test_allow_nan_false_rejects_nan(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    with pytest.raises(ValueError):
        writer.write_summary({"value": math.nan})


def test_allow_nan_false_rejects_infinity(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    with pytest.raises(ValueError):
        writer.write_summary({"value": math.inf})


def test_no_pickle_import_in_writer_module():
    import cwc.instrumentation.writer as writer_module

    source = Path(writer_module.__file__).read_text(encoding="utf-8")
    assert "import pickle" not in source


def test_output_is_utf8(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.write_metric({"note": "юнікод перевірка"})
    writer.close()
    text = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8")
    assert "юнікод перевірка" in text


def test_compute_checksums_covers_all_written_files(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.write_metric({"step": 0})
    writer.write_summary({"ok": True})
    writer.close()
    sums_path = writer.compute_checksums()
    content = sums_path.read_text()
    assert "metrics.jsonl" in content
    assert "summary.json" in content
    assert "SHA256SUMS" not in content  # never hashes itself


def test_crash_between_writes_does_not_corrupt_prior_summary(tmp_path: Path):
    writer = InstrumentationWriter(tmp_path)
    writer.write_summary({"version": 1})
    first_content = (tmp_path / "summary.json").read_text()
    with contextlib.suppress(ValueError):
        writer.write_summary({"value": math.nan})  # simulated "crash" mid-write
    # the previously-written summary.json must be untouched, not half-written
    assert (tmp_path / "summary.json").read_text() == first_content
