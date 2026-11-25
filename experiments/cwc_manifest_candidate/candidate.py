"""Assemble an inert source-manifest candidate from independently verified bytes.

The envelope and its null-license inner draft are deliberately inadmissible to
the original execution gate. This module never adopts a canonical manifest.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import zipfile

from experiments.cwc_closure import preflight as binding
from experiments.cwc_source_admission import verify_receipt as custody_verifier
from experiments.real_transfer_01 import contract, preflight, source_intake as intake

SCHEMA = "cwc-source-manifest-candidate-v1"
CACHE_NAME = "source-cache-candidate"
MODULE_PATH = "experiments/cwc_manifest_candidate/candidate.py"
FROZEN_PROTOCOL_COMMIT = "b0f24b1da0723bbfa6ff1af66af1d55a14ceeddb"
MAX_CANDIDATE = 8 * 1024**2
MAX_CUSTODY = 64 * 1024**2
MAX_EVIDENCE = 8 * 1024**2
HISTORICAL_ZIP_BYTES = 579686
ENVELOPE_KEYS = {"schema", "status", "candidate_fields", "publisher_declarations",
                 "evidence_bindings", "scope", "admission", "authority"}
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
PUBLISHER_DECLARATIONS = [
    {
        "source_name": "averitec_dev.json",
        "publisher": "Schlichtkrull, Guo and Vlachos (2023)",
        "declared_licenses": ["CC-BY-NC-4.0"],
        "references": ["https://fever.ai/dataset/averitec.html",
                       "https://creativecommons.org/licenses/by-nc/4.0/legalcode.en"],
        "scope": "DATASET_PUBLISHER_DECLARATION_NOT_USE_CONTEXT_OR_THIRD_PARTY_CLEARANCE",
    },
    {
        "source_name": "hybridqa_dev.json",
        "publisher": "Chen et al. (2020)",
        "declared_licenses": ["CC-BY-4.0"],
        "references": ["https://hybridqa.github.io/about.html",
                       "https://creativecommons.org/licenses/by/4.0/legalcode.en"],
        "scope": "DATASET_DECLARATION_DOES_NOT_OVERRIDE_THIRD_PARTY_WIKIPEDIA_TERMS_OR_CLEAR_DATA_UNDER_MIT_CODE_LICENSE",
    },
    {
        "source_name": "wikitable_links.zip",
        "publisher": "Wikipedia contributors",
        "declared_licenses": ["CC-BY-SA-3.0", "GFDL"],
        "references": ["https://foundation.wikimedia.org/w/index.php?oldid=98524&title=Policy:Terms_of_Use"],
        "scope": "HISTORICAL_COMMUNITY_TEXT_DEFAULTS_SUBJECT_TO_IMPORTED_CONTENT_NOTICES_AND_EXCEPTIONS",
    },
]


class CandidateError(ValueError):
    """Candidate assembly is blocked; no admission or scientific verdict follows."""


def require(condition, code):
    if not condition:
        raise CandidateError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_path(value):
    try:
        raw = os.fspath(value)
    except TypeError as exc:
        raise CandidateError("PATH_SCHEMA") from exc
    require(type(raw) is str and 0 < len(raw) <= 4096 and
            "\\" not in raw and "\x00" not in raw and not raw.startswith("//"), "PATH_SCHEMA")
    parsed = PurePosixPath(raw)
    require(parsed.is_absolute() and parsed.as_posix() == raw and
            all(part not in (".", "..") for part in parsed.parts), "PATH_ALIAS_OR_TRAVERSAL")
    return Path(raw)


def existing(path, *, directory):
    path = canonical_path(path)
    current = Path("/")
    require(stat.S_ISDIR(current.lstat().st_mode), "ROOT_DIRECTORY_TYPE")
    for index, part in enumerate(path.parts[1:]):
        current = current / part
        info = current.lstat()
        is_directory = directory or index < len(path.parts[1:])-1
        if is_directory:
            require(stat.S_ISDIR(info.st_mode), "PATH_COMPONENT_NOT_DIRECTORY")
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                    "INPUT_NOT_SINGLE_REGULAR_FILE")
    if not directory:
        require(path != Path("/"), "INPUT_NOT_SINGLE_REGULAR_FILE")
    return path


def open_parent(path):
    """Walk directories without following symlinks before an fd-relative open."""
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def read_regular(path, limit):
    require(type(limit) is int and limit > 0, "INPUT_LIMIT")
    path = existing(path, directory=False)
    parent = open_parent(path)
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                0 < before.st_size <= limit, "INPUT_FILE_OR_BUDGET")
        raw = handle.read(limit+1)
        after = os.fstat(handle.fileno())
    require(len(raw) == before.st_size == after.st_size and after.st_nlink == 1 and
            (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns), "INPUT_CHANGED")
    return raw


def validate_cache(root, cache):
    root = existing(root, directory=True)
    cache = existing(cache, directory=True)
    require(cache == root / CACHE_NAME, "SOURCE_CACHE_SUBSTITUTION")
    require({entry.name for entry in cache.iterdir()} == {row[1] for row in intake.SOURCES},
            "SOURCE_CACHE_ROSTER")
    for _, name, _, _, _, limit in intake.SOURCES:
        path = existing(cache / name, directory=False)
        require(0 < path.lstat().st_size <= limit, "SOURCE_BYTE_BUDGET")
    return cache


def check_output(root, out):
    root = existing(root, directory=True)
    out = canonical_path(out)
    require(out.name != "SOURCE_MANIFEST.json", "RESERVED_CANONICAL_MANIFEST_BASENAME")
    require(not out.is_relative_to(root), "OUTPUT_WITHIN_REPOSITORY")
    existing(out.parent, directory=True)
    try:
        out.lstat()
    except FileNotFoundError:
        return out
    raise CandidateError("OUTPUT_ALREADY_EXISTS")


def write_exclusive(root, out, payload):
    out = check_output(root, out)
    raw = canonical(payload) + b"\n"
    require(0 < len(raw) <= MAX_CANDIDATE, "CANDIDATE_BYTE_BUDGET")
    parent = open_parent(out)
    try:
        descriptor = os.open(out.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(descriptor, "wb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "OUTPUT_FILE_TYPE")
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    require(result.returncode == 0, "GIT_BINDING_FAILED")
    return result.stdout


def assert_target(root):
    root = existing(root, directory=True)
    commit = git(root, "rev-parse", "HEAD").strip().decode("ascii")
    tree = git(root, "rev-parse", "HEAD^{tree}").strip().decode("ascii")
    require(git(root, "status", "--porcelain", "--untracked-files=no") == b"",
            "DIRTY_TRACKED_TARGET")
    git(root, "merge-base", "--is-ancestor", FROZEN_PROTOCOL_COMMIT, commit)
    own_path = existing(root / MODULE_PATH, directory=False)
    require(Path(__file__).resolve() == own_path, "EXECUTED_ASSEMBLER_PATH")
    require(read_regular(own_path, MAX_EVIDENCE) == git(root, "show", commit+":"+MODULE_PATH),
            "EXECUTED_ASSEMBLER_NOT_COMMITTED")
    return {"target_commit": commit, "target_tree": tree}


def assemble_fields(projection, trace, repository_collision_count):
    """Pure inert field projection; only build() establishes authentic evidence."""
    require(type(repository_collision_count) is int and repository_collision_count >= 0,
            "COLLISION_COUNT_SCHEMA")
    require(type(projection) is dict and set(projection) == {"sources", "cohorts"},
            "SOURCE_PROJECTION_SCHEMA")
    require(type(projection["sources"]) is list and len(projection["sources"]) == 3 and
            type(trace) is dict and type(trace.get("sources")) is list and
            len(trace["sources"]) == 3, "SOURCE_PROJECTION_ROSTER")
    observed = {row["name"]: row for row in trace["sources"]}
    expected_names = {row[1] for row in intake.SOURCES}
    require(len(observed) == 3 and set(observed) == expected_names and
            {row["name"] for row in projection["sources"]} == expected_names,
            "SOURCE_PROJECTION_IDENTITY")
    require(binding.cohort_shape(projection["cohorts"]) == 1076, "ORDERED_COHORT_ROSTER")
    sources = []
    for source in sorted(projection["sources"], key=lambda row: row["name"]):
        name = source["name"]
        item = {key: source[key] for key in
                ("family", "canonical_url", "ref", "byte_length", "sha256")}
        item.update({"upstream_commit_sha": source["ref"], "path": CACHE_NAME+"/"+name,
                     "acquired_at": observed[name]["completed_at"], "license": None})
        if name != "wikitable_links.zip":
            item["git_blob"] = source["git_blob"]
        sources.append(item)
    return {"experiment": "REAL-TRANSFER-01", "sources": sources,
            "cohorts": deepcopy(projection["cohorts"]),
            "collision_audit": {"repository_exact_collision_count": repository_collision_count,
                                "training_exact_collision_count": None,
                                "training_collision_audit_complete": False}}


def require_inert(candidate):
    require(type(candidate) is dict and set(candidate) == ENVELOPE_KEYS,
            "CANDIDATE_ENVELOPE_SCHEMA")
    for value in (candidate, candidate["candidate_fields"]):
        try:
            preflight.validate_source_manifest(value)
        except contract.ContractError:
            continue
        raise CandidateError("CANDIDATE_ACCEPTED_AS_CANONICAL_MANIFEST")


def build(root, cache, acquisition_path, custody_path, verification_path, historical_zip):
    root = existing(root, directory=True)
    cache = validate_cache(root, cache)
    target = assert_target(root)
    paths = {"acquisition_receipt": acquisition_path, "custody_receipt": custody_path,
             "verification_receipt": verification_path}
    limits = {"acquisition_receipt": MAX_EVIDENCE, "custody_receipt": MAX_CUSTODY,
              "verification_receipt": MAX_EVIDENCE}
    raw = {name: read_regular(path, limits[name]) for name, path in paths.items()}
    values = {name: intake.parse(value) for name, value in raw.items()}
    require(all(type(value) is dict for value in values.values()), "EVIDENCE_OBJECT_REQUIRED")
    history_raw = read_regular(historical_zip, HISTORICAL_ZIP_BYTES)
    require(len(history_raw) == HISTORICAL_ZIP_BYTES and digest(history_raw) == custody_verifier.ZIP_SHA,
            "HISTORICAL_ZIP_IDENTITY")
    fresh = custody_verifier.verify(root, cache, Path(custody_path), Path(historical_zip),
                                    Path(acquisition_path))
    require(canonical(values["verification_receipt"]) == canonical(fresh),
            "SUPPLIED_VERIFICATION_NOT_FRESH_RECONSTRUCTION")
    require(fresh["receipt_sha256"] == digest(raw["custody_receipt"]) and
            {key: fresh[key] for key in target} == target, "EVIDENCE_TARGET_MISMATCH")
    custody = values["custody_receipt"]
    projection = binding.reconstruct(cache)
    require(binding.canonical(projection) == binding.canonical(custody["source_projection"]),
            "INDEPENDENT_SOURCE_PROJECTION_MISMATCH")
    fields = assemble_fields(projection, values["acquisition_receipt"],
                             custody["repository_collision_binding"]["repository_exact_collision_count"])
    require(binding.compare_source_declaration(root, cache, fields, projection),
            "CANONICAL_SOURCE_FIELDS_NOT_BOUND")
    evidence = {name: {"byte_length": len(value), "sha256": digest(value)}
                for name, value in raw.items()}
    evidence.update({
        "source_projection_sha256": digest(binding.canonical(projection)),
        "attribution_inventory_sha256": digest(canonical({
            "hybridqa_inventory": custody["hybridqa_inventory"],
            "averitec_inventory": custody["averitec_inventory"]})),
        "historical_zip_sha256": digest(history_raw),
        "current_tree": {**target, "target_roster_sha256": fresh["target_roster_sha256"]},
        "source_cache_relative_path": CACHE_NAME,
        "canonical_source_fields_bound": True,
    })
    candidate = {
        "schema": SCHEMA,
        "status": "ASSEMBLED_NOT_ADMITTED",
        "candidate_fields": fields,
        "publisher_declarations": deepcopy(PUBLISHER_DECLARATIONS),
        "evidence_bindings": evidence,
        "scope": {"candidate_is_tracked": False, "canonical_manifest_written": False,
                  "raw_source_or_gold_published": False, "model_inputs_produced": False,
                  "training_corpus_provenance": "UNKNOWN",
                  "later_manifest_commit_requires_new_tree_audit": True},
        "admission": {"use_context": "UNRESOLVED", "data_terms": "NOT_ADMITTED",
                      "required_next": ["ESTABLISH_ACTUAL_USE_PURPOSE",
                                        "COMPLETE_CONTEXT_APPLICABLE_TERMS_REVIEW",
                                        "COMMIT_AND_REVALIDATE_SOURCE_MANIFEST"],
                      "missing_oldid_is_rejection_threshold": False,
                      "universal_article_clearance_required": False},
        "authority": deepcopy(AUTHORITY),
    }
    require_inert(candidate)
    require(len(canonical(candidate))+1 <= MAX_CANDIDATE, "CANDIDATE_BYTE_BUDGET")
    for name, path in paths.items():
        require(read_regular(path, limits[name]) == raw[name], "EVIDENCE_CHANGED_DURING_BUILD")
    require(read_regular(historical_zip, HISTORICAL_ZIP_BYTES) == history_raw,
            "HISTORICAL_ZIP_CHANGED_DURING_BUILD")
    validate_cache(root, cache)
    require(binding.canonical(binding.reconstruct(cache)) == binding.canonical(projection),
            "SOURCE_CHANGED_DURING_BUILD")
    require(assert_target(root) == target, "CODE_TARGET_CHANGED_DURING_BUILD")
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "cache", "acquisition", "custody", "verification", "historical-zip", "out"):
        parser.add_argument("--"+name, required=True)
    args = parser.parse_args()
    try:
        check_output(args.root, args.out)
        candidate = build(args.root, args.cache, args.acquisition, args.custody,
                          args.verification, args.historical_zip)
        write_exclusive(args.root, args.out, candidate)
    except (ValueError, OSError, KeyError, TypeError, EOFError,
            subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "CANDIDATE_ASSEMBLY_BLOCKED", "failure_type": type(exc).__name__,
                          "authority": AUTHORITY}, sort_keys=True))
        return 3
    print(json.dumps({"status": candidate["status"], "schema": SCHEMA,
                      "source_count": len(candidate["candidate_fields"]["sources"]),
                      "candidate_bytes": len(canonical(candidate))+1,
                      "authority": AUTHORITY}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
