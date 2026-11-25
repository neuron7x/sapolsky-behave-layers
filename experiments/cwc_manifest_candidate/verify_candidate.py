"""Independent inert-candidate reconstruction; never source admission."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess

from experiments.cwc_closure import preflight as binding
from experiments.cwc_source_admission import acquisition
from experiments.cwc_source_admission import verify_receipt as custody_verifier
from experiments.real_transfer_01 import contract, preflight, source_intake

MAX_JSON = 8 * 1024**2
MAX_CUSTODY = 64 * 1024**2
CACHE_NAME = "source-cache-candidate"
FROZEN_PROTOCOL_COMMIT = "b0f24b1da0723bbfa6ff1af66af1d55a14ceeddb"
AUTHORITY = {
    "scientific_verdict": "NOT_TESTED", "scientific_promotion_authorized": False,
    "model_execution_authorized": False, "source_action_authorized": False,
    "source_manifest_admitted": False, "data_terms_verified": False,
    "use_context_verified": False, "real_model_execution": "NOT_RUN",
    "independent_external_replication": "NOT_TESTED",
}
PUBLISHER_DECLARATIONS = [
    {"source_name": "averitec_dev.json", "publisher": "Schlichtkrull, Guo and Vlachos (2023)",
     "declared_licenses": ["CC-BY-NC-4.0"],
     "references": ["https://fever.ai/dataset/averitec.html",
                    "https://creativecommons.org/licenses/by-nc/4.0/legalcode.en"],
     "scope": "DATASET_PUBLISHER_DECLARATION_NOT_USE_CONTEXT_OR_THIRD_PARTY_CLEARANCE"},
    {"source_name": "hybridqa_dev.json", "publisher": "Chen et al. (2020)",
     "declared_licenses": ["CC-BY-4.0"],
     "references": ["https://hybridqa.github.io/about.html",
                    "https://creativecommons.org/licenses/by/4.0/legalcode.en"],
     "scope": "DATASET_DECLARATION_DOES_NOT_OVERRIDE_THIRD_PARTY_WIKIPEDIA_TERMS_OR_CLEAR_DATA_UNDER_MIT_CODE_LICENSE"},
    {"source_name": "wikitable_links.zip", "publisher": "Wikipedia contributors",
     "declared_licenses": ["CC-BY-SA-3.0", "GFDL"],
     "references": ["https://foundation.wikimedia.org/w/index.php?oldid=98524&title=Policy:Terms_of_Use"],
     "scope": "HISTORICAL_COMMUNITY_TEXT_DEFAULTS_SUBJECT_TO_IMPORTED_CONTENT_NOTICES_AND_EXCEPTIONS"},
]
SCOPE = {"candidate_is_tracked": False, "canonical_manifest_written": False,
         "raw_source_or_gold_published": False, "model_inputs_produced": False,
         "training_corpus_provenance": "UNKNOWN", "later_manifest_commit_requires_new_tree_audit": True}
ADMISSION = {"use_context": "UNRESOLVED", "data_terms": "NOT_ADMITTED",
             "required_next": ["ESTABLISH_ACTUAL_USE_PURPOSE", "COMPLETE_CONTEXT_APPLICABLE_TERMS_REVIEW",
                               "COMMIT_AND_REVALIDATE_SOURCE_MANIFEST"],
             "missing_oldid_is_rejection_threshold": False, "universal_article_clearance_required": False}


class CandidateVerificationError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise CandidateVerificationError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def same(actual, expected, code):
    require(canonical(actual) == canonical(expected), code)


def checked_path(path, *, missing_leaf=False):
    raw = os.fspath(path)
    require(type(raw) is str and 0 < len(raw) <= 4096 and "\\" not in raw and
            "\x00" not in raw and not raw.startswith("//"), "PATH_SCHEMA")
    parsed = PurePosixPath(raw)
    require(parsed.is_absolute() and parsed.as_posix() == raw and ".." not in parsed.parts, "PATH_ALIAS")
    path = Path(raw)
    current = Path(path.anchor)
    for number, part in enumerate(path.parts[1:]):
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            require(missing_leaf and number == len(path.parts)-2, "MISSING_PATH_COMPONENT")
            return path
        require(not stat.S_ISLNK(mode), "SYMLINK_COMPONENT")
        if number < len(path.parts)-2:
            require(stat.S_ISDIR(mode), "NON_DIRECTORY_PARENT")
    return path


def parent_descriptor(path):
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def read_regular(path, limit):
    path = checked_path(path)
    require(type(limit) is int and limit > 0, "INPUT_BYTE_BUDGET")
    parent = parent_descriptor(path)
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                0 < before.st_size <= limit, "INPUT_FILE_IDENTITY")
        raw = handle.read(limit+1)
        after = os.fstat(handle.fileno())
    require(len(raw) == before.st_size == after.st_size and before.st_nlink == after.st_nlink and
            (before.st_mtime_ns, before.st_ctime_ns, before.st_ino, before.st_dev) ==
            (after.st_mtime_ns, after.st_ctime_ns, after.st_ino, after.st_dev), "INPUT_CHANGED")
    return raw


def validate_cache(root, cache):
    root, cache = checked_path(root), checked_path(cache)
    require(root.is_dir() and cache.is_dir() and cache == root/CACHE_NAME, "CACHE_PATH_BINDING")
    require({path.name for path in cache.iterdir()} == {row[1] for row in source_intake.SOURCES}, "CACHE_ROSTER")
    for _, name, _, _, _, limit in source_intake.SOURCES:
        path = checked_path(cache/name)
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= limit,
                "CACHE_FILE_IDENTITY")
    return cache


def outside_root(root, path, *, absent=False):
    root, path = checked_path(root), checked_path(path, missing_leaf=absent)
    require(not path.is_relative_to(root), "OUTPUT_INSIDE_REPOSITORY")
    require(path.name != "SOURCE_MANIFEST.json", "CANONICAL_MANIFEST_OUTPUT_FORBIDDEN")
    if absent:
        require(not path.exists(), "OUTPUT_EXISTS")
    return path


def write_exclusive(root, out, payload):
    out = outside_root(root, out, absent=True)
    raw = canonical(payload)+b"\n"
    require(len(raw) <= MAX_JSON, "OUTPUT_BYTE_BUDGET")
    parent = parent_descriptor(out)
    try:
        descriptor = os.open(out.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(descriptor, "wb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "OUTPUT_FILE_IDENTITY")
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git(root, *arguments):
    result = subprocess.run(["git", "-C", str(root), *arguments], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False, timeout=60)
    require(result.returncode == 0, "GIT_BINDING_FAILED")
    return result.stdout


def committed_bytes(root, target, relative):
    raw = read_regular(Path(root)/relative, MAX_JSON)
    require(git(root, "show", target+":"+relative) == raw, "EXECUTED_CODE_NOT_COMMITTED")


def target_identity(root):
    require(git(root, "status", "--porcelain", "--untracked-files=no") == b"", "DIRTY_TARGET")
    target = git(root, "rev-parse", "HEAD").strip().decode("ascii")
    tree = git(root, "rev-parse", "HEAD^{tree}").strip().decode("ascii")
    git(root, "merge-base", "--is-ancestor", FROZEN_PROTOCOL_COMMIT, target)
    for relative in ("experiments/cwc_manifest_candidate/candidate.py",
                     "experiments/cwc_manifest_candidate/verify_candidate.py"):
        committed_bytes(root, target, relative)
    require(Path(__file__).resolve() == Path(root)/"experiments/cwc_manifest_candidate/verify_candidate.py",
            "EXECUTED_VERIFIER_PATH")
    return target, tree


def compare_candidate(candidate, expected):
    """Exact separately reconstructed envelope; permissive legacy flags are irrelevant."""
    same(candidate, expected, "CANDIDATE_RECONSTRUCTION_MISMATCH")
    require(len(canonical(candidate)) <= MAX_JSON, "CANDIDATE_BYTE_BUDGET")
    for value in (candidate, candidate["candidate_fields"]):
        try:
            preflight.validate_source_manifest(value)
        except contract.ContractError:
            continue
        raise CandidateVerificationError("CANDIDATE_UNEXPECTEDLY_ADMISSIBLE")


def check_verification(supplied, freshly_reconstructed):
    same(supplied, freshly_reconstructed, "UNVERIFIED_OR_SUBSTITUTED_CUSTODY_VERDICT")


def verify(root, cache, candidate_path, acquisition_path, custody_path, verification_path, historical_zip):
    root = checked_path(root)
    cache = validate_cache(root, cache)
    candidate_path = outside_root(root, candidate_path)
    target, tree = target_identity(root)
    paths = {"acquisition_receipt": acquisition_path, "custody_receipt": custody_path,
             "verification_receipt": verification_path}
    raws = {name: read_regular(path, MAX_CUSTODY if name == "custody_receipt" else MAX_JSON)
            for name, path in paths.items()}
    receipts = {name: source_intake.parse(raw) for name, raw in raws.items()}
    candidate_raw = read_regular(candidate_path, MAX_JSON)
    candidate = source_intake.parse(candidate_raw)
    historical_raw = read_regular(historical_zip, 579686)
    require(len(historical_raw) == 579686 and digest(historical_raw) == custody_verifier.ZIP_SHA,
            "HISTORICAL_ZIP_IDENTITY")
    fresh = custody_verifier.verify(root, cache, Path(custody_path), Path(historical_zip), Path(acquisition_path))
    check_verification(receipts["verification_receipt"], fresh)
    same([fresh["target_commit"], fresh["target_tree"], fresh["receipt_sha256"]],
         [target, tree, digest(raws["custody_receipt"])], "FRESH_RECEIPT_TARGET_MISMATCH")
    trace = acquisition.validate_receipt(cache, receipts["acquisition_receipt"])
    projection = binding.reconstruct(cache)
    custody = receipts["custody_receipt"]
    same(custody["source_projection"], projection, "FRESH_SOURCE_PROJECTION")
    times = {source["name"]: source["completed_at"] for source in trace["sources"]}
    sources = []
    for item in sorted(projection["sources"], key=lambda value: value["name"]):
        source = {key: item[key] for key in ("family", "canonical_url", "ref", "byte_length", "sha256")}
        source.update({"upstream_commit_sha": item["ref"], "path": CACHE_NAME+"/"+item["name"],
                       "acquired_at": times[item["name"]], "license": None})
        if item["name"] in ("averitec_dev.json", "hybridqa_dev.json"):
            source["git_blob"] = item["git_blob"]
        sources.append(source)
    fields = {"experiment": "REAL-TRANSFER-01", "sources": sources, "cohorts": projection["cohorts"],
              "collision_audit": {"repository_exact_collision_count": fresh["repository_exact_collision_count"],
                                  "training_exact_collision_count": None, "training_collision_audit_complete": False}}
    require(binding.compare_source_declaration(root, cache, fields, projection), "CANONICAL_SOURCE_BINDING")
    collision = custody["repository_collision_binding"]
    same([collision["target_commit"], collision["target_tree"]], [target, tree], "CURRENT_TREE_MISMATCH")
    evidence = {name: {"byte_length": len(raw), "sha256": digest(raw)} for name, raw in raws.items()}
    evidence.update({"source_projection_sha256": digest(binding.canonical(projection)),
                     "attribution_inventory_sha256": digest(canonical({key: custody[key] for key in
                          ("hybridqa_inventory", "averitec_inventory")})),
                     "historical_zip_sha256": digest(historical_raw),
                     "current_tree": {key: collision[key] for key in ("target_commit", "target_tree", "target_roster_sha256")},
                     "source_cache_relative_path": CACHE_NAME, "canonical_source_fields_bound": True})
    expected = {"schema": "cwc-source-manifest-candidate-v1", "status": "ASSEMBLED_NOT_ADMITTED",
                "candidate_fields": fields, "publisher_declarations": PUBLISHER_DECLARATIONS,
                "evidence_bindings": evidence, "scope": SCOPE, "admission": ADMISSION, "authority": AUTHORITY}
    compare_candidate(candidate, expected)
    for name, path in paths.items():
        require(read_regular(path, MAX_CUSTODY if name == "custody_receipt" else MAX_JSON) == raws[name], "RECEIPT_CHANGED")
    require(read_regular(candidate_path, MAX_JSON) == candidate_raw, "CANDIDATE_CHANGED")
    require(read_regular(historical_zip, 579686) == historical_raw, "HISTORICAL_ZIP_CHANGED")
    validate_cache(root, cache)
    same(acquisition.validate_receipt(cache, trace), trace, "SOURCE_BYTES_CHANGED")
    same(target_identity(root), (target, tree), "TARGET_CHANGED")
    return {"schema": "cwc-source-manifest-candidate-verification-v1", "status": "CANDIDATE_RECONSTRUCTED_NOT_ADMITTED",
            "candidate_byte_length": len(candidate_raw), "candidate_sha256": digest(candidate_raw),
            "source_count": len(sources), "cohort_records": sum(info["count"] for family in projection["cohorts"].values() for info in family.values()),
            "repository_exact_collision_count": fresh["repository_exact_collision_count"],
            "target_commit": target, "target_tree": tree, "envelope_rejected_by_original_validator": True,
            "extracted_draft_rejected_by_original_validator": True,
            "shared_base": ["FROZEN_SOURCE_CONTRACTS", "QUALIFIED_ACQUISITION", "QUALIFIED_CUSTODY_INDEPENDENT_VERIFIER"],
            **AUTHORITY}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "cache", "candidate", "acquisition", "custody", "verification", "historical-zip", "out"):
        parser.add_argument("--"+name, required=True)
    args = parser.parse_args()
    try:
        out = outside_root(args.root, args.out, absent=True)
        result = verify(args.root, args.cache, args.candidate, args.acquisition, args.custody,
                        args.verification, args.historical_zip)
        write_exclusive(args.root, out, result)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "CANDIDATE_VERIFICATION_BLOCKED", "error_type": type(error).__name__, **AUTHORITY}, sort_keys=True))
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
