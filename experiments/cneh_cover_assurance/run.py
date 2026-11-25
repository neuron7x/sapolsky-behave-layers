"""Native cover qualification and same-attempt independent reconstruction."""
from __future__ import annotations

import argparse
from fractions import Fraction as F
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06c.algebra import need
from experiments.cneh_exp_06f.run import canonical, directory, read_receipt, sha
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as ip
from experiments.cneh_cover_assurance import cover as c, panel as p, verifier as v

PARENT = "bdc3d736692aeb1362c12918afc022fa11c7ca2c"
PARENT_SHA256 = "2f127a7590a9f6e5f01858c185be70d07ed28d78fd226a97807fa3443e729479"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"


def identity(args):
    need(all(re.fullmatch(r"[0-9a-f]{40}", s) for s in
             (args.head, args.base, args.checkout)), "commit identity")
    need(all(re.fullmatch(r"[1-9][0-9]*", s) for s in
             (args.run_id, args.attempt)), "run identity")
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "sealed J archive digest mismatch")


def receipt(args, arch, raw):
    need(arch in ARCHES, "native architecture")
    return {"experiment": "CNEH-COVER-01", "head_sha": args.head, "base_sha": args.base,
            "checkout_sha": args.checkout, "arch": arch, "python": PYTHON,
            "run_id": args.run_id, "run_attempt": args.attempt, "parent_head": PARENT,
            "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
            "scientific_promotion_authorized": False}


def validate(value):
    need(value["qualification"] == p.QUALIFIED and value["failures"] == [],
         "frozen cover gate failed")
    need(value["experiment"] == "CNEH-COVER-01" and value["scope"] == c.SCOPE and
         all(type(value.get(k)) is type(expected) and value[k] == expected
             for k, expected in c.NEGATIVE.items()), "scope or historic evidence changed")
    roster = {(family, index, j) for family in ("CLEAN", "STRESS")
              for index in ip.TRUTHS for j in range(2)}
    roster.update(("EXTREME", i, j, sign) for i in range(4) for j in range(3)
                  for sign in (-1, 1))
    roster.update(("REFERENCE", b, sign) for b in (-8, 8) for sign in (-1, 1))
    roster.update((("GROSS", 0, 900), ("GROSS", 60, -100)))
    roster.update(("SUBTLE", sign) for sign in (-1, 1))
    rows = value["cases"]
    need(len(rows) == len(roster) == 64 and {tuple(row["id"]) for row in rows} == roster,
         "case roster")
    positive = [row for row in rows if "proofs" in row]
    negative = [row for row in rows if "proof" in row]
    need(len(positive) == value["compatible_cases"] == 56 and
         len(negative) == value["contradictions"] == 8, "case counts")
    widths, checks, nodes = [], 0, 0
    for row in positive:
        key = tuple(row["id"])
        budgets = (0, 1, 7, 63) if key in (
            ("EXTREME", 0, 0, -1), ("EXTREME", 3, 2, 1)) else (0, 1, 7)
        proofs = row["proofs"]
        need(tuple(proof["node_budget"] for proof in proofs) == budgets, "budget roster")
        world = tuple(map(F, row["known_world"]))
        previous = None
        for proof, budget in zip(proofs, budgets, strict=True):
            need(v.verify(row["record"], proof, h.BOUNDED, budget), "proof admission")
            need(proof["status"] == c.OUTER and p.contains(proof["root"], world) and
                 any(p.contains(box, world[:4]) for box in proof["frontier"]),
                 "known compatible world omitted")
            if previous is not None:
                need(all(any(p.subset(box, parent) for parent in previous["frontier"])
                         for box in proof["frontier"]), "frontier refinement mismatch")
            previous = proof
            nodes += proof["nodes"]
            checks += 1
        widths.append(F(proofs[1]["max_width"]))
    for row in negative:
        proof = row["proof"]
        need(v.verify(row["record"], proof, h.BOUNDED, 1) and
             proof["status"] == c.EXCLUDED and proof["frontier"] == [],
             "contradiction admission")
        if row["id"][0] == "SUBTLE":
            need(row["legacy"]["status"] == "UNKNOWN" and row["legacy"]["nodes"] == 1,
                 "legacy baseline mismatch")
        nodes += proof["nodes"]
    need(checks == value["cover_checks"] == 170 and nodes == value["evaluated_nodes"],
         "cover accounting")
    need(max(widths) == F(value["max_one_node_width"]) <= h.WIDTH, "panel width")
    need(len(value["quantizer_panel"]) == 54 and
         len(value["controls"]["mutations"]) == 22 and
         set(value["controls"]["mutations"].values()) == {"REJECTED"}, "control roster")


def write_native(args, value):
    raw = canonical(value)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    meta = receipt(args, args.arch, raw)
    (args.out/"receipt.json").write_bytes(canonical(meta))
    print(canonical(meta).decode("ascii"), end="")


def native(args):
    identity(args)
    need(platform.machine() == args.arch and platform.python_version() == PYTHON,
         "native execution profile")
    value = None
    try:
        value = p.report()
        validate(value)
    except Exception as exc:
        failed = {"experiment": "CNEH-COVER-01", "qualification": "FAIL_FROZEN_GATE",
                  "error_type": type(exc).__name__, "error": str(exc),
                  "unadmitted_observation": value, **c.NEGATIVE}
        write_native(args, failed)
        print("FAIL_FROZEN_GATE:", type(exc).__name__, str(exc))
        return 1
    write_native(args, value)
    print(p.QUALIFIED)
    return 0


def verify_profiles(args, raw):
    directory(args.profiles, {"cnehcover-"+arch for arch in ARCHES})
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cnehcover-"+arch)
        directory(root, {"primary", "replay"})
        expected = receipt(args, arch, raw)
        for replica in ("primary", "replay"):
            folder = root/replica
            directory(folder, {"payload.json", "receipt.json"})
            need(read_receipt(folder/"payload.json") == raw, "fresh reconstruction mismatch")
            need(read_receipt(folder/"receipt.json") == canonical(expected), "receipt identity mismatch")
        receipts.append(expected)
    return receipts


def aggregate(args):
    identity(args)
    need(platform.python_version() == PYTHON, "aggregate Python profile")
    value = None
    try:
        value = p.report()
        validate(value)
        raw = canonical(value)
        receipts = verify_profiles(args, raw)
    except Exception as exc:
        args.out.mkdir(parents=True, exist_ok=False)
        failure = {"experiment": "CNEH-COVER-01", "qualification": "FAIL_FROZEN_GATE",
                   "error_type": type(exc).__name__, "error": str(exc),
                   "unadmitted_observation": value, **c.NEGATIVE}
        (args.out/"unadmitted.json").write_bytes(canonical(failure))
        print("FAIL_FROZEN_GATE:", type(exc).__name__, str(exc))
        return 1
    summary = {"experiment": "CNEH-COVER-01", "qualification": p.QUALIFIED,
               "scope": c.SCOPE, "head_sha": args.head, "base_sha": args.base,
               "checkout_sha": args.checkout, "run_id": args.run_id,
               "run_attempt": args.attempt, "parent_head": PARENT,
               "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
               "native_receipts": receipts, "native_process_receipts": 4,
               "independent_reconstructions": 1, "unique_records": 64,
               "native_records": 128, "native_known_compatible": 112,
               "native_contradictions": 16, "native_cover_checks": 340,
               "native_subtle_one_node_exclusions": 4,
               "native_quantizer_checks": 108, "native_rejected_mutations": 44,
               "max_one_node_width": value["max_one_node_width"],
               "evaluated_nodes_per_arch": value["evaluated_nodes"],
               "joint_existence_established": False, **c.NEGATIVE}
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    (args.out/"report.json").write_bytes(canonical(summary))
    (args.out/"SHA256SUMS").write_text("".join(
        sha((args.out/name).read_bytes())+"  "+name+"\n"
        for name in ("payload.json", "report.json")), encoding="ascii")
    print(canonical(summary).decode("ascii"), end="")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="command", required=True)
    for name in ("native", "aggregate"):
        sub = modes.add_parser(name)
        for arg in ("head", "base", "checkout", "run-id", "attempt"):
            sub.add_argument("--"+arg, required=True)
        sub.add_argument("--parent", required=True, type=Path)
        sub.add_argument("--out", required=True, type=Path)
        if name == "native":
            sub.add_argument("--arch", choices=ARCHES, required=True)
        else:
            sub.add_argument("--profiles", type=Path, required=True)
    args = parser.parse_args()
    return (native if args.command == "native" else aggregate)(args)


if __name__ == "__main__":
    raise SystemExit(main())
