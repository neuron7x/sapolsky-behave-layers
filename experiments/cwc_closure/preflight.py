"""Content-bound admission prerequisites for the frozen REAL-TRANSFER-01.

This is an additive, read-only diagnostic. It cannot run a model or issue a
scientific verdict. A source projection is not a scientific source manifest.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

from experiments.real_transfer_01 import contract as c
from experiments.real_transfer_01 import preflight as old
from experiments.real_transfer_01 import readiness
from experiments.real_transfer_01 import source_intake as intake

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = Path("experiments/real_transfer_01")
MAX_MANIFEST = 8 * 1024**2
MAX_ARTIFACT = 8 * 1024**3
MAX_TOTAL = 16 * 1024**3
MAX_CODE = 8 * 1024**2
SHA256 = re.compile(r"[0-9a-f]{64}")
FIELDS = ("weights_sha256", "tokenizer_sha256", "prompt_template_sha256",
          "calibration_procedure_sha256", "governor_parameters_sha256")
COHORT_COUNTS = {
    "AVeriTeC": {"CALIBRATION": 99, "PRIMARY": 199, "REPLICATION": 202},
    "HybridQA": {"CALIBRATION": 64, "PRIMARY": 256, "REPLICATION": 256},
}
AUTHORITY = {
    "scientific_verdict": "NOT_TESTED",
    "scientific_promotion_authorized": False,
    "model_execution_authorized": False,
    "real_model_execution": "NOT_RUN",
}


class BindingError(ValueError):
    """A pre-execution blocker, not a negative scientific result."""


def require(condition, message):
    if not condition:
        raise BindingError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hex_digest(value):
    require(type(value) is str and SHA256.fullmatch(value) is not None,
            "DIGEST_SCHEMA")
    return value


def regular(root, relative):
    """Require canonical relative path and regular, non-symlink components."""
    require(type(relative) is str and 0 < len(relative) <= 2048 and
            "\\" not in relative and "\x00" not in relative, "PATH_SCHEMA")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and path.parts and
            all(part not in (".", "..") for part in path.parts) and
            path.as_posix() == relative, "PATH_ESCAPE_OR_ALIAS")
    current = root.resolve()
    for index, part in enumerate(path.parts):
        current = current / part
        mode = current.lstat().st_mode
        if index == len(path.parts)-1:
            require(stat.S_ISREG(mode), "NONREGULAR_ARTIFACT")
        else:
            require(stat.S_ISDIR(mode), "NONREGULAR_PARENT")
    return current


def metadata(path, ceiling, expected_length=None):
    """Stream exact bytes with a size limit; no model files are executed."""
    require(type(ceiling) is int and ceiling > 0, "BYTE_CEILING")
    checksum = hashlib.sha256()
    total = 0
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= ceiling,
                "ARTIFACT_BYTE_BUDGET")
        if expected_length is not None:
            require(type(expected_length) is int and expected_length == before.st_size,
                    "ARTIFACT_LENGTH_MISMATCH")
        for block in iter(lambda: stream.read(1024**2), b""):
            total += len(block)
            require(total <= ceiling, "ARTIFACT_BYTE_BUDGET")
            checksum.update(block)
        after = os.fstat(stream.fileno())
    require(total == before.st_size == after.st_size and
            before.st_mtime_ns == after.st_mtime_ns and
            before.st_ctime_ns == after.st_ctime_ns, "ARTIFACT_CHANGED_DURING_READ")
    return {"byte_length": total, "sha256": checksum.hexdigest()}


def load_manifest(root, path):
    file = regular(root, path)
    with os.fdopen(os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "MANIFEST_FILE_TYPE")
        raw = stream.read(MAX_MANIFEST+1)
    require(0 < len(raw) <= MAX_MANIFEST, "MANIFEST_BYTE_BUDGET")
    value = intake.parse(raw)
    require(type(value) is dict, "MANIFEST_OBJECT_REQUIRED")
    return value, raw


def committed_bytes(root, path, raw):
    """Check Git object bytes, not a caller's assertion of a clean file."""
    result = subprocess.run(["git", "-C", str(root), "show", "HEAD:"+path],
                            check=False, capture_output=True, timeout=30)
    require(result.returncode == 0 and result.stdout == raw,
            "NOT_EXACT_COMMITTED_BYTES:"+path)


def cohort_shape(groups):
    require(type(groups) is dict and set(groups) == set(COHORT_COUNTS),
            "FAMILY_ROSTER")
    all_hashes = set()
    for family, sizes in COHORT_COUNTS.items():
        block = groups[family]
        require(type(block) is dict and set(block) == set(sizes), "COHORT_ROSTER")
        for name, count in sizes.items():
            info = block[name]
            require(type(info) is dict and set(info) == {
                "count", "cohort_sha256", "record_hashes"}, "COHORT_SCHEMA")
            require(type(info["count"]) is int and info["count"] == count,
                    "COHORT_COUNT")
            hashes = info["record_hashes"]
            require(type(hashes) is list and len(hashes) == count, "COHORT_HASH_ROSTER")
            for value in hashes:
                hex_digest(value)
                require(value not in all_hashes, "COHORT_DUPLICATE_OR_OVERLAP")
                all_hashes.add(value)
            require(hex_digest(info["cohort_sha256"]) == digest("\n".join(hashes).encode()),
                    "COHORT_DIGEST_MISMATCH")
    return len(all_hashes)


def projection_from_receipt(report):
    """Project a freshly reconstructed intake result, not arbitrary PASS evidence."""
    require(type(report) is dict and
            report.get("kind") == "SOURCE_INTAKE_RECEIPT_ONLY" and
            report.get("status") == "SOURCE_BYTES_AND_COHORTS_RECONSTRUCTED" and
            report.get("source_blockers") == [] and
            report.get("scientific_promotion_authorized") is False,
            "SOURCE_RECONSTRUCTION_INCOMPLETE")
    sources = report.get("sources")
    require(type(sources) is list and len(sources) == len(intake.SOURCES),
            "SOURCE_ROSTER")
    expected = {item[1]: item for item in intake.SOURCES}
    seen = set()
    projected = []
    for value in sources:
        require(type(value) is dict and type(value.get("name")) is str and
                value["name"] in expected and value["name"] not in seen,
                "SOURCE_IDENTITY")
        family, name, ref, url, _, ceiling = expected[value["name"]]
        require(value.get("family") == family and value.get("ref") == ref and
                value.get("canonical_url") == url, "UPSTREAM_IDENTITY")
        length = value.get("byte_length")
        require(type(length) is int and 0 < length <= ceiling, "SOURCE_BYTE_BUDGET")
        sha = hex_digest(value.get("sha256"))
        item = {"family": family, "name": name, "ref": ref, "canonical_url": url,
                "byte_length": length, "sha256": sha}
        blob = {"averitec_dev.json": intake.AV_BLOB,
                "hybridqa_dev.json": intake.HQ_BLOB}.get(name)
        if blob is not None:
            require(value.get("git_blob") == blob, "UPSTREAM_BLOB_MISMATCH")
            item["git_blob"] = blob
        if name == "hybridqa_dev.json":
            require(sha == intake.HQ_SHA256 and length == 1193503, "PINNED_HQ_MISMATCH")
        if name == "wikitable_links.zip":
            require(sha == intake.WIKI_SHA256 and length == 193533209, "PINNED_WIKI_MISMATCH")
        projected.append(item)
        seen.add(name)
    groups = report.get("cohorts")
    require(cohort_shape(groups) == 1076, "COHORT_TOTAL")
    return {"sources": sorted(projected, key=lambda x: x["name"]),
            "cohorts": deepcopy(groups)}


def reconstruct(cache):
    """Actual pinned-byte reconstruction. Never accepts a supplied receipt."""
    return projection_from_receipt(intake.analyze(cache))


def compare_source_declaration(root, cache, declared, projection):
    """Compare the declaration to an already reconstructed source projection.

    This helper has no authority; production use goes through bind_sources().
    """
    require(type(declared) is dict and type(declared.get("sources")) is list,
            "SOURCE_DECLARATION_SCHEMA")
    sources = declared["sources"]
    actual = projection["sources"]
    require(len(sources) == len(actual) == len(intake.SOURCES), "SOURCE_ROSTER")
    expected = {item["name"]: item for item in actual}
    seen = set()
    for item in sources:
        require(type(item) is dict and type(item.get("path")) is str,
                "SOURCE_PATH_SCHEMA")
        path = regular(root, item["path"])
        name = path.name
        require(name in expected and name not in seen and
                path == cache.resolve()/name, "SOURCE_PATH_IDENTITY")
        match = expected[name]
        for field in ("family", "canonical_url", "ref", "sha256"):
            require(type(item.get(field)) is str and item[field] == match[field],
                    "SOURCE_BINDING_MISMATCH:"+field)
        require(type(item.get("byte_length")) is int and
                item["byte_length"] == match["byte_length"], "SOURCE_LENGTH_MISMATCH")
        require(item.get("upstream_commit_sha") == match["ref"], "UPSTREAM_COMMIT_MISMATCH")
        if "git_blob" in match:
            require(item.get("git_blob") == match["git_blob"], "GIT_BLOB_MISMATCH")
        observed = metadata(path, match["byte_length"], match["byte_length"])
        require(observed["sha256"] == match["sha256"], "SOURCE_BYTES_CHANGED")
        seen.add(name)
    groups = declared.get("cohorts")
    cohort_shape(groups)
    require(canonical(groups) == canonical(projection["cohorts"]),
            "SOURCE_COHORT_MEMBERSHIP_MISMATCH")
    return True


def bind_sources(root, cache, manifest_path):
    manifest, raw = load_manifest(root, manifest_path)
    committed_bytes(root, manifest_path, raw)
    old.validate_source_manifest(manifest)
    projection = reconstruct(cache)
    compare_source_declaration(root, cache, manifest, projection)
    return {"manifest_sha256": digest(raw), "projection_sha256": digest(canonical(projection)),
            "source_bytes_and_ordered_cohorts_verified": True,
            "collision_audit_verified": False, "data_terms_verified": False}


def bind_model_artifacts(root, manifest):
    old.validate_model_manifest(manifest)
    bindings = manifest.get("artifact_bindings")
    require(type(bindings) is dict and set(bindings) == set(FIELDS), "MODEL_ARTIFACT_ROSTER")
    seen = set()
    total = 0
    results = {}
    for key in FIELDS:
        item = bindings[key]
        require(type(item) is dict and set(item) == {"path", "byte_length"},
                "MODEL_ARTIFACT_SCHEMA")
        path = regular(root, item["path"])
        require(path not in seen, "MODEL_ARTIFACT_ALIAS")
        seen.add(path)
        length = item["byte_length"]
        require(type(length) is int and 0 < length <= MAX_ARTIFACT, "MODEL_ARTIFACT_LENGTH")
        total += length
        require(total <= MAX_TOTAL, "TOTAL_MODEL_BYTE_BUDGET")
        observed = metadata(path, MAX_ARTIFACT, length)
        require(observed["sha256"] == hex_digest(manifest[key]), "MODEL_ARTIFACT_DIGEST:"+key)
        results[key] = {**observed, "path": item["path"]}
    return results


def bind_runtime(root, manifest):
    """Check real code bytes and the existing policy contract; no model invocation."""
    implementations = manifest.get("policy_implementations")
    require(type(implementations) is dict and
            set(implementations) == set(readiness.REQUIRED_POLICIES), "POLICY_ROSTER")
    code = [(manifest.get("runner_path"), manifest.get("runner_sha256"))]
    for policy in readiness.REQUIRED_POLICIES:
        entry = implementations[policy]
        require(type(entry) is dict, "POLICY_BINDING_SCHEMA")
        code.append((entry.get("path"), entry.get("sha256")))
    checked = {}
    for path, expected in code:
        actual = regular(root, path)
        observed = metadata(actual, MAX_CODE)
        require(observed["sha256"] == hex_digest(expected), "RUNTIME_CODE_DIGEST")
        raw = actual.read_bytes()
        require(len(raw) <= MAX_CODE and digest(raw) == expected, "RUNTIME_CODE_CHANGED")
        committed_bytes(root, path, raw)
        checked[path] = expected
    readiness.validate_runtime_binding(manifest, root=root)
    return checked


def bind_model(root, manifest_path):
    manifest, raw = load_manifest(root, manifest_path)
    committed_bytes(root, manifest_path, raw)
    artifacts = bind_model_artifacts(root, manifest)
    code = bind_runtime(root, manifest)
    return {"manifest_sha256": digest(raw), "artifact_bindings": artifacts,
            "runtime_code_bindings": code, "real_model_behavior_verified": False}


def audit(root, cache):
    result = {"schema": "cwc-terminal-preflight-v1", "checks": {}, "blockers": [],
              "status": "NOT_TESTED", **AUTHORITY}
    for name, operation in (
        ("SOURCE_BINDING", lambda: bind_sources(root, cache, str(EXPERIMENT/"SOURCE_MANIFEST.json"))),
        ("MODEL_BINDING", lambda: bind_model(root, str(EXPERIMENT/"MODEL_MANIFEST.json"))),
    ):
        try:
            result["checks"][name] = operation()
        except FileNotFoundError:
            result["blockers"].append(name+"_MISSING_FILE_OR_MANIFEST")
        except (BindingError, c.ContractError, intake.IntakeError, OSError,
                ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            # Do not print potentially sensitive path or source content.
            result["blockers"].append(name+"_REJECTED:"+type(exc).__name__)
    result["blockers"].extend((
        "REPOSITORY_FIXTURE_COLLISION_AUDIT_AND_TRAINING_PROVENANCE_ADMISSION_PENDING",
        "SOURCE_DATA_TERMS_REVIEW_PENDING",
        "ORIGINAL_READINESS_AND_CALIBRATION_FREEZE_PENDING",
        "REAL_RUNNER_BEHAVIOR_AND_RESOURCE_ACCOUNTING_PENDING",
    ))
    return result


def live_source_controls(root, cache):
    projection = reconstruct(cache)
    declaration = {"sources": [
        {**{k: v for k, v in item.items() if k != "name"},
         "upstream_commit_sha": item["ref"], "path": (cache.resolve()/item["name"]).relative_to(root.resolve()).as_posix()}
        for item in projection["sources"]], "cohorts": deepcopy(projection["cohorts"])}
    require(compare_source_declaration(root, cache, declaration, projection),
            "LIVE_SOURCE_POSITIVE_CONTROL")
    changed = deepcopy(declaration)
    cohort = changed["cohorts"]["AVeriTeC"]["PRIMARY"]
    replacement = digest(b"CWC-INTERNALLY-COHERENT-NONMEMBER")
    require(all(replacement not in info["record_hashes"] for family in COHORT_COUNTS
                for info in changed["cohorts"][family].values()), "MUTATION_COLLISION")
    cohort["record_hashes"][0] = replacement
    cohort["cohort_sha256"] = digest("\n".join(cohort["record_hashes"]).encode())
    cohort_shape(changed["cohorts"])
    try:
        compare_source_declaration(root, cache, changed, projection)
    except BindingError as exc:
        require(str(exc) == "SOURCE_COHORT_MEMBERSHIP_MISMATCH", "WRONG_MUTATION_REJECTION")
    else:
        raise BindingError("COHERENT_NONMEMBER_ADMITTED")
    result = audit(root, cache)
    require(result["status"] == "NOT_TESTED" and result["model_execution_authorized"] is False and
            "SOURCE_BINDING_MISSING_FILE_OR_MANIFEST" in result["blockers"] and
            "MODEL_BINDING_MISSING_FILE_OR_MANIFEST" in result["blockers"], "MISSING_MANIFEST_CONTROL")
    return {"experiment": "CWC-CLOSURE-01", "source_projection_sha256": digest(canonical(projection)),
            "sources": projection["sources"],
            "cohort_counts": COHORT_COUNTS, "cohort_digests": {
                family: {key: info["cohort_sha256"] for key, info in group.items()}
                for family, group in projection["cohorts"].items()},
            "source_membership_binding_control": "PASS",
            "internally_consistent_nonmember_mutation": "REJECTED",
            "preexecution_audit": result, **AUTHORITY}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--source-controls", action="store_true")
    args = parser.parse_args()
    result = (live_source_controls(args.root, args.cache) if args.source_controls
              else audit(args.root, args.cache))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    print(canonical(result).decode())
    return 0 if args.source_controls else 3


if __name__ == "__main__":
    raise SystemExit(main())
