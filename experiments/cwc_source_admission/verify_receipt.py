"""Independently reconstruct a Q2b custody receipt; no admission authority.

The producer's new custody/delta code is not imported. Frozen source semantics
and bounded archive expansion are shared; matching and inventory joins are not.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.parse import parse_qs, unquote, urlsplit
import zipfile

from experiments.cwc_collision import audit as frozen
from experiments.real_transfer_01 import contract, source_intake as intake

ZIP_SHA = "7aa6d37a7ba4c50f51c730a1cc4afbd027254788d1dddb26bc31f990992d9947"
INVENTORY_SHA = "c01ee88cc46e6394937bd94b6cbf490632c79f160b93041f0ee934e50dbf9693"
PARTS = {"audit.json": "15fcf4c66c8ac52c800a9b0b4ebf40c73cb61fe4e3301de37f305a69b8883b77",
         "identity.json": "8cdaa4b3d47789b5f4cd696e3a462bd558310396cb3db79e4a9c1ba8039c140f"}
IDENTITY = {"head": "1411aa0a48d8bc82a3ad21bce48bc530d90cadff",
            "base": "091a5d22f1776f5208e57afadf0ef4c79180b325",
            "checkout": "02e8c11d0352b044495850ea48b4d99031a82035",
            "run_id": "45621004026", "run_attempt": "1"}
AUTHORITY = {"scientific_verdict": "NOT_TESTED", "scientific_promotion_authorized": False,
             "model_execution_authorized": False, "source_manifest_admitted": False,
             "source_action_authorized": False,
             "data_terms_verified": False, "use_context_verified": False,
             "real_model_execution": "NOT_RUN", "independent_external_replication": "NOT_TESTED"}


class VerificationError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise VerificationError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode()


def same(actual, expected, code):
    require(canonical(actual) == canonical(expected), code)


def read(path, limit):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit, "INPUT_FILE")
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    require(len(raw) == before.st_size == after.st_size and
            (before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_mtime_ns, after.st_ctime_ns), "INPUT_CHANGED")
    return raw


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    require(result.returncode == 0, "GIT_READ_FAILED")
    return result.stdout


def roster(root, ref):
    result = {}
    for row in git(root, "ls-tree", "-rzl", ref).split(b"\0")[:-1]:
        metadata, path = row.split(b"\t", 1)
        mode, kind, blob, size = metadata.split()
        require(mode in (b"100644", b"100755") and kind == b"blob" and size.isdigit(),
                "UNSUPPORTED_TREE_ENTRY")
        name = path.decode("utf-8")
        require(name not in result and int(size) <= frozen.MAX_BLOB, "TREE_ROSTER")
        result[name] = {"mode": mode.decode(), "git_blob": blob.decode(), "bytes": int(size)}
    require(0 < len(result) <= frozen.MAX_OBJECTS, "TREE_SIZE")
    return dict(sorted(result.items()))


def verify_url(item, value, field, observed):
    """Check actual source identity and bounded URL facts without source retrieval."""
    text = type(value) is str
    raw = value.encode() if text else canonical(value)
    required = {"source_field", "source_value_sha256", "source_value_type", "url", "url_origin",
                "structural_url_valid", "http_fetch_performed", "provenance_verified",
                "historical_revision_id", "imported_notices_reviewed"}
    require(type(item) is dict and set(item) in (required, required | {"unresolved_reason"}),
            "ATTRIBUTION_SCHEMA")
    same([item["source_field"], item["source_value_sha256"], item["source_value_type"]],
         [field, sha(raw), "string" if text else "nonstring"], "ATTRIBUTION_SOURCE_IDENTITY")
    for flag in ("http_fetch_performed", "provenance_verified", "imported_notices_reviewed"):
        require(item[flag] is False, "ATTRIBUTION_AUTHORITY")
    valid = text and 0 < len(raw) <= 16384 and not re.search(r"[\s\x00-\x1f\x7f\\]", value) and not re.search(r"%(?![0-9a-fA-F]{2})", value)
    source_shape_valid = bool(valid)
    derived = text and value.startswith("/wiki/")
    url = "https://en.wikipedia.org" + value if derived else value
    try:
        parsed = urlsplit(url) if valid else None
        valid = bool(valid and parsed.scheme in ("http", "https") and parsed.hostname and
                     parsed.username is None and parsed.password is None and
                     (parsed.port is None or 0 < parsed.port <= 65535) and
                     not re.search(r"[\x00-\x1f\x7f]", unquote(url)))
        if valid:
            try:
                ipaddress.ip_address(parsed.hostname)
            except ValueError:
                host = parsed.hostname.encode("idna").decode().rstrip(".")
                labels = host.split(".")
                valid = len(host) <= 253 and len(labels) >= 2 and all(
                    re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in labels)
        if valid and derived:
            valid = parsed.path.startswith("/wiki/") and all(
                segment not in ("", ".", "..") for segment in unquote(parsed.path).split("/")[2:])
    except (ValueError, UnicodeError):
        valid = False
    require(item["structural_url_valid"] is bool(valid), "INDEPENDENT_URL_CLASSIFICATION")
    require(set(item) == (required if valid else required | {"unresolved_reason"}),
            "ATTRIBUTION_SCHEMA")
    if item["url_origin"] == "UNRESOLVED":
        require(not valid and item["url"] is None and item["structural_url_valid"] is False and
                item["historical_revision_id"] is None and
                type(item.get("unresolved_reason")) is str, "UNRESOLVED_URL_STATE")
        same(item["unresolved_reason"],
             "INVALID_OR_AMBIGUOUS_SOURCE_URL" if source_shape_valid else "MISSING_OR_MALFORMED_SOURCE_URL",
             "UNRESOLVED_REASON")
    else:
        require(valid, "URL_STRUCTURE")
        same([item["url"], item["url_origin"], item["structural_url_valid"]],
             [url, "MECHANICALLY_DERIVED_WIKIPEDIA_PATH" if derived else "SOURCE_ABSOLUTE_URL", True],
             "URL_DERIVATION")
        oldids = parse_qs(parsed.query, keep_blank_values=True).get("oldid", [])
        oldid = oldids[0] if len(oldids) == 1 and re.fullmatch(r"[0-9]+", oldids[0]) and int(oldids[0]) > 0 else None
        same(item["historical_revision_id"], oldid, "OBSERVED_REVISION")
    observed.append(item)
    return item


def verify_sources(cache, receipt, acquisition_path):
    trace_raw = read(acquisition_path, 1024**2)
    trace = intake.parse(trace_raw)
    require(type(trace) is dict and set(trace) == {"schema", "observation_kind", "status", "started_at",
            "completed_at", "sources"} | set(intake.AUTHORITY), "ACQUISITION_SCHEMA")
    same(receipt["acquisition"], trace, "ACQUISITION_TRACE")
    require(receipt["acquisition_receipt_sha256"] == sha(trace_raw), "ACQUISITION_TRACE_DIGEST")
    require(trace["schema"] == "cwc-source-acquisition-v1" and
            trace["observation_kind"] == "SELF_OBSERVED_NOT_AUTHENTICATED" and
            trace["status"] == "PINNED_SOURCE_BYTES_ACQUIRED", "ACQUISITION_SCOPE")
    for key, value in intake.AUTHORITY.items():
        same(trace[key], value, "ACQUISITION_AUTHORITY")
    def parse_time(value):
        require(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", value), "TIME_SCHEMA")
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    started, completed = parse_time(trace["started_at"]), parse_time(trace["completed_at"])
    require(started <= completed <= datetime.now(timezone.utc), "ACQUISITION_TIME")
    require(len(trace["sources"]) == 3 and not cache.is_symlink() and
            set(p.name for p in cache.iterdir()) == {x[1] for x in intake.SOURCES}, "SOURCE_ROSTER")
    actual = intake.analyze(cache)
    require(actual["status"] == "SOURCE_BYTES_AND_COHORTS_RECONSTRUCTED" and
            actual["source_blockers"] == [], "SOURCE_RECONSTRUCTION")
    projected, source_ids = [], []
    for source, recorded in zip(actual["sources"], trace["sources"]):
        identity = {key: source[key] for key in ("family", "name", "ref", "canonical_url", "byte_length", "sha256")}
        identity["git_blob"] = source.get("git_blob")
        require(set(recorded) == set(identity) | {"started_at", "completed_at"}, "SOURCE_TRACE_SCHEMA")
        same({key: recorded[key] for key in identity}, identity, "SOURCE_TRACE_BYTES")
        start, end = parse_time(recorded["started_at"]), parse_time(recorded["completed_at"])
        require(started <= start <= end <= completed, "SOURCE_TRACE_TIME")
        started = end
        if identity["git_blob"] is None:
            identity.pop("git_blob")
        projected.append(identity)
        source_ids.append({key: source[key] for key in ("name", "ref", "sha256", "byte_length")})
    projection = {"sources": sorted(projected, key=lambda x: x["name"]), "cohorts": actual["cohorts"]}
    same(receipt["source_projection"], projection, "SOURCE_PROJECTION")
    require(receipt["source_projection_sha256"] == sha(canonical(projection)), "PROJECTION_DIGEST")
    rows, needles = {}, {}
    for family, filename in (("AVeriTeC", "averitec_dev.json"), ("HybridQA", "hybridqa_dev.json")):
        source_raw = read(cache/filename, 4*1024**2)
        source_identity = next(item for item in source_ids if item["name"] == filename)
        require(sha(source_raw) == source_identity["sha256"] and len(source_raw) == source_identity["byte_length"], "SOURCE_REREAD")
        source_rows = intake.parse(source_raw)
        keyed = {}
        for row in source_rows:
            identity = (contract.make_averitec_case(row).record_hash if family == "AVeriTeC" else
                        sha("\n".join(row[k] for k in ("question_id", "question", "table_id", "answer-text")).encode()))
            require(identity not in keyed, "SOURCE_RECORD_DUPLICATE")
            keyed[identity] = row
        rows[family] = []
        for group, (count, expected_digest) in frozen.EXPECTED[family].items():
            declaration = actual["cohorts"][family][group]
            ids = declaration["record_hashes"]
            require(len(ids) == count and ids == sorted(set(ids)) and
                    sha("\n".join(ids).encode()) == expected_digest, "FROZEN_ORDERED_COHORT")
            for identity in ids:
                row = keyed[identity]
                rows[family].append((group, identity, row))
                needles[(family, group, identity)] = row["claim" if family == "AVeriTeC" else "question"]
    return source_ids, rows, needles


def verify_attribution(cache, receipt, rows):
    observed = []
    hq = receipt["hybridqa_inventory"]
    relations = [{"cohort": group, "record_hash": identity, "table_id_sha256": sha(row["table_id"].encode())}
                 for group, identity, row in rows["HybridQA"]]
    same(hq["records"], relations, "HQ_RECORD_RELATIONS")
    keys = sorted({row["table_id"] for _, _, row in rows["HybridQA"]})
    require(len(hq["tables"]) == len(keys), "HQ_TABLE_ROSTER")
    total_bytes = passages = unreferenced = 0
    with zipfile.ZipFile(cache/"wikitable_links.zip") as archive:
        for key, table_item in zip(keys, hq["tables"]):
            payloads, metadata = [], []
            for directory in ("tables_tok", "request_tok"):
                name = f"{intake.WIKI_PREFIX}/{directory}/{key}.json"
                raw = archive.read(name)
                require(0 < len(raw) <= intake.MAX_ENTRY, "MEMBER_BYTES")
                payloads.append(intake.parse(raw))
                metadata.append({"member": name, "byte_length": len(raw), "sha256": sha(raw)})
                total_bytes += len(raw)
            table, docs = payloads
            links = {link for row in [table["header"], *table["data"]] for cell in row for link in cell[1]}
            require(links.issubset(docs) and len(table_item["passages"]) == len(docs), "FULL_REQUEST_DICTIONARY")
            for (source_key, text), item in zip(sorted(docs.items()), table_item["passages"]):
                expected = {"key_sha256": sha(source_key.encode()), "passage_byte_length": len(text.encode()),
                            "passage_sha256": sha(text.encode()),
                            "attribution": verify_url(item["attribution"], source_key, "request_tok.key", observed)}
                same(item, expected, "PASSAGE_METADATA")
            expected = {"table_id_sha256": sha(key.encode()), "table_member": metadata[0], "request_member": metadata[1],
                        "table_attribution": verify_url(table_item["table_attribution"], table.get("url"), "table.url", observed),
                        "passage_count": len(docs), "table_cell_link_count": len(links),
                        "unreferenced_passage_count": len(set(docs)-links), "passages": table_item["passages"]}
            same(table_item, expected, "TABLE_METADATA")
            passages += len(docs)
            unreferenced += len(set(docs)-links)
    same(hq, {"record_count": 576, "records": relations, "distinct_table_count": len(keys), "tables": hq["tables"],
              "selected_member_bytes": total_bytes, "passage_entry_count": passages,
              "unreferenced_passage_count": unreferenced}, "HQ_TOTALS")
    av = receipt["averitec_inventory"]
    require(len(av["records"]) == 500, "AV_RECORD_ROSTER")
    answer_count = 0
    for (group, identity, source), record in zip(rows["AVeriTeC"], av["records"]):
        answers = [(qi, ai, answer) for qi, question in enumerate(source["questions"])
                   for ai, answer in enumerate(question["answers"])]
        require(len(record["evidence_sources"]) == len(answers), "AV_EVIDENCE_ROSTER")
        for (qi, ai, answer), evidence in zip(answers, record["evidence_sources"]):
            require(len(evidence["sources"]) == 2, "AV_URL_ROSTER")
            urls = [verify_url(item, answer.get(field), field, observed) for field, item in
                    zip(("source_url", "cached_source_url"), evidence["sources"])]
            same(evidence, {"question_index": qi, "answer_index": ai, "sources": urls}, "AV_EVIDENCE_IDENTITY")
        same(record, {"cohort": group, "record_hash": identity, "evidence_sources": record["evidence_sources"]}, "AV_RECORD_IDENTITY")
        answer_count += len(answers)
    same(av, {"record_count": 500, "records": av["records"], "evidence_answer_count": answer_count}, "AV_TOTALS")
    summary = {"url_metadata_entries": len(observed), "url_origins": dict(sorted(Counter(x["url_origin"] for x in observed).items())),
               "entries_with_observed_oldid": sum(x["historical_revision_id"] is not None for x in observed),
               "article_http_fetches": 0, "verified_revision_provenance": 0, "reviewed_imported_content_notices": 0,
               "unresolved_by_source_field": dict(sorted(Counter(x["source_field"] for x in observed if not x["structural_url_valid"]).items())),
               "averitec_evidence_answers_without_structural_source_url": sum(
                   not any(url["structural_url_valid"] for url in evidence["sources"])
                   for record in av["records"] for evidence in record["evidence_sources"]),
               "url_gaps_are_scientific_rejection_thresholds": False}
    same(receipt["attribution_summary"], summary, "ATTRIBUTION_TOTALS")
    return {"hybridqa_records": 576, "hybridqa_tables": len(keys), "passage_entries": passages,
            "averitec_records": 500, "evidence_answers": answer_count, "url_metadata_entries": len(observed)}


def verify_collision(root, receipt, historical_zip, source_ids, needles):
    raw = read(historical_zip, 579686)
    require(len(raw) == 579686 and sha(raw) == ZIP_SHA, "HISTORICAL_ZIP_IDENTITY")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(sorted(archive.namelist()) == ["SHA256SUMS", "audit.json", "identity.json"] and
                archive.testzip() is None, "HISTORICAL_ARCHIVE_ROSTER_CRC")
        parts = {name: archive.read(name) for name in archive.namelist()}
    require(all(sha(parts[name]) == digest for name, digest in PARTS.items()), "HISTORICAL_PART_DIGEST")
    checksums = {name: digest for digest, name in (line.split() for line in parts["SHA256SUMS"].decode().splitlines())}
    same(checksums, PARTS, "HISTORICAL_CHECKSUMS")
    history, identity = intake.parse(parts["audit.json"]), intake.parse(parts["identity.json"])
    same(identity, IDENTITY, "HISTORICAL_RUN")
    require(sha(canonical(history["inventory"])) == INVENTORY_SHA and
            history["repository_exact_collision_count"] == 0, "HISTORICAL_INVENTORY")
    same(history["source_identities"], source_ids, "HISTORICAL_SOURCE_BYTES")
    target = git(root, "rev-parse", "HEAD").strip().decode()
    tree = git(root, "rev-parse", "HEAD^{tree}").strip().decode()
    require(git(root, "status", "--porcelain", "--untracked-files=no") == b"", "DIRTY_TARGET")
    require(git(root, "rev-parse", frozen.SNAPSHOT+"^{tree}").strip().decode() == frozen.TREE, "HISTORICAL_TREE")
    old, current = roster(root, frozen.SNAPSHOT), roster(root, target)
    prior = {row["path"]: row for row in history["inventory"]}
    require(len(prior) == len(history["inventory"]) and set(prior) == set(old), "HISTORICAL_ROSTER")
    for path, entry in old.items():
        same([prior[path]["git_blob"], prior[path]["bytes"]], [entry["git_blob"], entry["bytes"]], "HISTORICAL_OBJECT")
    reused = [{"path": path, **item, "sha256": prior[path]["sha256"],
               "payload_count": len(prior[path]["payloads"]),
               "payload_bytes": sum(x["bytes"] for x in prior[path]["payloads"])}
              for path, item in current.items() if old.get(path) == item]
    changed = [path for path, item in current.items() if old.get(path) != item]
    variants = {identity: {text.encode(), json.dumps(text, ensure_ascii=True)[1:-1].encode(),
                           json.dumps(text, ensure_ascii=False)[1:-1].encode()}
                for identity, text in needles.items()}
    budget, matched, inventory = frozen.Budget(), set(), []
    for path in changed:
        item = current[path]
        body = git(root, "cat-file", "blob", item["git_blob"])
        require(len(body) == item["bytes"] and intake.git_blob(body) == item["git_blob"], "CURRENT_OBJECT_BYTES")
        row_hits, units = set(), []
        for unit_name, unit in frozen.payloads(body, path, budget):
            hits = {identity for identity, choices in variants.items() if any(value in unit for value in choices)}
            row_hits.update(hits)
            units.append({"name_sha256": sha(unit_name.encode()), "bytes": len(unit), "sha256": sha(unit),
                          "matched_record_count": len(hits)})
        matched.update(row_hits)
        inventory.append({"path": path, **item, "sha256": sha(body), "payloads": units, "matched_record_count": len(row_hits)})
    counts = {family: {group: sum(x[0] == family and x[1] == group for x in matched)
                       for group in groups} for family, groups in frozen.EXPECTED.items()}
    expected = {"target_commit": target, "target_tree": tree, "target_roster_sha256": sha(canonical(current)),
                "target_blob_count": len(current), "target_bytes": sum(x["bytes"] for x in current.values()),
                "historical_artifact_id": 15023724404, "historical_zip_sha256": ZIP_SHA, "historical_identity": identity,
                "historical_snapshot": frozen.SNAPSHOT, "historical_tree": frozen.TREE,
                "historical_inventory_sha256": INVENTORY_SHA, "reused_inventory": reused,
                "reused_inventory_sha256": sha(canonical(reused)), "removed_paths": sorted(set(old)-set(current)),
                "source_identities": source_ids, "cohort_counts": history["cohort_counts"],
                "delta_inventory": inventory, "delta_payload_count": budget.objects, "delta_payload_bytes": budget.bytes,
                "matched_record_ids": [list(x) for x in sorted(matched)], "repository_exact_collision_count": len(matched),
                "collision_counts_by_cohort": counts, "covered_payload_count": budget.objects + sum(x["payload_count"] for x in reused),
                "covered_payload_bytes": budget.bytes + sum(x["payload_bytes"] for x in reused), "scope": history["scope"]}
    require(expected["covered_payload_count"] <= frozen.MAX_OBJECTS and
            expected["covered_payload_bytes"] <= frozen.MAX_TOTAL, "COMBINED_PAYLOAD_BUDGET")
    declared = receipt["repository_collision_binding"]
    expected.update({"schema": "cwc-q2b-current-tree-collision-v1", "status": "CURRENT_TRACKED_TREE_LITERAL_COVERAGE_COMPLETE",
                     "independent_matchers_agree": True, **intake.AUTHORITY, "data_terms_verified": False,
                     "source_manifest_admitted": False, "model_execution_authorized": False,
                     "training_provenance": "UNKNOWN", "training_collision_audit_complete": False,
                     "training_exact_collision_count": None})
    same(declared, expected, "CURRENT_COLLISION_BINDING")
    return {"target_commit": target, "target_tree": tree, "reused_blobs": len(reused), "scanned_delta_blobs": len(changed),
            "removed_blobs": len(expected["removed_paths"]), "repository_exact_collision_count": len(matched),
            "target_roster_sha256": expected["target_roster_sha256"]}


def verify(root, cache, receipt_path, historical_zip, acquisition_path):
    raw = read(receipt_path, 64*1024**2)
    receipt = intake.parse(raw)
    known = {"schema", "status", "acquisition_receipt_sha256", "acquisition", "source_projection", "source_projection_sha256",
             "hybridqa_inventory", "averitec_inventory", "attribution_summary", "repository_collision_binding",
             "governance_metadata_is_model_input", "source_text_or_gold_published", "blockers", "attribution", "limits",
             "limitations", "source_action_authorized"} | set(AUTHORITY)
    require(type(receipt) is dict and set(receipt) == known, "CUSTODY_SCHEMA")
    require(receipt["schema"] == "cwc-source-custody-v1" and
            receipt["status"] == "SOURCE_CUSTODY_RECONSTRUCTED_ADMISSION_BLOCKED", "CUSTODY_SCOPE")
    same(receipt["blockers"], ["SOURCE_MANIFEST_NOT_ADMITTED", "NONCOMMERCIAL_USE_CONTEXT_UNESTABLISHED",
         "ITEM_LEVEL_ATTRIBUTION_AND_IMPORTED_NOTICE_REVIEW_PENDING",
         "MODEL_MATERIALS_AND_EXECUTION_PREREQUISITES_PENDING"], "CUSTODY_BLOCKERS")
    same(receipt["limitations"], ["REVISION_PROVENANCE_UNVERIFIED",
         "ABSENT_HISTORICAL_OLDID_IS_NOT_AN_ADMISSION_THRESHOLD",
         "STRUCTURAL_URL_VALIDITY_IS_NOT_HTTP_OR_NOTICE_VERIFICATION"], "CUSTODY_LIMITATIONS")
    same(receipt["attribution"], ["Schlichtkrull, Guo and Vlachos (2023): AVeriTeC",
         "Chen et al. (2020): HybridQA", "Wikipedia contributors"], "PUBLISHER_ATTRIBUTION")
    same(receipt["limits"], {"max_url_bytes": 16384, "max_custody_receipt_bytes": 64*1024**2,
         "source_and_archive_limits": "UNCHANGED_SOURCE_INTAKE_LIMITS"}, "CUSTODY_LIMITS")
    for key, value in {**AUTHORITY, "source_action_authorized": False,
                       "governance_metadata_is_model_input": False, "source_text_or_gold_published": False}.items():
        same(receipt[key], value, "CUSTODY_AUTHORITY")
    source_ids, rows, needles = verify_sources(cache, receipt, acquisition_path)
    attribution = verify_attribution(cache, receipt, rows)
    collision = verify_collision(root, receipt, historical_zip, source_ids, needles)
    for source in source_ids:
        metadata = intake.file_metadata(cache/source["name"], source["byte_length"])
        same(metadata, {"byte_length": source["byte_length"], "sha256": source["sha256"]}, "SOURCE_CHANGED_DURING_VERIFICATION")
    own_path = Path(__file__).resolve()
    relative = own_path.relative_to(root.resolve()).as_posix()
    require(read(own_path, 1024**2) == git(root, "show", collision["target_commit"]+":"+relative), "VERIFIER_NOT_COMMITTED")
    require(git(root, "rev-parse", "HEAD").strip().decode() == collision["target_commit"] and
            git(root, "status", "--porcelain", "--untracked-files=no") == b"", "TARGET_CHANGED_DURING_VERIFICATION")
    return {"schema": "cwc-source-custody-independent-verification-v1", "status": "METADATA_AND_CURRENT_TREE_RECONSTRUCTED",
            "receipt_sha256": sha(raw), "source_count": len(source_ids), "cohort_records": len(needles),
            "shared_components": ["FROZEN_SOURCE_INTAKE_AND_CONTRACT", "ORIGINAL_BOUNDED_ARCHIVE_EXPANSION"],
            "independent_external_replication_performed": False, **attribution, **collision, **AUTHORITY}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "cache", "receipt", "historical-zip", "acquisition", "out"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.out.exists() and not args.out.is_symlink(), "VERIFICATION_OUTPUT_EXISTS")
        result = verify(args.root, args.cache, args.receipt, args.historical_zip, args.acquisition)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as handle:
            handle.write(canonical(result).decode()+"\n")
    except (ValueError, OSError, KeyError, TypeError, EOFError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "VERIFICATION_BLOCKED", "failure_type": type(exc).__name__, **AUTHORITY}, sort_keys=True))
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
