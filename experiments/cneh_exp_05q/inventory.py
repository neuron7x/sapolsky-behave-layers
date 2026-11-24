"""Read-only historical numerical provenance inventory. Never authorizes replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
from urllib.parse import unquote, urlsplit
import zipfile

ARCHIVE_SHA = "db78569d633a4fd1ae5649ab02e53a86b48e97f0317b45a849a56cd73e993ea8"
ARCHIVE_ID = 14890028886
EXPERIMENT = "CNEH-EXP-05Q"
LIMIT = 8 * 1024 * 1024
LOCK = Path(__file__).resolve().parents[1] / "cneh_exp_01" / "bnsyn-requirements.lock"
ROSTER = {
    "cneh05/preregistration.md", "cneh05/implementation.json",
    "cneh05/certificate.json", "cneh05/episodes.json.gz",
    "cneh05/worlds.json", "cneh05/verdict.json", "cneh05/SHA256SUMS",
    "cneh05-install.json",
}
ENV_FIELDS = (
    "implementation_name", "implementation_version", "os_name", "platform_machine",
    "platform_release", "platform_system", "platform_version", "python_full_version",
    "python_version", "sys_platform",
)
UNESTABLISHED = (
    "original_cpu_model_features_and_dispatch",
    "original_interpreter_executable_sha256",
    "original_loaded_native_binary_sha256",
    "original_libm_libc_blas_binary_identity",
    "original_numerical_kernel_execution_contract",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha_file(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def invalid(token):
        raise ValueError("invalid JSON constant: " + token)

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def name_key(name):
    require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", name),
            "invalid package name")
    return re.sub(r"[-_.]+", "-", name).lower()


def lock_records(lock_text):
    records = {}
    current = None
    for line in lock_text.splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        requirement = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)\s*\\?", value)
        digest = re.fullmatch(r"--hash=sha256:([0-9a-f]{64})\s*\\?", value)
        if requirement:
            current = name_key(requirement.group(1))
            require(current not in records, "duplicate locked package")
            records[current] = (requirement.group(2), set())
        elif digest:
            require(current is not None, "orphan lock digest")
            records[current][1].add(digest.group(1))
        else:
            raise ValueError("unexpected lock syntax")
    require(records and all(hashes for _, hashes in records.values()), "empty lock record")
    return records


def installed_records(report, lock_text):
    require(isinstance(report, dict) and isinstance(report.get("install"), list),
            "invalid pip installation report")
    locked = lock_records(lock_text)
    selected = {}
    for item in report["install"]:
        meta, download = item["metadata"], item["download_info"]
        package = name_key(meta["name"])
        version = meta["version"]
        digest = download["archive_info"]["hashes"]["sha256"]
        require(package in locked and package not in selected, "invalid installed roster")
        expected_version, digests = locked[package]
        require(version == expected_version and digest in digests, "unlocked wheel identity")
        url = urlsplit(download["url"])
        wheel = PurePosixPath(unquote(url.path)).name
        require(wheel.endswith(".whl") and url.scheme == "https", "non-wheel download")
        selected[package] = {"version": version, "wheel": wheel, "sha256": digest}
    require(set(selected) == set(locked), "incomplete installed roster")
    environment = report.get("environment", {})
    require(isinstance(environment, dict), "invalid environment record")
    observed = {k: environment[k] for k in ENV_FIELDS
                if isinstance(environment.get(k), str) and environment[k]}
    return selected, observed


def inventory(path, expected_sha, lock_text):
    require(path.is_file() and not path.is_symlink(), "regular archive required")
    require(sha_file(path) == expected_sha, "outer archive SHA256 mismatch")
    with zipfile.ZipFile(path) as archive:
        files = [i for i in archive.infolist() if not i.is_dir()]
        names = [i.filename for i in files]
        require(len(names) == len(set(names)) and set(names) == ROSTER, "unexpected ZIP roster")
        require(all(stat.S_IFMT(i.external_attr >> 16) in (0, stat.S_IFREG) for i in files),
                "nonregular ZIP member")
        info = archive.getinfo("cneh05-install.json")
        require(0 < info.file_size <= LIMIT, "invalid install report size")
        raw = archive.read(info)
        require(len(raw) == info.file_size, "incomplete install report")
        selected, environment = installed_records(strict_json(raw), lock_text)
    require(sha_file(path) == expected_sha, "archive changed during inventory")
    return {
        "experiment": EXPERIMENT,
        "scientific_promotion_authorized": False,
        "scientific_promotion": "BLOCKED",
        "scope": "OUTER_ARCHIVE_AND_PIP_REPORT_ONLY_NOT_NATIVE_REPLAY",
        "historical_archive_sha256": expected_sha,
        "install_report_sha256": hashlib.sha256(raw).hexdigest(),
        "locked_wheel_roster": selected,
        "reported_environment": environment,
        "missing_report_environment_fields": sorted(set(ENV_FIELDS) - set(environment)),
        "unestablished_execution_domain_fields": list(UNESTABLISHED),
        "historical_domain": "HISTORICAL_DOMAIN_UNRESOLVED",
        "historical_native_replay": "FAIL_PRESERVED",
        "replay_rerun_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.archive, ARCHIVE_SHA, LOCK.read_text(encoding="utf-8"))
    result["historical_archive_id"] = ARCHIVE_ID
    with args.out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
