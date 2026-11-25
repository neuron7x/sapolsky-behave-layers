"""Bind the qualified historical Q2c receipt to a complete current Git tree.

Only unchanged object identities reuse historical evidence. Every added or
modified payload is scanned, and positive matches are observations, not errors.
"""
from __future__ import annotations

import io
from pathlib import Path
import re
import sys
import zipfile

from experiments.cwc_collision import audit as old
from experiments.real_transfer_01 import source_intake as intake

ZIP_BYTES = 579686
ZIP_SHA256 = "7aa6d37a7ba4c50f51c730a1cc4afbd027254788d1dddb26bc31f990992d9947"
AUDIT_SHA256 = "15fcf4c66c8ac52c800a9b0b4ebf40c73cb61fe4e3301de37f305a69b8883b77"
IDENTITY_SHA256 = "8cdaa4b3d47789b5f4cd696e3a462bd558310396cb3db79e4a9c1ba8039c140f"
INVENTORY_SHA256 = "c01ee88cc46e6394937bd94b6cbf490632c79f160b93041f0ee934e50dbf9693"
IDENTITY = {
    "head": "1411aa0a48d8bc82a3ad21bce48bc530d90cadff",
    "base": "091a5d22f1776f5208e57afadf0ef4c79180b325",
    "checkout": "02e8c11d0352b044495850ea48b4d99031a82035",
    "run_id": "45621004026",
    "run_attempt": "1",
}


class DeltaError(ValueError):
    """Incomplete evidence coverage, never a scientific endpoint failure."""


def require(ok, code):
    if not ok:
        raise DeltaError(code)


def load_historical_zip(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "HISTORICAL_ARCHIVE_FILE")
    require(path.stat().st_size == ZIP_BYTES, "HISTORICAL_ARCHIVE_LENGTH")
    raw = path.read_bytes()
    require(len(raw) == ZIP_BYTES and old.sha(raw) == ZIP_SHA256,
            "HISTORICAL_ARCHIVE_DIGEST")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        require(len(names) == 3 and set(names) == {"audit.json", "identity.json", "SHA256SUMS"},
                "HISTORICAL_ARCHIVE_ROSTER")
        require(all(0 < item.file_size <= 8 * 1024**2 for item in archive.infolist()),
                "HISTORICAL_MEMBER_BUDGET")
        require(archive.testzip() is None, "HISTORICAL_ARCHIVE_CRC")
        parts = {name: archive.read(name) for name in names}
    require(old.sha(parts["audit.json"]) == AUDIT_SHA256 and
            old.sha(parts["identity.json"]) == IDENTITY_SHA256, "HISTORICAL_MEMBER_DIGEST")
    sums = {}
    for line in parts["SHA256SUMS"].decode("ascii").splitlines():
        digest, name = line.split(None, 1)
        name = name.strip().lstrip("*")
        require(name in ("audit.json", "identity.json") and name not in sums,
                "HISTORICAL_CHECKSUM_ROSTER")
        require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None and
                old.sha(parts[name]) == digest, "HISTORICAL_CHECKSUM_MISMATCH")
        sums[name] = digest
    require(set(sums) == {"audit.json", "identity.json"}, "HISTORICAL_CHECKSUM_ROSTER")
    report = intake.parse(parts["audit.json"])
    identity = intake.parse(parts["identity.json"])
    require(old.canonical(identity) == old.canonical(IDENTITY), "HISTORICAL_RUN_IDENTITY")
    require(type(report) is dict and report.get("status") == "REPOSITORY_LITERAL_AUDIT_COMPLETE"
            and report.get("snapshot") == old.SNAPSHOT and report.get("tree") == old.TREE,
            "HISTORICAL_SCOPE")
    require(type(report.get("repository_exact_collision_count")) is int and
            report["repository_exact_collision_count"] == 0 and
            report.get("independent_matchers_agree") is True,
            "HISTORICAL_ZERO_RECEIPT_REQUIRED")
    require(report.get("inventory_sha256") == INVENTORY_SHA256 and
            old.sha(old.canonical(report.get("inventory"))) == INVENTORY_SHA256,
            "HISTORICAL_INVENTORY_DIGEST")
    return report, identity


def _ref(ref):
    require(type(ref) is str and (ref == "HEAD" or re.fullmatch(r"[0-9a-f]{40}", ref)),
            "TARGET_REF_SCHEMA")
    return ref


def tree_entries(root, ref):
    _ref(ref)
    raw = old.git(root, "ls-tree", "-r", "-z", "-l", ref)
    rows = raw.split(b"\0")
    require(rows[-1] == b"", "TREE_ROSTER_FORMAT")
    result = {}
    for row in rows[:-1]:
        meta, sep, path = row.partition(b"\t")
        fields = meta.split()
        require(sep == b"\t" and len(fields) == 4, "TREE_ENTRY_FORMAT")
        mode, kind, oid, size = fields
        require(mode in (b"100644", b"100755") and kind == b"blob" and size.isdigit(),
                "UNSUPPORTED_TREE_ENTRY")
        name = path.decode("utf-8", errors="strict")
        require(name and name not in result and not any(ord(ch) < 32 for ch in name),
                "TREE_PATH_SCHEMA")
        require(re.fullmatch(rb"[0-9a-f]{40}", oid) is not None and
                0 <= int(size) <= old.MAX_BLOB, "TREE_OBJECT_SCHEMA")
        result[name] = {"mode": mode.decode(), "git_blob": oid.decode(), "bytes": int(size)}
    require(0 < len(result) <= old.MAX_OBJECTS, "TREE_OBJECT_BUDGET")
    return dict(sorted(result.items()))


def assert_clean_target(root, ref="HEAD"):
    _ref(ref)
    sha = old.git(root, "rev-parse", "--verify", ref + "^{commit}").strip().decode("ascii")
    require(old.git(root, "rev-parse", "HEAD").strip().decode("ascii") == sha,
            "TARGET_NOT_EXECUTED_HEAD")
    require(old.git(root, "status", "--porcelain", "--untracked-files=no") == b"",
            "DIRTY_TRACKED_EXECUTION_TREE")
    tree = old.git(root, "rev-parse", sha + "^{tree}").strip().decode("ascii")
    return sha, tree


def validate_historical_inventory(report, entries):
    inventory = report.get("inventory")
    require(type(inventory) is list and len(inventory) == len(entries),
            "HISTORICAL_INVENTORY_ROSTER")
    indexed = {}
    total_payloads = total_bytes = 0
    for row in inventory:
        require(type(row) is dict and type(row.get("path")) is str and
                row["path"] in entries and row["path"] not in indexed,
                "HISTORICAL_INVENTORY_PATH")
        expected = entries[row["path"]]
        require(row.get("git_blob") == expected["git_blob"] and
                type(row.get("bytes")) is int and row["bytes"] == expected["bytes"] and
                type(row.get("sha256")) is str and
                re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
                "HISTORICAL_OBJECT_IDENTITY")
        require(type(row.get("matched_record_count")) is int and
                row["matched_record_count"] == 0, "HISTORICAL_NONZERO_ROW")
        units = row.get("payloads")
        require(type(units) is list and len(units) > 0, "HISTORICAL_PAYLOAD_ROSTER")
        for unit in units:
            require(type(unit) is dict and type(unit.get("bytes")) is int and
                    0 <= unit["bytes"] <= old.MAX_UNIT and
                    type(unit.get("matched_record_count")) is int and
                    unit["matched_record_count"] == 0, "HISTORICAL_PAYLOAD_IDENTITY")
            total_bytes += unit["bytes"]
            total_payloads += 1
        indexed[row["path"]] = row
    require(set(indexed) == set(entries), "HISTORICAL_INVENTORY_ROSTER")
    expected_totals = (len(entries), sum(x["bytes"] for x in entries.values()),
                       total_payloads, total_bytes)
    fields = ("tracked_blob_count", "tracked_bytes", "scanned_payload_count", "scanned_payload_bytes")
    require(all(type(report.get(k)) is int for k in fields) and
            tuple(report[k] for k in fields) == expected_totals, "HISTORICAL_TOTALS")
    return indexed


def _entry_schema(entries):
    require(type(entries) is dict and 0 < len(entries) <= old.MAX_OBJECTS,
            "DELTA_ENTRY_ROSTER")
    for name, row in entries.items():
        require(type(name) is str and name and type(row) is dict and
                set(row) == {"mode", "git_blob", "bytes"} and
                row["mode"] in ("100644", "100755") and
                type(row["git_blob"]) is str and
                re.fullmatch(r"[0-9a-f]{40}", row["git_blob"]) is not None and
                type(row["bytes"]) is int and 0 <= row["bytes"] <= old.MAX_BLOB,
                "DELTA_ENTRY_SCHEMA")


def scan_delta(root, baseline_entries, target_entries, needles):
    _entry_schema(baseline_entries)
    _entry_schema(target_entries)
    reused = sorted(name for name, row in target_entries.items()
                    if baseline_entries.get(name) == row)
    changed = sorted(set(target_entries) - set(reused))
    removed = sorted(set(baseline_entries) - set(target_entries))
    require(set(reused).isdisjoint(changed) and
            set(reused) | set(changed) == set(target_entries), "INCOMPLETE_TARGET_PARTITION")
    matcher = old.ExactMatcher(needles)
    budget = old.Budget()
    inventory = []
    matched = set()
    for name in changed:
        item = target_entries[name]
        raw = old.checked_blob(root, item["git_blob"], item["bytes"])
        row_matches = set()
        units = []
        for unit_name, unit in old.payloads(raw, name, budget):
            hits = matcher.compare(unit)
            row_matches.update(hits)
            units.append({"name_sha256": old.sha(unit_name.encode("utf-8")),
                          "bytes": len(unit), "sha256": old.sha(unit),
                          "matched_record_count": len(hits)})
        matched.update(row_matches)
        inventory.append({"path": name, **item, "sha256": old.sha(raw),
                          "payloads": units, "matched_record_count": len(row_matches)})
    require(len(inventory) + len(reused) == len(target_entries), "INCOMPLETE_DELTA_INVENTORY")
    return {"reused_paths": reused, "removed_paths": removed, "delta_inventory": inventory,
            "matched_record_ids": [list(x) for x in sorted(matched)],
            "repository_exact_collision_count": len(matched),
            "collision_counts_by_cohort": old.group_counts(matched),
            "delta_payload_count": budget.objects, "delta_payload_bytes": budget.bytes}


def audit_delta(root, cache, historical_zip, target_ref="HEAD"):
    root, cache = Path(root), Path(cache)
    target, tree = assert_clean_target(root, target_ref)
    # Do not allow untracked or substituted executable Python to claim HEAD evidence.
    modules = (
        "experiments/cwc_source_admission/collision_delta.py",
        "experiments/cwc_source_admission/acquisition.py",
        "experiments/cwc_source_admission/custody.py",
        "experiments/cwc_collision/audit.py",
        "experiments/cwc_closure/preflight.py",
        "experiments/real_transfer_01/source_intake.py",
        "experiments/real_transfer_01/contract.py",
        "experiments/real_transfer_01/preflight.py",
    )
    for path in modules:
        local = root / path
        module_name = path.removesuffix(".py").replace("/", ".")
        loaded = sys.modules.get(module_name)
        if loaded is None:
            candidate = sys.modules.get("__main__")
            if (candidate is not None and getattr(candidate, "__file__", None) is not None and
                    Path(candidate.__file__).resolve() == local.resolve()):
                loaded = candidate
        require(loaded is not None and getattr(loaded, "__file__", None) is not None and
                Path(loaded.__file__).resolve() == local.resolve(), "EXECUTED_MODULE_PATH_MISMATCH")
        require(local.is_file() and not local.is_symlink() and
                local.read_bytes() == old.git(root, "show", target + ":" + path),
                "EXECUTED_CODE_NOT_COMMITTED")
    historical, identity = load_historical_zip(historical_zip)
    require(old.git(root, "rev-parse", old.SNAPSHOT + "^{tree}").strip().decode() == old.TREE,
            "HISTORICAL_TREE_IDENTITY")
    baseline = tree_entries(root, old.SNAPSHOT)
    prior = validate_historical_inventory(historical, baseline)
    needles, sources = old.read_source_needles(cache)
    require(old.canonical(sources) == old.canonical(historical["source_identities"]) and
            old.canonical(old.group_counts(needles)) == old.canonical(historical["cohort_counts"]),
            "HISTORICAL_SOURCE_OR_COHORT_IDENTITY")
    entries = tree_entries(root, target)
    delta = scan_delta(root, baseline, entries, needles)
    reused = [{"path": name, **entries[name], "sha256": prior[name]["sha256"],
               "payload_count": len(prior[name]["payloads"]),
               "payload_bytes": sum(x["bytes"] for x in prior[name]["payloads"])}
              for name in delta.pop("reused_paths")]
    payloads = sum(x["payload_count"] for x in reused) + delta["delta_payload_count"]
    payload_bytes = sum(x["payload_bytes"] for x in reused) + delta["delta_payload_bytes"]
    require(payloads <= old.MAX_OBJECTS and payload_bytes <= old.MAX_TOTAL,
            "COMBINED_TARGET_PAYLOAD_BUDGET")
    require(assert_clean_target(root, target) == (target, tree), "EXECUTION_TREE_CHANGED")
    return {"schema": "cwc-q2b-current-tree-collision-v1",
            "status": "CURRENT_TRACKED_TREE_LITERAL_COVERAGE_COMPLETE",
            "target_commit": target, "target_tree": tree,
            "target_roster_sha256": old.sha(old.canonical(entries)),
            "target_blob_count": len(entries), "target_bytes": sum(x["bytes"] for x in entries.values()),
            "historical_artifact_id": 15023724404, "historical_zip_sha256": ZIP_SHA256,
            "historical_identity": identity, "historical_snapshot": old.SNAPSHOT,
            "historical_tree": old.TREE, "historical_inventory_sha256": INVENTORY_SHA256,
            "reused_inventory": reused, "reused_inventory_sha256": old.sha(old.canonical(reused)),
            "source_identities": sources, "cohort_counts": old.group_counts(needles),
            "covered_payload_count": payloads, "covered_payload_bytes": payload_bytes,
            "independent_matchers_agree": True, **delta,
            "scope": historical["scope"], "training_provenance": "UNKNOWN",
            "training_exact_collision_count": None, "training_collision_audit_complete": False,
            "data_terms_verified": False, "source_manifest_admitted": False,
            "model_execution_authorized": False, **intake.AUTHORITY}
