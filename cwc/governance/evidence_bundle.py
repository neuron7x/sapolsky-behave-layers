from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


REQUIRED_PRODUCT_EVIDENCE_FILES = (
    "PREREGISTRATION.md",
    "CLAIM_BOUNDARY.md",
    "BASELINES.md",
    "environment.lock",
    "task_manifest.json",
    "model_manifest.json",
    "raw_results.jsonl",
    "aggregate_results.json",
    "statistical_report.json",
    "economics.json",
    "faults.json",
    "independent_replication.json",
    "PRODUCT_VERDICT.md",
    "SHA256SUMS",
)


@dataclass(frozen=True, slots=True)
class EvidenceBundleVerification:
    complete: bool
    missing_files: tuple[str, ...]
    hash_mismatches: tuple[str, ...]
    unhashed_files: tuple[str, ...]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_evidence_bundle(root: Path) -> EvidenceBundleVerification:
    missing = tuple(name for name in REQUIRED_PRODUCT_EVIDENCE_FILES if not (root / name).is_file())
    if "SHA256SUMS" in missing:
        return EvidenceBundleVerification(False, missing, (), ())

    declared: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            return EvidenceBundleVerification(False, missing, ("MALFORMED_SHA256SUMS",), ())
        digest, name = parts[0].strip(), parts[1].lstrip("* ").strip()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()) or not name:
            return EvidenceBundleVerification(False, missing, ("MALFORMED_SHA256SUMS",), ())
        if name == "SHA256SUMS":
            continue
        declared[name] = digest.lower()

    required_payload = [name for name in REQUIRED_PRODUCT_EVIDENCE_FILES if name != "SHA256SUMS"]
    unhashed = tuple(name for name in required_payload if name not in declared and (root / name).is_file())
    mismatches: list[str] = []
    for name, expected in declared.items():
        path = root / name
        if not path.is_file() or _sha256(path) != expected:
            mismatches.append(name)
    complete = not missing and not mismatches and not unhashed
    return EvidenceBundleVerification(complete, missing, tuple(sorted(mismatches)), unhashed)
