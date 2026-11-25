"""Metadata-only source custody for Q2b; no source or scientific admission.

URLs and cohort identities in this governance receipt must never become model
features. An inventory of source metadata is not verification of source rights.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.parse import parse_qs, unquote, urlsplit
import zipfile

from experiments.cwc_closure import preflight as binding
from experiments.cwc_source_admission import acquisition, collision_delta
from experiments.real_transfer_01 import contract
from experiments.real_transfer_01 import source_intake as intake

COHORT_NAMES = ("CALIBRATION", "PRIMARY", "REPLICATION")
MAX_ACQUISITION_RECEIPT = 1024**2
MAX_CUSTODY_RECEIPT = 64 * 1024**2
MAX_URL_BYTES = 16384
SHA256 = re.compile(r"[0-9a-f]{64}")
BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
AUTHORITY = {
    "scientific_verdict": "NOT_TESTED",
    "scientific_promotion_authorized": False,
    "model_execution_authorized": False,
    "source_action_authorized": False,
    "source_manifest_admitted": False,
    "data_terms_verified": False,
    "use_context_verified": False,
    "real_model_execution": "NOT_RUN",
    "independent_external_replication": "NOT_TESTED",
}


class CustodyError(ValueError):
    """An integrity failure, not a negative scientific result."""


def require(condition, code):
    if not condition:
        raise CustodyError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def attribution_for_value(value, source_field):
    """Describe an observed URL or /wiki/ key without guessing a page title.

    This performs only structural validation. It never fetches an article,
    authenticates a revision, inspects notices or establishes permission.
    """
    require(type(source_field) is str and bool(source_field), "SOURCE_FIELD_SCHEMA")
    is_text = type(value) is str
    raw = value.encode("utf-8") if is_text else canonical(value)
    result = {
        "source_field": source_field,
        "source_value_sha256": digest(raw),
        "source_value_type": "string" if is_text else "nonstring",
        "url": None,
        "url_origin": "UNRESOLVED",
        "structural_url_valid": False,
        "http_fetch_performed": False,
        "provenance_verified": False,
        "historical_revision_id": None,
        "imported_notices_reviewed": False,
    }
    if (not is_text or not raw or len(raw) > MAX_URL_BYTES or
            any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value) or
            "\\" in value or BAD_PERCENT.search(value)):
        result["unresolved_reason"] = "MISSING_OR_MALFORMED_SOURCE_URL"
        return result
    derived = value.startswith("/wiki/")
    candidate = "https://en.wikipedia.org"+value if derived else value
    try:
        parsed = urlsplit(candidate)
        host = parsed.hostname
        port = parsed.port
        decoded = unquote(candidate)
        valid = (parsed.scheme in ("http", "https") and bool(parsed.netloc) and
                 host is not None and parsed.username is None and
                 parsed.password is None and "@" not in parsed.netloc and
                 (port is None or 0 < port <= 65535) and
                 not any(ord(ch) < 32 or ord(ch) == 127 for ch in decoded))
        if valid:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                ascii_host = host.encode("idna").decode("ascii")
                labels = ascii_host.rstrip(".").split(".")
                valid = (len(ascii_host) <= 253 and len(labels) >= 2 and
                         all(HOST_LABEL.fullmatch(label) is not None for label in labels))
        if derived:
            valid = valid and parsed.path.startswith("/wiki/") and len(parsed.path) > 6
            # A /wiki/ article key cannot smuggle a different navigation target.
            path_parts = unquote(parsed.path).split("/")[2:]
            valid = valid and bool(path_parts) and all(part not in ("", ".", "..")
                                                       for part in path_parts)
        if not valid:
            raise ValueError("invalid source URL")
        oldids = parse_qs(parsed.query, keep_blank_values=True).get("oldid", [])
        if (len(oldids) == 1 and oldids[0].isascii() and
                oldids[0].isdigit() and int(oldids[0]) > 0):
            result["historical_revision_id"] = oldids[0]
    except (ValueError, UnicodeError):
        result["unresolved_reason"] = "INVALID_OR_AMBIGUOUS_SOURCE_URL"
        return result
    result.update({"url": candidate,
                   "url_origin": ("MECHANICALLY_DERIVED_WIKIPEDIA_PATH" if derived
                                  else "SOURCE_ABSOLUTE_URL"),
                   "structural_url_valid": True})
    return result


def join_cohort_records(records_by_hash, cohorts, *, expected_counts):
    """Join exact ordered governance identities to actual source records.

    The returned raw record is internal only; callers project it into metadata
    before serializing a receipt. The expected counts are frozen in production.
    """
    require(type(records_by_hash) is dict and type(cohorts) is dict and
            type(expected_counts) is dict and set(cohorts) == set(COHORT_NAMES) ==
            set(expected_counts), "COHORT_JOIN_SCHEMA")
    joined = []
    seen = set()
    for name in COHORT_NAMES:
        group = cohorts[name]
        count = expected_counts[name]
        require(type(count) is int and count > 0 and type(group) is dict and
                set(group) == {"count", "cohort_sha256", "record_hashes"},
                "COHORT_JOIN_GROUP_SCHEMA")
        hashes = group["record_hashes"]
        require(type(group["count"]) is int and group["count"] == count and
                type(hashes) is list and len(hashes) == count and
                all(type(h) is str and SHA256.fullmatch(h) is not None for h in hashes),
                "COHORT_JOIN_COUNT_OR_HASH")
        require(hashes == sorted(hashes) and len(set(hashes)) == len(hashes) and
                not seen.intersection(hashes), "COHORT_JOIN_ORDER_OR_OVERLAP")
        require(group["cohort_sha256"] == digest("\n".join(hashes).encode("utf-8")),
                "COHORT_JOIN_DIGEST")
        for identity in hashes:
            require(identity in records_by_hash, "COHORT_JOIN_MISSING_RECORD")
            joined.append({"cohort": name, "record_hash": identity,
                           "record": records_by_hash[identity]})
        seen.update(hashes)
    return joined


def checked_member_metadata(meta, expected_name):
    require(type(meta) is dict and set(meta) == {"member", "byte_length", "sha256"} and
            meta["member"] == expected_name and type(meta["byte_length"]) is int and
            0 < meta["byte_length"] <= intake.MAX_ENTRY and type(meta["sha256"]) is str and
            SHA256.fullmatch(meta["sha256"]) is not None, "LINKED_MEMBER_METADATA")
    return dict(meta)


def table_inventory(key, table, docs, table_meta, request_meta):
    """Inventory every model-visible request_tok entry, including unlinked ones."""
    intake.table_key(key)
    link_count = intake.validate_modalities(table, docs, key)
    links = {link for row in [table["header"], *table["data"]]
             for cell in row for link in cell[1]}
    passages = []
    for source_key, passage in sorted(docs.items()):
        raw = passage.encode("utf-8")
        passages.append({
            "key_sha256": digest(source_key.encode("utf-8")),
            "passage_byte_length": len(raw),
            "passage_sha256": digest(raw),
            "attribution": attribution_for_value(source_key, "request_tok.key"),
        })
    require(len(passages) == len(docs) and
            len({item["key_sha256"] for item in passages}) == len(docs),
            "INCOMPLETE_PASSAGE_INVENTORY")
    return {
        "table_id_sha256": digest(key.encode("utf-8")),
        "table_member": checked_member_metadata(
            table_meta, f"{intake.WIKI_PREFIX}/tables_tok/{key}.json"),
        "request_member": checked_member_metadata(
            request_meta, f"{intake.WIKI_PREFIX}/request_tok/{key}.json"),
        "table_attribution": attribution_for_value(table.get("url"), "table.url"),
        "passage_count": len(passages),
        "table_cell_link_count": link_count,
        "unreferenced_passage_count": len(set(docs)-links),
        "passages": passages,
    }


def hybrid_inventory(cache, projection):
    records, _ = intake.exact_blob(cache/"hybridqa_dev.json", 4*1024**2,
                                   intake.HQ_BLOB, intake.HQ_SHA256)
    by_hash = {}
    for record in records:
        require(type(record) is dict, "HQ_RECORD_SCHEMA")
        fields = ("question_id", "question", "table_id", "answer-text")
        require(all(type(record.get(key)) is str and record[key].strip() for key in fields),
                "HQ_RECORD_IDENTITY")
        identity = digest("\n".join(record[key] for key in fields).encode("utf-8"))
        require(identity not in by_hash, "HQ_DUPLICATE_RECORD")
        by_hash[identity] = record
    joined = join_cohort_records(by_hash, projection["cohorts"]["HybridQA"],
                                expected_counts=binding.COHORT_COUNTS["HybridQA"])
    table_ids = sorted({intake.table_key(item["record"]["table_id"]) for item in joined})
    tables = []
    table_material = {}
    usage = [0]
    with zipfile.ZipFile(cache/"wikitable_links.zip") as archive:
        index = intake.archive_index(archive)
        for key in table_ids:
            table, table_meta = intake.member(
                archive, index, f"{intake.WIKI_PREFIX}/tables_tok/{key}.json", usage)
            docs, request_meta = intake.member(
                archive, index, f"{intake.WIKI_PREFIX}/request_tok/{key}.json", usage)
            inventory = table_inventory(key, table, docs, table_meta, request_meta)
            tables.append(inventory)
            table_material[key] = (table, docs)
    relations = []
    for item in joined:
        record = item["record"]
        key = record["table_id"]
        table, docs = table_material[key]
        actual = contract.make_hybridqa_case(record, table_payload=table, text_payload=docs)
        require(actual.record_hash == item["record_hash"], "HQ_RECORD_REJOIN_MISMATCH")
        relations.append({"cohort": item["cohort"], "record_hash": item["record_hash"],
                          "table_id_sha256": digest(key.encode("utf-8"))})
    require(len(relations) == 576 and len({row["record_hash"] for row in relations}) == 576,
            "HQ_SELECTED_RECORD_ROSTER")
    return {"record_count": len(relations), "records": relations,
            "distinct_table_count": len(tables), "tables": tables,
            "selected_member_bytes": usage[0],
            "passage_entry_count": sum(item["passage_count"] for item in tables),
            "unreferenced_passage_count": sum(item["unreferenced_passage_count"] for item in tables)}


def averitec_inventory(cache, projection):
    records, _ = intake.exact_blob(cache/"averitec_dev.json", 4*1024**2,
                                   intake.AV_BLOB)
    by_hash = {}
    for record in records:
        case = contract.make_averitec_case(record)
        require(case.record_hash not in by_hash, "AV_DUPLICATE_RECORD")
        by_hash[case.record_hash] = record
    joined = join_cohort_records(by_hash, projection["cohorts"]["AVeriTeC"],
                                expected_counts=binding.COHORT_COUNTS["AVeriTeC"])
    inventory = []
    for item in joined:
        urls = []
        for question_index, question in enumerate(item["record"]["questions"]):
            for answer_index, answer in enumerate(question["answers"]):
                urls.append({"question_index": question_index, "answer_index": answer_index,
                             "sources": [attribution_for_value(answer.get(field), field)
                                         for field in ("source_url", "cached_source_url")]})
        inventory.append({"cohort": item["cohort"], "record_hash": item["record_hash"],
                          "evidence_sources": urls})
    require(len(inventory) == 500, "AV_SELECTED_RECORD_ROSTER")
    return {"record_count": len(inventory), "records": inventory,
            "evidence_answer_count": sum(len(item["evidence_sources"]) for item in inventory)}


def read_acquisition(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and
                0 < before.st_size <= MAX_ACQUISITION_RECEIPT, "ACQUISITION_RECEIPT_FILE")
        raw = handle.read(MAX_ACQUISITION_RECEIPT+1)
        after = os.fstat(handle.fileno())
    require(len(raw) == before.st_size == after.st_size and
            before.st_mtime_ns == after.st_mtime_ns and
            before.st_ctime_ns == after.st_ctime_ns, "ACQUISITION_RECEIPT_CHANGED")
    value = intake.parse(raw)
    require(type(value) is dict, "ACQUISITION_RECEIPT_SCHEMA")
    return value, raw


def attribution_summary(hybridqa, averitec):
    values = []
    missing_evidence_urls = 0
    for table in hybridqa["tables"]:
        values.append(table["table_attribution"])
        values.extend(item["attribution"] for item in table["passages"])
    for record in averitec["records"]:
        for evidence in record["evidence_sources"]:
            values.extend(evidence["sources"])
            if not any(item["structural_url_valid"] for item in evidence["sources"]):
                missing_evidence_urls += 1
    return {"url_metadata_entries": len(values),
            "url_origins": dict(sorted(Counter(item["url_origin"] for item in values).items())),
            "unresolved_by_source_field": dict(sorted(Counter(
                item["source_field"] for item in values if not item["structural_url_valid"]).items())),
            "averitec_evidence_answers_without_structural_source_url": missing_evidence_urls,
            "url_gaps_are_scientific_rejection_thresholds": False,
            "entries_with_observed_oldid": sum(item["historical_revision_id"] is not None
                                               for item in values),
            "article_http_fetches": 0, "verified_revision_provenance": 0,
            "reviewed_imported_content_notices": 0}


def audit(root, cache, acquisition_path, historical_zip, target_ref="HEAD"):
    receipt, raw = read_acquisition(acquisition_path)
    observed = acquisition.validate_receipt(cache, receipt)
    projection = binding.projection_from_receipt(intake.analyze(cache))
    hybridqa = hybrid_inventory(cache, projection)
    averitec = averitec_inventory(cache, projection)
    delta = collision_delta.audit_delta(root, cache, historical_zip, target_ref=target_ref)
    rechecked = acquisition.validate_receipt(cache, receipt)
    require(canonical(observed) == canonical(rechecked), "SOURCE_ACQUISITION_CHANGED")
    result = {
        "schema": "cwc-source-custody-v1",
        "status": "SOURCE_CUSTODY_RECONSTRUCTED_ADMISSION_BLOCKED",
        "acquisition_receipt_sha256": digest(raw),
        "acquisition": observed,
        "source_projection": projection,
        "source_projection_sha256": digest(binding.canonical(projection)),
        "hybridqa_inventory": hybridqa,
        "averitec_inventory": averitec,
        "attribution_summary": attribution_summary(hybridqa, averitec),
        "repository_collision_binding": delta,
        "governance_metadata_is_model_input": False,
        "source_text_or_gold_published": False,
        "blockers": ["SOURCE_MANIFEST_NOT_ADMITTED", "NONCOMMERCIAL_USE_CONTEXT_UNESTABLISHED",
                     "ITEM_LEVEL_ATTRIBUTION_AND_IMPORTED_NOTICE_REVIEW_PENDING",
                     "MODEL_MATERIALS_AND_EXECUTION_PREREQUISITES_PENDING"],
        "limitations": ["REVISION_PROVENANCE_UNVERIFIED",
                        "ABSENT_HISTORICAL_OLDID_IS_NOT_AN_ADMISSION_THRESHOLD",
                        "STRUCTURAL_URL_VALIDITY_IS_NOT_HTTP_OR_NOTICE_VERIFICATION"],
        "attribution": ["Schlichtkrull, Guo and Vlachos (2023): AVeriTeC",
                        "Chen et al. (2020): HybridQA", "Wikipedia contributors"],
        "limits": {"max_url_bytes": MAX_URL_BYTES,
                   "max_custody_receipt_bytes": MAX_CUSTODY_RECEIPT,
                   "source_and_archive_limits": "UNCHANGED_SOURCE_INTAKE_LIMITS"},
        **AUTHORITY,
    }
    require(len(canonical(result)) <= MAX_CUSTODY_RECEIPT, "CUSTODY_RECEIPT_BYTE_BUDGET")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--acquisition", type=Path, required=True)
    parser.add_argument("--historical-zip", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.receipt.exists() and not args.receipt.is_symlink(),
                "RECEIPT_ALREADY_EXISTS")
        result = audit(args.root, args.cache, args.acquisition, args.historical_zip)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open("x", encoding="utf-8") as handle:
            handle.write(canonical(result).decode("utf-8")+"\n")
    except (ValueError, OSError, KeyError, TypeError, EOFError,
            subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(json.dumps({"schema": "cwc-source-custody-v1", "status": "NOT_TESTED",
                          "integrity_failure": type(exc).__name__, **AUTHORITY}, sort_keys=True))
        return 3
    print(json.dumps({"status": result["status"],
                      "record_count": (result["hybridqa_inventory"]["record_count"] +
                                       result["averitec_inventory"]["record_count"]),
                      "attribution_summary": result["attribution_summary"], **AUTHORITY}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
