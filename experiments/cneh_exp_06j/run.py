"""Attempt-bound native receipts and fresh reconstruction for J."""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06c.algebra import need
from experiments.cneh_exp_06f.run import canonical, directory, read_receipt, sha
from experiments.cneh_exp_06j import kernel as k, panel as p

BASE = "2511a31828c4547de5eefb9dc26231025180d1df"
PARENT_SHA256 = "5941cb26ddfb49792199768eedd8d44be64e548dcde0d55c6fb16e64aa81ac3c"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"


def identity(args):
    need(all(re.fullmatch(r"[0-9a-f]{40}", s) for s in
             (args.head, args.base, args.checkout)) and args.base == BASE, "commit identity")
    need(all(re.fullmatch(r"[1-9][0-9]*", s) for s in
             (args.run_id, args.attempt)), "run identity")
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "I archive digest mismatch")


def receipt(args, arch, raw):
    need(arch in ARCHES, "native architecture")
    return {"experiment": "CNEH-EXP-06J", "head_sha": args.head, "base_sha": args.base,
            "checkout_sha": args.checkout, "arch": arch, "python": PYTHON,
            "run_id": args.run_id, "run_attempt": args.attempt, "parent_sha256": PARENT_SHA256,
            "payload_sha256": sha(raw), "scientific_promotion_authorized": False}


def validate(value):
    need(value["qualification"] == p.QUALIFIED and value["failures"] == [], "J frozen gate failed")
    need(value["scope"] == k.SCOPE and all(type(value.get(key)) is type(v) and value[key] == v
             for key, v in k.NEGATIVE.items()), "scope or historical evidence changed")
    need(len(value["cases"]) == 38 and len(value["negative_controls"]) == 13 and
         value["finite_panel"]["DP_cases"] == 2040, "frozen case or control roster")
    primary = [row for row in value["cases"] if row["family"] == "PRIMARY"]
    need(len(primary) == 16 and value["primary_metrics"] == p.metrics(primary),
         "primary metrics mismatch")


def native(args):
    identity(args)
    need(platform.machine() == args.arch and platform.python_version() == PYTHON, "native profile")
    value = None
    try:
        value = p.report()
        validate(value)
    except Exception as exc:
        value = {"experiment": "CNEH-EXP-06J", "qualification": "FAIL_FROZEN_GATE",
                 "error_type": type(exc).__name__, "error": str(exc),
                 "unadmitted_observation": value, **k.NEGATIVE}
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
    need(platform.python_version() == PYTHON, "aggregate profile")
    value = p.report()
    validate(value)
    raw = canonical(value)
    directory(args.profiles, {"cneh06j-"+arch for arch in ARCHES})
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cneh06j-"+arch)
        directory(root, {"primary", "replay"})
        expected = receipt(args, arch, raw)
        for replica in ("primary", "replay"):
            folder = root/replica
            directory(folder, {"payload.json", "receipt.json"})
            need(read_receipt(folder/"payload.json") == raw, "fresh reconstruction mismatch")
            need(read_receipt(folder/"receipt.json") == canonical(expected), "receipt identity mismatch")
        receipts.append(expected)
    summary = {"experiment": "CNEH-EXP-06J", "qualification": p.QUALIFIED, "scope": k.SCOPE,
               "head_sha": args.head, "base_sha": args.base, "checkout_sha": args.checkout,
               "run_id": args.run_id, "run_attempt": args.attempt, "parent_sha256": PARENT_SHA256,
               "payload_sha256": sha(raw), "native_receipts": receipts,
               "native_process_receipts": 4, "independent_reconstructions": 1,
               "native_cases": 76, "unique_cases": 38,
               "primary_metrics_per_arch": value["primary_metrics"],
               "best_fixed_certified_per_arch": value["best_fixed_certified"],
               "stress_metrics_per_arch": value["stress_metrics"],
               "finite_panel_per_arch": value["finite_panel"],
               "negative_controls_per_arch": value["negative_controls"], **k.NEGATIVE}
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
