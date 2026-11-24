"""Attempt-bound native proof evidence for the joint feasibility experiment."""
from __future__ import annotations

import argparse
from fractions import Fraction as F
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06c.algebra import need
from experiments.cneh_exp_06f.run import canonical, directory, read_receipt, sha
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as p, solver as s

# The CI checkout verifies ancestry and zero tree difference from this exact
# parent; the actual event base is separately bound into each receipt.
BASE = "83afb6275fad878a3bdb4058f80820cea004926e"
PARENT_SHA256 = "7ac2b6c1dd7c26a57433ffdd1f06827fe1efcdc9e0146079a9feb1e6f2a2a13d"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"


def identity(args):
    need(all(re.fullmatch(r"[0-9a-f]{40}", v) for v in
             (args.head, args.base, args.checkout)), "invalid commit identity")
    need(all(re.fullmatch(r"[1-9][0-9]*", v) for v in
             (args.run_id, args.attempt)), "invalid run identity")


def metadata(args, arch, raw):
    identity(args)
    need(arch in ARCHES, "unsupported architecture")
    return {"experiment": "CNEH-EXP-06I", "head_sha": args.head,
            "base_sha": args.base, "checkout_sha": args.checkout,
            "parent_head": BASE, "run_id": args.run_id, "run_attempt": args.attempt,
            "arch": arch, "python": PYTHON, "parent_sha256": PARENT_SHA256,
            "payload_sha256": sha(raw), "scientific_promotion_authorized": False}


def case_key(row):
    family = row["family"]
    if family in ("CLEAN", "STRESS"):
        return family, row["truth_id"], row["world_id"]
    if family == "MARGINAL_CONFLICT":
        return family, row["b0"], row["direction"]
    if family == "CURRENT_CONFLICT":
        return family, row["time_ms"], row["code_pA"]
    raise ValueError("unknown family")


def validate(value):
    need(value["qualification"] == p.QUALIFIED and value["failures"] == [],
         "I engineering admission failed")
    need(value["scope"] == s.SCOPE and
         all(type(value.get(k)) is type(v) and value[k] == v
             for k, v in s.NEGATIVE.items()), "negative evidence or scope changed")
    rows = value["cases"]
    roster = {(family, i, j) for family in ("CLEAN", "STRESS")
              for i in p.TRUTHS for j in range(2)}
    roster.update(("MARGINAL_CONFLICT", b, d) for b in ("-8/1", "8/1") for d in (-1, 1))
    roster.update((("CURRENT_CONFLICT", 0, "900/1"), ("CURRENT_CONFLICT", 60, "-100/1")))
    actual = {case_key(row) for row in rows}
    need(len(rows) == len(actual) == 38 and actual == roster, "case roster")
    counts = {}
    for row in rows:
        record, result = row["record"], row["I"]
        need(row["H"] == h.estimate(record, h.BOUNDED), "H comparison mismatch")
        need(s.verify(record, result, h.BOUNDED) and s.verify(record, row["unverified"]),
             "independent result admission")
        family, status = row["family"], result["status"]
        if family in ("CLEAN", "STRESS"):
            truth = tuple(map(F, row["truth"]))
            need(status != s.EXCLUDED and result["outer_bounds"] is not None and
                 all(F(lo) <= v <= F(hi) for v, (lo, hi) in
                     zip(truth, result["outer_bounds"], strict=True)), "false exclusion")
            if family == "CLEAN":
                need(status == s.WITNESS, "clean feasibility witness absent")
        elif family == "MARGINAL_CONFLICT":
            proof = result["certificate"]
            need(status == s.EXCLUDED and row["H"]["status"] == "CONDITIONAL_NARROW_ENCLOSURE"
                 and proof["kind"] == "JOINT_REFERENCE_EMPTY"
                 and F(proof["lower"])-F(proof["upper"]) == h.STEP,
                 "marginal counterexample lost")
        else:
            need(status == s.EXCLUDED and result["certificate"]["kind"] == "COVER"
                 and result["certificate"]["unresolved_leaves"] == 0,
                 "current contradiction lost")
        counts.setdefault(family, {})
        counts[family][status] = counts[family].get(status, 0)+1
    need(counts == value["counts"], "disposition summary mismatch")
    controls = value["negative_controls"]
    need(controls == p.negative_controls() and len(controls["controls"]) == 16,
         "proof mutation control roster")


def write(args, value):
    raw = canonical(value)
    args.out.mkdir(parents=True, exist_ok=False)
    receipt = metadata(args, args.arch, raw)
    (args.out/"payload.json").write_bytes(raw)
    (args.out/"receipt.json").write_bytes(canonical(receipt))
    print(canonical(receipt).decode("ascii"), end="")


def native(args):
    identity(args)
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "H archive digest mismatch")
    need(platform.python_version() == PYTHON and platform.machine() == args.arch,
         "native execution profile mismatch")
    value = None
    try:
        value = p.report()
        validate(value)
    except Exception as exc:
        write(args, {"experiment": "CNEH-EXP-06I", "qualification": "FAIL_ENGINEERING_GATE",
                     "error_type": type(exc).__name__, "error": str(exc),
                     "unadmitted_observation": value, **s.NEGATIVE})
        print("FAIL_ENGINEERING_GATE:", type(exc).__name__, str(exc))
        return 1
    write(args, value)
    print(p.QUALIFIED)
    return 0


def verify_profiles(args, expected):
    directory(args.profiles, {"cneh06i-"+arch for arch in ARCHES})
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cneh06i-"+arch)
        directory(root, {"primary", "replay"})
        for replica in ("primary", "replay"):
            folder = root/replica
            directory(folder, {"payload.json", "receipt.json"})
            raw = read_receipt(folder/"payload.json")
            need(raw == expected, "raw evidence differs from fresh reconstruction")
            receipt = metadata(args, arch, raw)
            need(read_receipt(folder/"receipt.json") == canonical(receipt),
                 "native identity receipt mismatch")
        receipts.append(receipt)
    return receipts


def aggregate(args):
    identity(args)
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "H archive digest mismatch")
    need(platform.python_version() == PYTHON, "locked Python mismatch")
    value = p.report()
    validate(value)
    raw = canonical(value)
    receipts = verify_profiles(args, raw)
    rows = value["cases"]
    summary = {"experiment": "CNEH-EXP-06I", "qualification": p.QUALIFIED,
               "scope": s.SCOPE, "head_sha": args.head, "base_sha": args.base,
               "checkout_sha": args.checkout, "parent_head": BASE,
               "run_id": args.run_id, "run_attempt": args.attempt,
               "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
               "native_receipts": receipts, "native_process_receipts": 4,
               "native_exact_payload_pairs": 1, "independent_reconstructions": 1,
               "native_cases": 2*len(rows),
               "native_feasible_witnesses": 2*sum(row["I"]["status"] == s.WITNESS for row in rows),
               "native_certified_infeasible": 2*sum(row["I"]["status"] == s.EXCLUDED for row in rows),
               "native_unknown": 2*sum(row["I"]["status"] == s.UNKNOWN for row in rows),
               "native_H_narrow_jointly_impossible": 2*sum(
                   row["H"]["status"] == "CONDITIONAL_NARROW_ENCLOSURE" and
                   row["I"]["status"] == s.EXCLUDED for row in rows),
               "native_negative_controls": 2*len(value["negative_controls"]["controls"]),
               "counts_per_arch": value["counts"], "max_search_nodes": s.MAX_NODES,
               **s.NEGATIVE}
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
        sub.add_argument("--parent", type=Path, required=True)
        sub.add_argument("--head", required=True)
        sub.add_argument("--base", required=True)
        sub.add_argument("--checkout", required=True)
        sub.add_argument("--run-id", required=True)
        sub.add_argument("--attempt", required=True)
        sub.add_argument("--out", type=Path, required=True)
        if name == "native":
            sub.add_argument("--arch", choices=ARCHES, required=True)
        else:
            sub.add_argument("--profiles", type=Path, required=True)
    args = parser.parse_args()
    return (native if args.command == "native" else aggregate)(args)


if __name__ == "__main__":
    raise SystemExit(main())
