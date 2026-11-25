"""Attempt-bound native receipts and fresh reconstruction for K."""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06f.run import canonical, directory, read_receipt, sha
from experiments.cneh_exp_06k import kernel as k, panel as p

BASE = "bdc3d736692aeb1362c12918afc022fa11c7ca2c"
PARENT_SHA256 = "2f127a7590a9f6e5f01858c185be70d07ed28d78fd226a97807fa3443e729479"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"


def identity(args):
    k.need(all(re.fullmatch(r"[0-9a-f]{40}", s) for s in
               (args.head, args.base, args.checkout)) and args.base == BASE, "commit identity")
    k.need(all(re.fullmatch(r"[1-9][0-9]*", s) for s in
               (args.run_id, args.attempt)), "run identity")
    k.need(sha(read_receipt(args.parent)) == PARENT_SHA256, "J archive digest mismatch")


def receipt(args, arch, raw):
    k.need(arch in ARCHES, "native architecture")
    return {"experiment": p.EXPERIMENT, "head_sha": args.head, "base_sha": args.base,
            "checkout_sha": args.checkout, "arch": arch, "python": PYTHON,
            "run_id": args.run_id, "run_attempt": args.attempt,
            "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
            "scientific_promotion_authorized": False}


def validate(value):
    k.need(value["qualification"] == p.QUALIFIED and value["failures"] == [],
           "K frozen gate failed")
    k.need(value["scope"] == k.SCOPE and all(type(value.get(key)) is type(v) and
           value[key] == v for key, v in p.NEGATIVE.items()), "scope or authority")
    k.need(len(value["shared_cases"]) == 16 and len(value["independent_cases"]) == 64
           and len(value["negative_controls"]) == 16 and
           value["oracle"]["configurations"] == 24480 and
           len(value["full_response_ambiguities"]) == 16, "frozen roster")


def native(args):
    identity(args)
    k.need(platform.machine() == args.arch and platform.python_version() == PYTHON,
           "native profile")
    value = None
    try:
        value = p.report()
        validate(value)
    except Exception as exc:
        value = {"experiment": p.EXPERIMENT, "qualification": "FAIL_FROZEN_GATE",
                 "error_type": type(exc).__name__, "error": str(exc),
                 "unadmitted_observation": value, **p.NEGATIVE}
    raw = canonical(value)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    meta = receipt(args, args.arch, raw)
    (args.out/"receipt.json").write_bytes(canonical(meta))
    print(canonical(meta).decode("ascii"), end="")
    print(value["qualification"])
    return int(value["qualification"] != p.QUALIFIED)


def aggregate(args):
    identity(args)
    k.need(platform.python_version() == PYTHON, "aggregate profile")
    value = p.report()
    validate(value)
    raw = canonical(value)
    directory(args.profiles, {"cneh06k-"+arch for arch in ARCHES})
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cneh06k-"+arch)
        directory(root, {"primary", "replay"})
        expected = receipt(args, arch, raw)
        for replica in ("primary", "replay"):
            folder = root/replica
            directory(folder, {"payload.json", "receipt.json"})
            k.need(read_receipt(folder/"payload.json") == raw, "fresh reconstruction mismatch")
            k.need(read_receipt(folder/"receipt.json") == canonical(expected),
                   "receipt identity mismatch")
        receipts.append(expected)
    summary = {"experiment": p.EXPERIMENT, "qualification": p.QUALIFIED, "scope": k.SCOPE,
               "head_sha": args.head, "base_sha": args.base, "checkout_sha": args.checkout,
               "run_id": args.run_id, "run_attempt": args.attempt, "parent_sha256": PARENT_SHA256,
               "payload_sha256": sha(raw), "native_receipts": receipts,
               "native_process_receipts": 4, "independent_reconstructions": 1,
               "unique_world_cases": 80, "native_world_cases": 160,
               "oracle_configurations_per_arch": value["oracle"]["configurations"],
               "metrics_per_arch": value["metrics"],
               "negative_controls_per_arch": value["negative_controls"],
               "full_response_ambiguities_per_arch": value["full_response_ambiguities"],
               **p.NEGATIVE}
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    (args.out/"report.json").write_bytes(canonical(summary))
    (args.out/"SHA256SUMS").write_text("".join(
        sha((args.out/name).read_bytes())+"  "+name+"\n"
        for name in ("payload.json", "report.json")), encoding="ascii")
    print(canonical(summary).decode("ascii"), end="")
    return 0


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_subparsers(dest="command", required=True)
    for name in ("native", "aggregate"):
        sub = modes.add_parser(name)
        for arg in ("head", "base", "checkout", "run-id", "attempt"):
            sub.add_argument("--"+arg, required=True)
        sub.add_argument("--parent", required=True, type=Path)
        sub.add_argument("--out", required=True, type=Path)
        if name == "native":
            sub.add_argument("--arch", required=True, choices=ARCHES)
        else:
            sub.add_argument("--profiles", required=True, type=Path)
    args = parser.parse_args()
    return (native if args.command == "native" else aggregate)(args)


if __name__ == "__main__":
    raise SystemExit(main())
