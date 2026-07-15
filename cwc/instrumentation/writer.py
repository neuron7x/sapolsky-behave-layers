"""Buffered, crash-safe, machine-readable output (Act 4.11).

- metrics.jsonl: append-only, buffered (flush on buffer-size or explicit
  flush/close), never fsync'd per record.
- summary.json / overhead_report.json: written to a temp file then
  os.replace()'d into place — atomic, so a crash mid-write cannot leave a
  half-written summary behind.
- No pickle anywhere. UTF-8. allow_nan=False (a NaN/Infinity in a metric is a
  measurement bug, not a value to silently serialize).
- SHA256SUMS is computed last, after every other file in the run directory is
  closed, so it is a checksum over final content, not content still being
  written.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class InstrumentationWriter:
    def __init__(self, output_dir: Path, *, buffer_size: int = 100) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[dict[str, Any]] = []
        self._buffer_size = buffer_size
        self._metrics_path = output_dir / "metrics.jsonl"
        self._closed = False

    def write_metric(self, record: dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("cannot write_metric after close()")
        self._buffer.append(record)
        if len(self._buffer) >= self._buffer_size:
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            for record in self._buffer:
                handle.write(json.dumps(record, allow_nan=False, sort_keys=True, ensure_ascii=False) + "\n")
        self._buffer.clear()

    def flush(self) -> None:
        self._flush_buffer()

    def _write_json_atomic(self, filename: str, payload: dict[str, Any]) -> Path:
        final_path = self.output_dir / filename
        tmp_path = self.output_dir / f".{filename}.tmp"
        tmp_path.write_text(
            json.dumps(payload, allow_nan=False, sort_keys=True, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp_path.replace(final_path)
        return final_path

    def write_summary(self, summary: dict[str, Any]) -> Path:
        self._flush_buffer()
        return self._write_json_atomic("summary.json", summary)

    def write_overhead_report(self, report: dict[str, Any]) -> Path:
        return self._write_json_atomic("overhead_report.json", report)

    def write_manifest(self, manifest: dict[str, Any]) -> Path:
        return self._write_json_atomic("manifest.json", manifest)

    def write_resolved_config(self, config: dict[str, Any]) -> Path:
        return self._write_json_atomic("config.resolved.json", config)

    def write_energy_raw(self, samples: list[dict[str, Any]]) -> Path:
        path = self.output_dir / "energy.raw.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for sample in samples:
                handle.write(json.dumps(sample, allow_nan=False, sort_keys=True, ensure_ascii=False) + "\n")
        return path

    def close(self) -> None:
        if self._closed:
            return
        self._flush_buffer()
        self._closed = True

    def compute_checksums(self) -> Path:
        """Must be called only after close() and after every other write_*
        call for this run — it hashes final file content in self.output_dir.
        """
        checksums: list[str] = []
        for path in sorted(self.output_dir.rglob("*")):
            if path.is_dir() or path.name == "SHA256SUMS":
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            relative = path.relative_to(self.output_dir)
            checksums.append(f"{digest}  {relative}")
        sums_path = self.output_dir / "SHA256SUMS"
        sums_path.write_text("\n".join(checksums) + ("\n" if checksums else ""), encoding="utf-8")
        return sums_path
