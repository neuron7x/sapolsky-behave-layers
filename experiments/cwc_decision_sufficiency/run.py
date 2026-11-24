"""Native receipt admission for DS01; no scientific promotion authority."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import re

from experiments.cwc_decision_sufficiency import oracle as o

ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"
LIMIT = 1024*1024


def sha(value):
    return hashlib.sha256(value).hexdigest()


def metadata(arch, raw):
    ids = {key: os.environ.get(env, "") for key, env in (
        ("head_sha", "HEAD_SHA"), ("base_sha", "BASE_SHA"),
        ("checkout_sha", "GITHUB_SHA"), ("run_id", "GITHUB_RUN_ID"),
        ("run_attempt", "GITHUB_RUN_ATTEMPT"))}
    o.need(all(re.fullmatch("[0-9a-f]{40}", ids[k]) for k in
               ("head_sha", "base_sha", "checkout_sha")), "commit identity")
    o.need(all(re.fullmatch("[1-9][0-9]*", ids[k]) for k in
               ("run_id", "run_attempt")), "run identity")
    o.need(arch in ARCHES, "architecture")
    return {"experiment": "CWC-DS01", **ids, "arch": arch, "python": PYTHON,
            "payload_sha256": sha(raw), "scientific_promotion_authorized": False}


def directory(root, expected):
    o.need(root.is_dir() and not root.is_symlink() and
           {x.name for x in root.iterdir()} == set(expected), "directory roster")


def read(path):
    o.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= LIMIT,
           "bounded receipt file")
    raw = path.read_bytes()
    o.need(len(raw) <= LIMIT, "oversized receipt")
    return raw


def write(folder, value, arch):
    raw = o.canonical(value)
    folder.mkdir(parents=True, exist_ok=False)
    (folder/"payload.json").write_bytes(raw)
    (folder/"receipt.json").write_bytes(o.canonical(metadata(arch, raw)))


def native(args):
    o.need(platform.machine() == args.arch and platform.python_version() == PYTHON,
           "native profile")
    try:
        value = o.report()
    except Exception as exc:
        write(args.out, {"qualification": "FAIL", "error_type": type(exc).__name__,
                         "error": str(exc), "scientific_promotion_authorized": False}, args.arch)
        raise
    write(args.out, value, args.arch)
    return 0


def aggregate(args):
    o.need(platform.python_version() == PYTHON, "aggregate profile")
    value = o.report()
    raw = o.canonical(value)
    directory(args.profiles, ARCHES)
    receipts = []
    for arch in ARCHES:
        root = args.profiles/arch
        directory(root, ("primary", "replay"))
        for replica in ("primary", "replay"):
            folder = root/replica
            directory(folder, ("payload.json", "receipt.json"))
            o.need(read(folder/"payload.json") == raw, "raw mismatch")
            expected = metadata(arch, raw)
            o.need(read(folder/"receipt.json") == o.canonical(expected), "receipt identity mismatch")
            receipts.append(expected)
    summary = {"experiment": "CWC-DS01", "qualification": "PASS_FINITE_CONDITIONAL_ORACLE_ONLY",
               "payload_sha256": sha(raw), "native_receipts": receipts,
               "native_process_receipts": 4, "fresh_reconstructions": 1,
               "native_cases": 2*value["cases"], "unique_frozen_cases": value["cases"],
               "nested_checks_per_arch": value["nested_checks"],
               "obstruction_checks_per_arch": value["obstruction_checks"],
               "families": {name: {key: row[key] for key in
                                   ("adaptive", "static", "full_id_adaptive", "greedy")}
                            for name, row in value["families"].items()},
               "scientific_promotion_authorized": False,
               "source_action_authorized": False, "external_novelty": "NOT_ESTABLISHED"}
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    (args.out/"report.json").write_bytes(o.canonical(summary))
    (args.out/"SHA256SUMS").write_text("".join(
        sha((args.out/name).read_bytes())+"  "+name+"\n"
        for name in ("payload.json", "report.json")), encoding="ascii")
    print(o.canonical(summary).decode("ascii"), end="")
    return 0


def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="mode", required=True)
    n = subs.add_parser("native")
    n.add_argument("--arch", required=True, choices=ARCHES)
    n.add_argument("--out", required=True, type=Path)
    a = subs.add_parser("aggregate")
    a.add_argument("--profiles", required=True, type=Path)
    a.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    return (native if args.mode == "native" else aggregate)(args)


if __name__ == "__main__":
    raise SystemExit(main())
