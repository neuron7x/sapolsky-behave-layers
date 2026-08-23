from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("rb") as f:
        os.fsync(f.fileno())


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def file_manifest(root: Path, *, excluded_names: frozenset[str] = frozenset()) -> tuple[tuple[str, int, str], ...]:
    rows: list[tuple[str, int, str]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel in excluded_names:
            continue
        rows.append((rel, path.stat().st_size, sha256_file(path)))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class PublishedEvidenceGeneration:
    root: Path
    payload_manifest_sha256: str
    publication_manifest_sha256: str
    file_count: int


class AtomicEvidenceGeneration:
    """Fail-closed same-filesystem transaction for evidence materialization.

    The final path is never populated incrementally. Callers write only beneath
    ``staging_root`` and may publish exactly once. On any exception or an exit
    without ``publish()``, staging bytes are deleted and the final path remains
    absent.
    """

    RECEIPT_NAME = "MATERIALIZATION_RECEIPT.json"
    PROVENANCE_NAME = "MATERIALIZATION_PROVENANCE.json"
    MANIFEST_NAME = "GENERATION_MANIFEST.json"
    _CONTROL_FILES = frozenset({RECEIPT_NAME, PROVENANCE_NAME, MANIFEST_NAME})

    def __init__(self, final_root: Path) -> None:
        self.final_root = Path(final_root).resolve()
        self.staging_root: Path | None = None
        self._published = False

    def __enter__(self) -> "AtomicEvidenceGeneration":
        if self.final_root.exists():
            raise FileExistsError("final evidence root must not exist")
        parent = self.final_root.parent
        parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{self.final_root.name}.staging-", dir=parent))
        self.staging_root = staging
        return self

    def _require_open(self) -> Path:
        if self.staging_root is None:
            raise RuntimeError("evidence transaction is not open")
        if self._published:
            raise RuntimeError("evidence generation already published")
        return self.staging_root

    def publish(
        self,
        *,
        receipt: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> PublishedEvidenceGeneration:
        root = self._require_open()
        for control_name in self._CONTROL_FILES:
            if (root / control_name).exists():
                raise ValueError(f"reserved control file already exists: {control_name}")

        payload_rows = file_manifest(root, excluded_names=self._CONTROL_FILES)
        payload_digest = sha256_bytes(canonical_json_bytes(payload_rows))

        receipt_payload = dict(receipt)
        receipt_payload["payload_manifest_sha256"] = payload_digest
        receipt_path = root / self.RECEIPT_NAME
        receipt_path.write_bytes(json.dumps(receipt_payload, indent=2, sort_keys=True).encode("utf-8") + b"\n")

        provenance_payload = dict(provenance)
        provenance_payload["payload_manifest_sha256"] = payload_digest
        provenance_path = root / self.PROVENANCE_NAME
        provenance_path.write_bytes(json.dumps(provenance_payload, indent=2, sort_keys=True).encode("utf-8") + b"\n")

        publication_rows = file_manifest(root, excluded_names=frozenset({self.MANIFEST_NAME}))
        publication_digest = sha256_bytes(canonical_json_bytes(publication_rows))
        manifest_payload = {
            "schema": "DGC_EVIDENCE_GENERATION_MANIFEST_V1",
            "payload_manifest_sha256": payload_digest,
            "publication_manifest_sha256": publication_digest,
            "files": [
                {"path": path, "bytes": size, "sha256": digest}
                for path, size, digest in publication_rows
            ],
        }
        manifest_path = root / self.MANIFEST_NAME
        manifest_path.write_bytes(json.dumps(manifest_payload, indent=2, sort_keys=True).encode("utf-8") + b"\n")

        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            _fsync_file(path)
        for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
            _fsync_dir(path)
        _fsync_dir(root)

        # Same-parent staging guarantees os.replace remains on one filesystem.
        # No fallible filesystem operation occurs after rename: if replace fails,
        # __exit__ removes staging and the final root remains absent.
        _fsync_dir(self.final_root.parent)
        os.replace(root, self.final_root)
        self._published = True
        self.staging_root = None
        return PublishedEvidenceGeneration(
            root=self.final_root,
            payload_manifest_sha256=payload_digest,
            publication_manifest_sha256=publication_digest,
            file_count=len(publication_rows),
        )

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self.staging_root is not None:
            shutil.rmtree(self.staging_root, ignore_errors=True)
            self.staging_root = None
        return False
