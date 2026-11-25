"""Read-only source acquisition audit for the frozen REAL-TRANSFER-01 contract.

No model invocation, raw source publication, or scientific verdict promotion.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import stat
import zipfile

from experiments.real_transfer_01 import contract as c
from experiments.real_transfer_01 import preflight as p

AV_BLOB = "40974243267f395dc583d805d10f043812419249"
HQ_BLOB = "3d0f6a9d7f11275e53cf35ca36eaa2eaff1c8a0e"
HQ_SHA256 = "424272b233735a70ed8ef5af4a615373d114f472168c686c4370d54c92d58ac1"
WIKI_SHA256 = "8f8f708f485e38a6114cf7d246e6ac00eb6f7705a9e5b740ab2ef499b864da43"
WIKI_COMMIT = "f4ed68e54e25c495f63d309de0b89c0f97b3c508"
WIKI_PREFIX = "WikiTables-WithLinks-"+WIKI_COMMIT
SOURCES = (
    ("AVeriTeC", "averitec_dev.json",
     "7c62d1ec8df3fb560d6efe2b85fa191135636f81",
     "https://raw.githubusercontent.com/MichSchli/AVeriTeC/7c62d1ec8df3fb560d6efe2b85fa191135636f81/data/dev.json",
     "CC-BY-NC-4.0", 4*1024**2),
    ("HybridQA", "hybridqa_dev.json",
     "db22fda8c5951438fade3c69d75b350335ba93b3",
     "https://raw.githubusercontent.com/wenhuchen/HybridQA/db22fda8c5951438fade3c69d75b350335ba93b3/released_data/dev.json",
     "MIT_REPOSITORY_DATA_TERMS_REVIEW_PENDING", 4*1024**2),
    ("HybridQA", "wikitable_links.zip", WIKI_COMMIT,
     "https://github.com/wenhuchen/WikiTables-WithLinks/archive/"+WIKI_COMMIT+".zip",
     "WIKIPEDIA_DERIVED_TERMS_REVIEW_PENDING", 256*1024**2),
)
MAX_ENTRY = 8*1024**2
MAX_SELECTED = 512*1024**2
MAX_ARCHIVE_ENTRIES = 40000
MAX_ARCHIVE_EXPANDED = 2*1024**3
AUTHORITY = {"scientific_verdict": "NOT_TESTED",
             "scientific_promotion_authorized": False,
             "source_action_authorized": False,
             "real_model_execution": "NOT_RUN",
             "independent_external_replication": "NOT_TESTED"}


class IntakeError(ValueError):
    """An acquisition or integrity blocker; never a behavioral negative."""


def require(ok, code):
    if not ok:
        raise IntakeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    # Git SHA1 identifies the upstream object; SHA256 is reported independently.
    return hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw,
                        usedforsecurity=False).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def reject_constant(_):
    raise IntakeError("NONFINITE_JSON_CONSTANT")


def finite_float(token):
    value = float(token)
    require(math.isfinite(value), "NONFINITE_JSON_NUMBER")
    return value


def parse(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=reject_constant, parse_float=finite_float)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise IntakeError("INVALID_SOURCE_JSON") from exc


def file_metadata(path, max_bytes):
    require(path.is_file() and not path.is_symlink(), "MISSING_OR_NONREGULAR_SOURCE")
    size = path.stat().st_size
    require(0 < size <= max_bytes, "SOURCE_BYTE_BUDGET")
    sha = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            count += len(block)
            require(count <= max_bytes, "SOURCE_BYTE_BUDGET")
            sha.update(block)
    require(count == size, "SOURCE_SIZE_CHANGED")
    return {"byte_length": count, "sha256": sha.hexdigest()}


def exact_blob(path, max_bytes, expected_blob, expected_sha=None):
    meta = file_metadata(path, max_bytes)
    raw = path.read_bytes()
    require(len(raw) == meta["byte_length"] and digest(raw) == meta["sha256"],
            "SOURCE_CHANGED_DURING_READ")
    require(git_blob(raw) == expected_blob, "UPSTREAM_GIT_BLOB_MISMATCH")
    require(expected_sha is None or meta["sha256"] == expected_sha,
            "SOURCE_SHA256_MISMATCH")
    return parse(raw), {**meta, "git_blob": expected_blob}


def table_key(value):
    require(type(value) is str and 0 < len(value) <= 512 and
            value not in (".", "..") and "/" not in value and "\\" not in value and
            all(ord(ch) >= 32 and ord(ch) != 127 for ch in value),
            "TABLE_ID_SCHEMA")
    return value


def archive_index(z):
    infos = z.infolist()
    require(0 < len(infos) <= MAX_ARCHIVE_ENTRIES, "ARCHIVE_ENTRY_BUDGET")
    seen = {}
    expanded = 0
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        require(not path.is_absolute() and path.parts and path.parts[0] == WIKI_PREFIX and
                ".." not in path.parts and "\\" not in name and
                path.as_posix() == name.rstrip("/") and name not in seen,
                "ARCHIVE_MEMBER_IDENTITY")
        mode = (info.external_attr >> 16) & 0o170000
        require(mode in (0, stat.S_IFREG, stat.S_IFDIR), "ARCHIVE_MEMBER_TYPE")
        require(not (info.flag_bits & 1), "ENCRYPTED_ARCHIVE_MEMBER")
        expanded += info.file_size
        require(expanded <= MAX_ARCHIVE_EXPANDED, "ARCHIVE_EXPANSION_BUDGET")
        seen[name] = info
    return seen


def member(z, index, name, usage):
    require(name in index and not index[name].is_dir(), "MISSING_LINKED_RESOURCE")
    info = index[name]
    require(0 < info.file_size <= MAX_ENTRY and usage[0]+info.file_size <= MAX_SELECTED,
            "LINKED_RESOURCE_BYTE_BUDGET")
    with z.open(info) as handle:
        raw = handle.read(MAX_ENTRY+1)
    require(len(raw) == info.file_size, "LINKED_RESOURCE_SIZE_MISMATCH")
    usage[0] += len(raw)
    return parse(raw), {"member": name, "byte_length": len(raw), "sha256": digest(raw)}


def validate_modalities(table, docs, key):
    require(type(table) is dict and type(docs) is dict and
            table.get("uid") == key and type(table.get("header")) is list and
            bool(table["header"]) and type(table.get("data")) is list and bool(table["data"]),
            "TABLE_OR_PASSAGE_SCHEMA")
    require(all(type(k) is str and type(v) is str for k, v in docs.items()),
            "LINKED_PASSAGE_SCHEMA")
    links = set()
    width = len(table["header"])
    for row in [table["header"], *table["data"]]:
        require(type(row) is list and len(row) == width, "TABLE_ROW_SCHEMA")
        for cell in row:
            require(type(cell) is list and len(cell) == 2 and type(cell[0]) is str and
                    type(cell[1]) is list and all(type(x) is str for x in cell[1]),
                    "TABLE_CELL_SCHEMA")
            links.update(cell[1])
    require(links.issubset(docs), "UNRESOLVED_TABLE_LINK")
    return len(links)


def av_cohorts(records):
    require(type(records) is list and len(records) == 500, "AV_DEV_ROSTER")
    labels = Counter(row.get("label") for row in records)
    require(dict(labels) == {"Refuted": 305, "Supported": 122, "Not Enough Evidence": 35,
                             "Conflicting Evidence/Cherrypicking": 38}, "AV_LABEL_ROSTER")
    cohorts = c.split_averitec(records)
    for group in (cohorts.calibration, cohorts.primary, cohorts.replication):
        for case in group:
            p.validate_averitec_model_input(case.model_input)
    bound = p.validate_cohorts(cohorts)
    require(tuple(bound[name]["count"] for name in ("CALIBRATION", "PRIMARY", "REPLICATION"))
            == (99, 199, 202), "AV_AMENDED_COHORT_ROSTER")
    return bound, dict(sorted(labels.items()))


def hybrid_cohorts(records, archive):
    require(type(records) is list and len(records) == 3466, "HQ_DEV_ROSTER")
    groups = defaultdict(list)
    ids = set()
    for row in records:
        require(type(row) is dict, "HQ_RECORD_SCHEMA")
        key = table_key(row.get("table_id"))
        identity = row.get("question_id")
        require(type(identity) is str and identity and identity not in ids, "HQ_QUESTION_ID_ROSTER")
        ids.add(identity)
        groups[key].append(row)
    require(len(groups) == 3053, "HQ_TABLE_ID_ROSTER")
    usage = [0]
    cases = []
    files = []
    link_count = 0
    missing = []
    with zipfile.ZipFile(archive) as z:
        index = archive_index(z)
        for key in sorted(groups):
            try:
                table, t_meta = member(z, index, f"{WIKI_PREFIX}/tables_tok/{key}.json", usage)
                docs, d_meta = member(z, index, f"{WIKI_PREFIX}/request_tok/{key}.json", usage)
                link_count += validate_modalities(table, docs, key)
                files.extend((t_meta, d_meta))
                for row in groups[key]:
                    case = c.make_hybridqa_case(row, table_payload=table, text_payload=docs)
                    p.validate_hybridqa_stage0(case.stage0_input(), case.initial_modality)
                    cases.append(case)
            except (IntakeError, c.ContractError, KeyError, TypeError, OSError,
                    zipfile.BadZipFile) as exc:
                # No model-output-driven skipping. Any unresolved source blocks freeze.
                missing.append({"table_id_sha256": digest(key.encode("utf-8")),
                                "error_type": type(exc).__name__,
                                "reason": str(exc) if type(exc) is IntakeError else "SOURCE_SCHEMA_ERROR"})
    if missing:
        return None, {"resolved_records": len(cases), "unresolved_tables": missing,
                      "selected_bytes": usage[0], "resolved_links": link_count}
    require(len(cases) == len(records), "HQ_RESOLUTION_ROSTER")
    cohorts = c.split_hybridqa(cases)
    bound = p.validate_cohorts(cohorts)
    require(tuple(bound[n]["count"] for n in ("CALIBRATION", "PRIMARY", "REPLICATION"))
            == (64, 256, 256), "HQ_FROZEN_COHORT_ROSTER")
    return bound, {"resolved_records": len(cases), "distinct_tables": len(groups),
                   "selected_bytes": usage[0], "resolved_links": link_count,
                   "members": files, "unresolved_tables": []}


def analyze(cache):
    result = {"experiment": "REAL-TRANSFER-01", "kind": "SOURCE_INTAKE_RECEIPT_ONLY",
              "status": "NOT_TESTED", "sources": [], "cohorts": {},
              "source_blockers": [], "execution_blockers": [
                  "SOURCE_MANIFEST_COMMIT_AND_LOCAL_BYTES_REQUIRED",
                  "REPOSITORY_FIXTURE_COLLISION_AUDIT_REQUIRED",
                  "MODEL_MANIFEST_AND_REAL_CHECKPOINT_REQUIRED",
                  "RUNNER_COMPARATORS_AND_CALIBRATION_BINDING_REQUIRED",
                  "HYBRIDQA_LINKED_DATA_TERMS_REVIEW_REQUIRED",
                  "TRAINING_PROVENANCE_UNKNOWN",
              ], **AUTHORITY}
    av = hq = None
    for family, name, ref, url, license_note, limit in SOURCES:
        try:
            path = cache/name
            if name == "averitec_dev.json":
                records, meta = exact_blob(path, limit, AV_BLOB)
                av = av_cohorts(records)
            elif name == "hybridqa_dev.json":
                hq, meta = exact_blob(path, limit, HQ_BLOB, HQ_SHA256)
                require(meta["byte_length"] == 1193503, "HQ_DEV_BYTE_ROSTER")
            else:
                meta = file_metadata(path, limit)
                require(meta["byte_length"] == 193533209 and meta["sha256"] == WIKI_SHA256,
                        "PINNED_WIKI_ARCHIVE_MISMATCH")
            result["sources"].append({"family": family, "name": name, "ref": ref,
                                      "canonical_url": url, "license_note": license_note, **meta})
        except (IntakeError, c.ContractError, KeyError, TypeError, OSError, ValueError) as exc:
            result["source_blockers"].append({"source": name, "error_type": type(exc).__name__,
                         "reason": str(exc) if type(exc) is IntakeError else "SOURCE_CONTRACT_ERROR"})
    if av is not None:
        result["cohorts"]["AVeriTeC"], result["averitec_label_counts"] = av
    if hq is not None and any(s["name"] == "wikitable_links.zip" for s in result["sources"]):
        try:
            cohorts, audit = hybrid_cohorts(hq, cache/"wikitable_links.zip")
            result["hybridqa_resolution"] = audit
            if cohorts is None:
                result["source_blockers"].append({"source": "HybridQA", "reason": "LINK_RESOLUTION_INCOMPLETE"})
            else:
                result["cohorts"]["HybridQA"] = cohorts
        except (IntakeError, c.ContractError, KeyError, TypeError, OSError, ValueError,
                zipfile.BadZipFile) as exc:
            result["source_blockers"].append({"source": "HybridQA", "error_type": type(exc).__name__,
                "reason": str(exc) if type(exc) is IntakeError else "LINKED_SOURCE_CONTRACT_ERROR"})
    if not result["source_blockers"] and set(result["cohorts"]) == {"AVeriTeC", "HybridQA"}:
        result["status"] = "SOURCE_BYTES_AND_COHORTS_RECONSTRUCTED"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.cache)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as out:
        json.dump(result, out, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
        out.write("\n")
    # Log only digests, counts and statuses; never external content or gold labels.
    summary = {"status": result["status"], "source_count": len(result["sources"]),
               "cohort_counts": {family: {name: info["count"] for name, info in groups.items()}
                                 for family, groups in result["cohorts"].items()},
               "source_blocker_count": len(result["source_blockers"]),
               "source_blockers": result["source_blockers"],
               "execution_blockers": result["execution_blockers"], **AUTHORITY}
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if result["status"] == "SOURCE_BYTES_AND_COHORTS_RECONSTRUCTED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
