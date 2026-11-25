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
from experiments.cneh_joint_decision import decision as c, panel as p
from experiments.cneh_cover_assurance import cover as parent_cover

PARENT = "5d75a637685a3036ca9f764a29fd5dff78f0fdc1"
PARENT_SHA256 = "a2fd1fc8e32568c7549919dd70bf507a8870823cc000b01cc7083eb7043b27e9"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"


def identity(args):
    need(all(re.fullmatch(r"[0-9a-f]{40}", s) for s in
             (args.head, args.base, args.checkout)), "commit identity")
    need(all(re.fullmatch(r"[1-9][0-9]*", s) for s in
             (args.run_id, args.attempt)), "run identity")
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "sealed COVER-01 archive digest mismatch")


def receipt(args, arch, raw):
    need(arch in ARCHES, "native architecture")
    return {"experiment": "CNEH-COVER-02", "head_sha": args.head, "base_sha": args.base,
            "checkout_sha": args.checkout, "arch": arch, "python": PYTHON,
            "run_id": args.run_id, "run_attempt": args.attempt, "parent_head": PARENT,
            "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
            "scientific_promotion_authorized": False}


def validate(value):
    need(value["qualification"] == p.QUALIFIED and value["failures"] == [],
         "frozen joint-support gate failed")
    need(value["experiment"] == "CNEH-COVER-02" and value["scope"] == c.SCOPE and
         all(type(value.get(k)) is type(expected) and value[k] == expected
             for k, expected in c.NEGATIVE.items()), "scope or historical evidence changed")
    expected = {(family,index,j) for family in ("CLEAN","STRESS")
                for index in ip.TRUTHS for j in range(2)}
    rows = value["cases"]
    need(len(rows) == len(expected) == 32 and {tuple(row["id"]) for row in rows} == expected,
         "compatible record roster")
    checked = decisions = improvements = 0
    decision_counts = {}
    for row in rows:
        world = tuple(map(F,row["known_world"]))
        covers = row["covers"]
        need(tuple(item["budget"] for item in covers) == (1,7), "budget roster")
        for item in covers:
            parent, outer, budget = item["parent"],item["correlated"],item["budget"]
            need(c.verify_cover(row["record"],parent,outer,h.BOUNDED,budget),
                 "joint cover admission")
            need(outer["status"] == parent_cover.OUTER and
                 any(c.contains(c.decode_box(box,4),world[:4]) for box in outer["frontier"]) and
                 all(box in parent["frontier"] for box in outer["frontier"]), "cover soundness")
            need(F(outer["max_width"]) <= F(parent["max_width"]), "expanded cover")
            checked += 1
            improvements += int(F(outer["max_width"]) < F(parent["max_width"]))
        need(len(row["decisions"]) == (2 if row["id"][2] == 0 else 0), "decision roster")
        for idx,item in enumerate(row["decisions"]):
            proof = item["proof"]
            losses = (p.DOMINANCE,p.THRESHOLD)[idx]
            need(c.verify_decision(row["record"],covers[0]["parent"],covers[0]["correlated"],
                 item["witnesses"],losses,"0/1",h.BOUNDED,1,proof), "decision proof admission")
            decisions += 1
            decision_counts[proof["status"]] = decision_counts.get(proof["status"],0)+1
    need(checked == value["cover_checks"] == 64 and decisions == value["decision_cases"] == 32
         and decision_counts == value["decision_counts"] and improvements == value["strict_width_improvements"],
         "evaluation accounting")
    neg = value["contradictions"]
    negative_roster = {("REFERENCE",b,sign) for b in (-8,8) for sign in (-1,1)}
    negative_roster.update((("GROSS",0,900),("GROSS",60,-100),("SUBTLE",-1),("SUBTLE",1)))
    need(len(neg)==8 and {tuple(row["id"]) for row in neg}==negative_roster,"contradiction roster")
    for row in neg:
        need(c.verify_cover(row["record"],row["parent"],row["correlated"],h.BOUNDED,1) and
             row["correlated"]["status"] == parent_cover.EXCLUDED and
             c.verify_decision(row["record"],row["parent"],row["correlated"],[],p.DOMINANCE,
                "0/1",h.BOUNDED,1,row["decision"]) and row["decision"]["status"] == "CONTRADICTION",
             "contradiction admission")
    support = value["support"]
    need(support == p.support_panel() and len(support["comparisons"]) == 450 and
         support["strict_improvements"] > 0 and support["analytic_width_ratio"] == "23/8" and
         support["degenerate_checks"] == 15, "support comparison roster")
    controls = value["controls"]
    need(controls == p.controls() and sum(x == "REJECTED" for x in controls["dispositions"].values())==18,
         "mutation roster")


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
        failed = {"experiment": "CNEH-COVER-02", "qualification": "FAIL_FROZEN_GATE",
                  "error_type": type(exc).__name__, "error": str(exc),
                  "unadmitted_observation": value, **c.NEGATIVE}
        write_native(args, failed)
        print("FAIL_FROZEN_GATE:", type(exc).__name__, str(exc))
        return 1
    write_native(args, value)
    print(p.QUALIFIED)
    return 0


def verify_profiles(args, raw):
    directory(args.profiles, {"cnehcover02-"+arch for arch in ARCHES})
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cnehcover02-"+arch)
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
        failure = {"experiment": "CNEH-COVER-02", "qualification": "FAIL_FROZEN_GATE",
                   "error_type": type(exc).__name__, "error": str(exc),
                   "unadmitted_observation": value, **c.NEGATIVE}
        (args.out/"unadmitted.json").write_bytes(canonical(failure))
        print("FAIL_FROZEN_GATE:", type(exc).__name__, str(exc))
        return 1
    summary = {"experiment": "CNEH-COVER-02", "qualification": p.QUALIFIED,
               "scope": c.SCOPE, "head_sha": args.head, "base_sha": args.base,
               "checkout_sha": args.checkout, "run_id": args.run_id,
               "run_attempt": args.attempt, "parent_head": PARENT,
               "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
               "native_receipts": receipts, "native_process_receipts": 4,
               "independent_reconstructions": 1, "unique_continuous_records": 40,
               "native_support_comparisons": 900, "native_degenerate_support_checks": 30,
               "strict_support_improvements_per_arch": value["support"]["strict_improvements"],
               "native_compatible_records": 64, "native_contradictions": 16,
               "native_cover_checks": 128, "native_decision_cases": 64,
               "native_rejected_mutations": 36,
               "strict_frontier_width_improvements_per_arch": value["strict_width_improvements"],
               "decision_counts_per_arch": value["decision_counts"],
               "analytic_cartesian_to_joint_width_ratio": value["support"]["analytic_width_ratio"],
               "opposing_witness_decision": value["controls"]["opposing_witnesses"]["decision"],
               **c.NEGATIVE}
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
