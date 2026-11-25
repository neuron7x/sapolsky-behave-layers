"""Bounded acquisition of the three frozen REAL-TRANSFER-01 source files.

Receipts record this process's observed UTC clock, not an authenticated external
witness. Revalidation checks chronology and bytes; it cannot detect an otherwise
plausible forged timestamp. No model execution or source-manifest admission.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.parse import urlsplit

from experiments.cwc_collision import audit
from experiments.real_transfer_01 import source_intake as intake

SCHEMA = "cwc-source-acquisition-v1"
OBSERVATION = "SELF_OBSERVED_NOT_AUTHENTICATED"
STATUS = "PINNED_SOURCE_BYTES_ACQUIRED"
CONNECT_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 240
PINS = {
    "averitec_dev.json": {
        "byte_length": 1785475, "sha256": audit.AV_SHA, "git_blob": intake.AV_BLOB,
    },
    "hybridqa_dev.json": {
        "byte_length": 1193503, "sha256": intake.HQ_SHA256, "git_blob": intake.HQ_BLOB,
    },
    "wikitable_links.zip": {
        "byte_length": 193533209, "sha256": intake.WIKI_SHA256, "git_blob": None,
    },
}
TIME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", re.ASCII)


class AcquisitionError(ValueError):
    """A bounded acquisition or custody failure; never a scientific negative."""


def require(condition, code):
    if not condition:
        raise AcquisitionError(code)


def _utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _time(value):
    require(type(value) is str and TIME_PATTERN.fullmatch(value) is not None, "UTC_TIME_SCHEMA")
    try:
        return datetime.fromisoformat(value[:-1]+"+00:00")
    except ValueError as exc:
        raise AcquisitionError("INVALID_UTC_TIME") from exc


def _safe_path(path):
    path = Path(path)
    require(".." not in path.parts, "PATH_TRAVERSAL")
    path = path.absolute()
    require(all(not part.is_symlink() for part in (path, *path.parents)), "SYMLINK_PATH")
    return path


def _exclusive_file(path):
    path = _safe_path(path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        raise AcquisitionError("OUTPUT_EXISTS_OR_UNAVAILABLE") from exc
    return os.fdopen(fd, "wb")


def _require_https(url):
    require(type(url) is str and not any(ord(c) < 33 or ord(c) == 127 for c in url),
            "HTTPS_URL_SCHEMA")
    try:
        parts = urlsplit(url)
        require(parts.scheme == "https" and bool(parts.hostname) and
                parts.username is None and parts.password is None and
                parts.port in (None, 443) and not parts.fragment, "HTTPS_URL_REQUIRED")
    except ValueError as exc:
        raise AcquisitionError("HTTPS_URL_SCHEMA") from exc


def _download(url, path, limit):
    _require_https(url)
    require(type(limit) is int and limit > 0, "DOWNLOAD_LIMIT_SCHEMA")
    command = [
        "curl", "--disable", "--proto", "=https", "--proto-redir", "=https",
        "--location", "--max-redirs", "5", "--connect-timeout", str(CONNECT_TIMEOUT),
        "--max-time", str(DOWNLOAD_TIMEOUT), "--max-filesize", str(limit),
        "--fail", "--silent", "--show-error", "--url", url,
    ]
    with _exclusive_file(path) as out:
        try:
            result = subprocess.run(command, stdout=out, stderr=subprocess.PIPE,
                                    timeout=DOWNLOAD_TIMEOUT+10, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AcquisitionError("BOUNDED_HTTPS_ACQUISITION_FAILED") from exc
        require(result.returncode == 0, "BOUNDED_HTTPS_ACQUISITION_FAILED")
        out.flush()
        os.fsync(out.fileno())
        require(0 < os.fstat(out.fileno()).st_size <= limit, "DOWNLOAD_BYTE_BUDGET")


def _metadata(path, name, limit):
    path = _safe_path(path)
    try:
        require(stat.S_ISREG(path.stat(follow_symlinks=False).st_mode), "SOURCE_NOT_REGULAR")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "SOURCE_NOT_REGULAR")
            require(0 < before.st_size <= limit, "SOURCE_BYTE_BUDGET")
            sha = hashlib.sha256()
            blob = hashlib.sha1(b"blob "+str(before.st_size).encode("ascii")+b"\0",
                                usedforsecurity=False)
            count = 0
            for block in iter(lambda: handle.read(1024*1024), b""):
                count += len(block)
                require(count <= limit, "SOURCE_BYTE_BUDGET")
                sha.update(block)
                blob.update(block)
            after = os.fstat(handle.fileno())
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        require(count == before.st_size and
                all(getattr(before, field) == getattr(after, field) for field in fields),
                "SOURCE_CHANGED_DURING_READ")
        final = path.stat(follow_symlinks=False)
        require(final.st_dev == before.st_dev and final.st_ino == before.st_ino and
                stat.S_ISREG(final.st_mode), "SOURCE_REPLACED_DURING_READ")
    except OSError as exc:
        raise AcquisitionError("SOURCE_UNAVAILABLE") from exc
    pin = PINS[name]
    meta = {"byte_length": count, "sha256": sha.hexdigest(),
            "git_blob": blob.hexdigest() if pin["git_blob"] is not None else None}
    require(meta == pin, "PINNED_SOURCE_IDENTITY_MISMATCH")
    return meta


def _exact_fields(actual, expected, code):
    require(type(actual) is dict and set(actual) == set(expected), code)
    for key, value in expected.items():
        require(type(actual[key]) is type(value) and actual[key] == value, code)


def validate_receipt(cache, receipt):
    """Rebind the source roster and chronology, without authenticating the clock."""
    cache = _safe_path(cache)
    require(cache.is_dir(), "CACHE_UNAVAILABLE")
    expected_names = {source[1] for source in intake.SOURCES}
    require(set(PINS) == expected_names and
            {path.name for path in cache.iterdir()} == expected_names, "CACHE_ROSTER_MISMATCH")
    constants = {"schema": SCHEMA, "observation_kind": OBSERVATION, "status": STATUS,
                 **intake.AUTHORITY}
    require(type(receipt) is dict and set(receipt) ==
            set(constants) | {"started_at", "completed_at", "sources"}, "RECEIPT_SCHEMA")
    _exact_fields({key: receipt[key] for key in constants}, constants, "RECEIPT_AUTHORITY")
    started, completed = _time(receipt["started_at"]), _time(receipt["completed_at"])
    require(started <= completed <= _time(_utcnow()), "RECEIPT_TIME_ORDER")
    entries = receipt["sources"]
    require(type(entries) is list and len(entries) == len(intake.SOURCES), "SOURCE_ROSTER_MISMATCH")
    previous = started
    for entry, source in zip(entries, intake.SOURCES):
        family, name, ref, url, _, limit = source
        fields = {"family": family, "name": name, "ref": ref, "canonical_url": url,
                  **_metadata(cache/name, name, limit)}
        require(type(entry) is dict and set(entry) ==
                set(fields) | {"started_at", "completed_at"}, "SOURCE_RECEIPT_SCHEMA")
        _exact_fields({key: entry[key] for key in fields}, fields, "SOURCE_RECEIPT_IDENTITY")
        start, end = _time(entry["started_at"]), _time(entry["completed_at"])
        require(previous <= start <= end <= completed, "SOURCE_TIME_ORDER")
        previous = end
    return receipt


def acquire(cache):
    """Create a fresh cache and acquire only the three immutable source URLs."""
    cache = _safe_path(cache)
    require(set(PINS) == {source[1] for source in intake.SOURCES}, "PIN_ROSTER_MISMATCH")
    try:
        cache.mkdir(mode=0o700)
    except OSError as exc:
        raise AcquisitionError("CACHE_EXISTS_OR_UNAVAILABLE") from exc
    result = {"schema": SCHEMA, "observation_kind": OBSERVATION, "status": STATUS,
              "started_at": _utcnow(), "sources": [], **intake.AUTHORITY}
    for family, name, ref, url, _, limit in intake.SOURCES:
        started = _utcnow()
        _download(url, cache/name, limit)
        meta = _metadata(cache/name, name, limit)
        result["sources"].append({"family": family, "name": name, "ref": ref,
                                  "canonical_url": url, "started_at": started,
                                  "completed_at": _utcnow(), **meta})
    result["completed_at"] = _utcnow()
    return validate_receipt(cache, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    receipt_path = _safe_path(args.receipt)
    if args.validate:
        require(receipt_path.is_file() and receipt_path.stat().st_size <= 1024*1024,
                "RECEIPT_FILE_SCHEMA")
        result = validate_receipt(args.cache, intake.parse(receipt_path.read_bytes()))
    else:
        # Reserve output first: an existing receipt must prevent any acquisition.
        with _exclusive_file(receipt_path) as out:
            result = acquire(args.cache)
            out.write((json.dumps(result, sort_keys=True, ensure_ascii=True,
                                  allow_nan=False, indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"status": result["status"], "source_count": len(result["sources"]),
                      "observation_kind": OBSERVATION, **intake.AUTHORITY}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AcquisitionError, intake.IntakeError) as exc:
        print(json.dumps({"status": "ACQUISITION_BLOCKED", "reason": str(exc),
                          **intake.AUTHORITY}, sort_keys=True))
        raise SystemExit(3) from None
