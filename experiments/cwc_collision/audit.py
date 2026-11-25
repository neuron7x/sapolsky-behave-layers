"""Q2c immutable repository literal audit; no model execution or scientific authority."""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

from experiments.real_transfer_01 import contract as c
from experiments.real_transfer_01 import source_intake as intake

SNAPSHOT = "c7d67507df2d096b9cfb1f200ff3cc09c205ca6d"
TREE = "ad224c7e257e65fb5764dca61f646915eea6cedb"
QUALIFIED_CHECKOUT = "0af17009f7e62c00ed425b56550dade601a47913"
AV_SHA = "499793726b4a5406780928a3d9dedc48d6dd53de778f22437d129cacdb08e300"
EXPECTED = {
    "AVeriTeC": {
        "CALIBRATION": (99, "7a1e8c14d806608840031b47be6d00c3229911a7cf80d0c049b8760650dda9a6"),
        "PRIMARY": (199, "fb307bb7f6f69a762cdecd5627773747025358c2cbd921347601128768b17195"),
        "REPLICATION": (202, "2e8f2c36966ed92958062ba729396abdabd9e7c449674c8bf39b734890839f6d"),
    },
    "HybridQA": {
        "CALIBRATION": (64, "a41d898072b1f2a65d239a9dbd0de0650c6e0e705277abb7e5d9420a32746ad4"),
        "PRIMARY": (256, "52258e464ea62f4e04e9fa327745b206b35df151222ed9ab3f6db24fbb91135c"),
        "REPLICATION": (256, "92db05c5bcbb6c94eb00bf4dd45881c2004931ed9316aba10bb11c3b576ec7f7"),
    },
}
MAX_BLOB = 32 * 1024**2
MAX_UNIT = 256 * 1024**2
MAX_TOTAL = 1024**3
MAX_OBJECTS = 100000
MAX_DEPTH = 4


class AuditError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise AuditError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, check=False, timeout=60)
    require(result.returncode == 0, "GIT_OBJECT_UNAVAILABLE")
    return result.stdout


def roster(root):
    require(git(root, "rev-parse", SNAPSHOT+"^{tree}").strip().decode() == TREE,
            "SNAPSHOT_TREE_MISMATCH")
    rows = git(root, "ls-tree", "-r", "-z", "-l", TREE).split(b"\0")
    require(rows[-1] == b"", "TREE_ROSTER_FORMAT")
    seen = set()
    entries = []
    for row in rows[:-1]:
        meta, sep, path = row.partition(b"\t")
        fields = meta.split()
        require(sep == b"\t" and len(fields) == 4, "TREE_ENTRY_FORMAT")
        mode, kind, object_id, size = fields
        require(mode in (b"100644", b"100755") and kind == b"blob" and size.isdigit(),
                "UNSUPPORTED_TREE_ENTRY")
        name = path.decode("utf-8", errors="strict")
        require(bool(name) and name not in seen, "TREE_DUPLICATE_PATH")
        seen.add(name)
        n = int(size)
        require(0 <= n <= MAX_BLOB, "BLOB_BYTE_BUDGET")
        entries.append((name, object_id.decode("ascii"), n))
    require(0 < len(entries) <= MAX_OBJECTS, "TREE_OBJECT_BUDGET")
    return sorted(entries)


def checked_blob(root, object_id, size):
    raw = git(root, "cat-file", "blob", object_id)
    require(len(raw) == size and intake.git_blob(raw) == object_id, "BLOB_IDENTITY_MISMATCH")
    return raw


def read_source_needles(cache):
    report = intake.analyze(cache)
    require(report.get("status") == "SOURCE_BYTES_AND_COHORTS_RECONSTRUCTED"
            and not report.get("source_blockers"), "PINNED_SOURCE_ADMISSION")
    av, av_meta = intake.exact_blob(cache/"averitec_dev.json", 4*1024**2, intake.AV_BLOB, AV_SHA)
    hq, hq_meta = intake.exact_blob(cache/"hybridqa_dev.json", 4*1024**2, intake.HQ_BLOB, intake.HQ_SHA256)
    require(len(av) == 500 and len(hq) == 3466, "SOURCE_RECORD_ROSTER")
    observed = {x["name"]: x for x in report["sources"]}
    for name, meta in (("averitec_dev.json", av_meta), ("hybridqa_dev.json", hq_meta)):
        require(observed[name]["sha256"] == meta["sha256"], "SOURCE_REREAD_MISMATCH")
    # Original intake already resolved all 3466 records against actual linked bytes.
    # Reconstruct only the frozen canonical identity, not a fabricated modality.
    require(report["hybridqa_resolution"]["resolved_records"] == 3466, "HQ_RESOLUTION_ROSTER")
    av_rows = [(c.make_averitec_case(row).record_hash, row["claim"]) for row in av]
    hq_rows = [(sha("\n".join(row[k] for k in
                 ("question_id", "question", "table_id", "answer-text")).encode("utf-8")),
                row["question"]) for row in hq]
    needles = bind_rosters(report["cohorts"], {"AVeriTeC": av_rows, "HybridQA": hq_rows})
    return needles, [{k: x[k] for k in ("name", "ref", "sha256", "byte_length")}
                     for x in report["sources"]]


def bind_rosters(declared, rows):
    require(set(declared) == set(EXPECTED) == set(rows), "COHORT_FAMILY_ROSTER")
    result = {}
    for family, groups in EXPECTED.items():
        raw_rows = rows[family]
        by_id = dict(raw_rows)
        require(len(by_id) == len(raw_rows), "DUPLICATE_SOURCE_ID")
        require(set(declared[family]) == set(groups), "COHORT_GROUP_ROSTER")
        seen = set()
        for group, (count, digest) in groups.items():
            info = declared[family][group]
            ids = info["record_hashes"]
            require(type(info["count"]) is int and info["count"] == count
                    and len(ids) == count and ids == sorted(ids)
                    and len(set(ids)) == count and not seen.intersection(ids)
                    and set(ids).issubset(by_id)
                    and info["cohort_sha256"] == digest
                    and sha("\n".join(ids).encode("utf-8")) == digest,
                    "FROZEN_COHORT_IDENTITY")
            for identity in ids:
                value = by_id[identity]
                require(type(value) is str and bool(value.strip()), "EMPTY_SOURCE_NEEDLE")
                result[(family, group, identity)] = value
            seen.update(ids)
    require(len(result) == 1076, "FROZEN_COHORT_TOTAL")
    return result


class ExactMatcher:
    def __init__(self, needles):
        values = defaultdict(set)
        for identity, value in needles.items():
            require(type(value) is str and bool(value), "EMPTY_SOURCE_NEEDLE")
            variants = {value, json.dumps(value, ensure_ascii=True)[1:-1],
                        json.dumps(value, ensure_ascii=False)[1:-1]}
            for variant in variants:
                values[variant.encode("utf-8")].add(identity)
        self.values = dict(values)
        self.reference = {value: re.compile(re.escape(value)) for value in values}

    def compare(self, raw):
        direct = {value for value in self.values if raw.find(value) != -1}
        reference = {value for value, pattern in self.reference.items()
                     if pattern.search(raw) is not None}
        require(direct == reference, "INDEPENDENT_MATCHER_DISAGREEMENT")
        return {identity for value in direct for identity in self.values[value]}


class Budget:
    def __init__(self, max_total=MAX_TOTAL, max_objects=MAX_OBJECTS):
        self.max_total = max_total
        self.max_objects = max_objects
        self.bytes = 0
        self.objects = 0

    def add(self, raw, depth):
        require(depth <= MAX_DEPTH and len(raw) <= MAX_UNIT, "PAYLOAD_UNIT_BUDGET")
        self.bytes += len(raw)
        self.objects += 1
        require(self.bytes <= self.max_total and self.objects <= self.max_objects,
                "PAYLOAD_TOTAL_BUDGET")


def bounded_read(handle):
    raw = handle.read(MAX_UNIT+1)
    require(len(raw) <= MAX_UNIT, "ARCHIVE_EXPANSION_BUDGET")
    return raw


def payloads(raw, name, budget, depth=0):
    """Read actual payloads, without extracting archive members or executing code."""
    budget.add(raw, depth)
    yield name, raw
    lower = name.lower()
    if lower.endswith(".gz") or raw.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
            inner = bounded_read(handle)
        inner_name = name[:-3] if lower.endswith(".gz") else name+"!gzip"
        yield from payloads(inner, inner_name, budget, depth+1)
    elif lower.endswith(".tar") or (len(raw) >= 265 and raw[257:262] == b"ustar"):
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            seen = set()
            for member in archive:
                require(member.name not in seen, "DUPLICATE_ARCHIVE_MEMBER")
                seen.add(member.name)
                if member.isdir():
                    continue
                require(member.isreg(), "UNSUPPORTED_TAR_MEMBER")
                require(0 <= member.size <= MAX_UNIT, "ARCHIVE_MEMBER_BUDGET")
                handle = archive.extractfile(member)
                require(handle is not None, "ARCHIVE_MEMBER_MISSING")
                with handle:
                    child = bounded_read(handle)
                require(len(child) == member.size, "ARCHIVE_MEMBER_SIZE")
                yield from payloads(child, name+"!"+member.name, budget, depth+1)
    elif lower.endswith(".zip") or raw.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            seen = set()
            for member in archive.infolist():
                require(member.filename not in seen and not member.flag_bits & 1,
                        "INVALID_ZIP_MEMBER")
                seen.add(member.filename)
                if member.is_dir():
                    continue
                require(0 <= member.file_size <= MAX_UNIT, "ARCHIVE_MEMBER_BUDGET")
                with archive.open(member) as handle:
                    child = bounded_read(handle)
                require(len(child) == member.file_size, "ARCHIVE_MEMBER_SIZE")
                yield from payloads(child, name+"!"+member.filename, budget, depth+1)


def group_counts(identities):
    return {family: {group: sum(x[0] == family and x[1] == group for x in identities)
                     for group in groups} for family, groups in EXPECTED.items()}


def repeated_text(needles):
    result = {}
    for family in EXPECTED:
        groups = defaultdict(list)
        for identity, value in needles.items():
            if identity[0] == family:
                groups[value].append(identity[1])
        repeated = [v for v in groups.values() if len(v) > 1]
        cross = [v for v in repeated if len(set(v)) > 1]
        result[family] = {"unique_texts": len(groups), "duplicate_text_groups": len(repeated),
                          "cross_cohort_groups": len(cross),
                          "records_in_cross_cohort_groups": sum(map(len, cross))}
    return result


def audit(root, cache):
    needles, sources = read_source_needles(cache)
    matcher = ExactMatcher(needles)
    budget = Budget()
    inventory = []
    matched = set()
    entries = roster(root)
    for name, oid, n in entries:
        raw = checked_blob(root, oid, n)
        row_matches = set()
        child_meta = []
        for unit_name, unit in payloads(raw, name, budget):
            hits = matcher.compare(unit)
            row_matches.update(hits)
            child_meta.append({"name_sha256": sha(unit_name.encode("utf-8")),
                               "bytes": len(unit), "sha256": sha(unit),
                               "matched_record_count": len(hits)})
        matched.update(row_matches)
        inventory.append({"path": name, "git_blob": oid, "bytes": n, "sha256": sha(raw),
                          "payloads": child_meta, "matched_record_count": len(row_matches)})
    require(len(inventory) == len(entries), "INCOMPLETE_TREE_INVENTORY")
    return {"schema": "cwc-q2c-repository-audit-v1", "status": "REPOSITORY_LITERAL_AUDIT_COMPLETE",
            "snapshot": SNAPSHOT, "tree": TREE, "prior_qualified_checkout": QUALIFIED_CHECKOUT,
            "source_identities": sources, "cohort_counts": group_counts(needles),
            "repository_exact_collision_count": len(matched),
            "collision_counts_by_cohort": group_counts(matched),
            "duplicate_input_text": repeated_text(needles),
            "inventory": inventory, "inventory_sha256": sha(canonical(inventory)),
            "tracked_blob_count": len(entries), "tracked_bytes": sum(x[2] for x in entries),
            "scanned_payload_count": budget.objects, "scanned_payload_bytes": budget.bytes,
            "independent_matchers_agree": True,
            "scope": "EXACT_UTF8_OR_JSON_ESCAPED_LITERAL_SUBSTRING_ALL_TRACKED_BLOBS_AND_SUPPORTED_ARCHIVES",
            "training_provenance": "UNKNOWN", "training_exact_collision_count": None,
            "training_collision_audit_complete": False,
            "data_terms_verified": False, "source_manifest_admitted": False,
            "model_execution_authorized": False, **intake.AUTHORITY}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.root, args.cache)
    except (AuditError, intake.IntakeError, c.ContractError, OSError, ValueError,
            UnicodeError, KeyError, TypeError, EOFError, tarfile.TarError, zipfile.BadZipFile,
            subprocess.SubprocessError) as exc:
        report = {"schema": "cwc-q2c-repository-audit-v1", "status": "NOT_TESTED",
                  "blocker": str(exc) if type(exc) is AuditError else type(exc).__name__,
                  "repository_exact_collision_count": None, "model_execution_authorized": False,
                  **intake.AUTHORITY}
    with args.receipt.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, sort_keys=True, ensure_ascii=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "inventory"},
                     sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0 if report["status"] == "REPOSITORY_LITERAL_AUDIT_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
