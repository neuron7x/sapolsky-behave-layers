from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .models import PublicationStatus, SourceGateStatus


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(encoded)


@dataclass(frozen=True, slots=True)
class FrozenSource:
    source_id: str
    canonical_title: str
    publication_status: PublicationStatus
    version: str
    primary_source: bool
    primary_source_bytes: bool
    content_sha256: str
    metadata_sha256: str
    raw_path: str
    retrieved_at: str
    gate_status: SourceGateStatus
    revision_of: str | None
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def freeze_local_source(
    *,
    source_path: Path,
    raw_root: Path,
    metadata: dict[str, Any],
    primary_source_bytes: bool,
    path_base: Path | None = None,
) -> FrozenSource:
    """Freeze bytes without silent overwrite and emit a strict source gate status."""
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    required = ("source_id", "canonical_title", "publication_status", "version", "retrieved_at")
    missing = [key for key in required if not metadata.get(key)]
    if missing:
        raise ValueError(f"source metadata missing: {', '.join(missing)}")

    source_id = str(metadata["source_id"])
    content_hash = sha256_file(source_path)
    metadata_payload = dict(metadata)
    metadata_payload["primary_source_bytes"] = primary_source_bytes
    metadata_hash = stable_json_sha256(metadata_payload)

    target_dir = raw_root / source_id
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix or ".bin"
    target = target_dir / f"{content_hash}{suffix}"
    if not target.exists():
        shutil.copyfile(source_path, target)

    pointer = target_dir / "CURRENT.json"
    previous: dict[str, Any] | None = None
    if pointer.exists():
        previous = json.loads(pointer.read_text(encoding="utf-8"))

    revision_of = None
    gate_status: SourceGateStatus
    if previous and previous.get("content_sha256") != content_hash:
        gate_status = "NEW_REVISION"
        revision_of = str(previous.get("content_sha256"))
    elif bool(metadata.get("primary_source")) and primary_source_bytes:
        gate_status = "SOURCE_VERIFIED"
    else:
        gate_status = "QUARANTINED"

    boundary = (
        "Primary-source bytes hashed and versioned."
        if gate_status == "SOURCE_VERIFIED"
        else "Local bytes are immutable but are not verified full primary-source bytes; paper-level reproduction authority is withheld."
    )
    stored_path = target
    if path_base is not None:
        try:
            stored_path = target.relative_to(path_base)
        except ValueError:
            stored_path = target

    record = FrozenSource(
        source_id=source_id,
        canonical_title=str(metadata["canonical_title"]),
        publication_status=str(metadata["publication_status"]),  # type: ignore[arg-type]
        version=str(metadata["version"]),
        primary_source=bool(metadata.get("primary_source")),
        primary_source_bytes=primary_source_bytes,
        content_sha256=content_hash,
        metadata_sha256=metadata_hash,
        raw_path=str(stored_path),
        retrieved_at=str(metadata["retrieved_at"]),
        gate_status=gate_status,
        revision_of=revision_of,
        boundary=boundary,
    )
    pointer.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record
