"""Attempt-bound native reference evidence and exact independent reconstruction."""
from __future__ import annotations

import argparse
from fractions import Fraction as F
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06c.algebra import need
from experiments.cneh_exp_06f.run import canonical, directory, read_receipt, sha
from experiments.cneh_exp_06h import panel as p, reference as h

BASE = "0f3ae2ee00001b9d99adcedb95443ce6ae3f4bfc"
PARENT_SHA256 = "5ff7e7857e3420d4ca0909515ac58a3eb11bac335dcc2c1081d094e8db1b50f8"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"


def identity(args):
    need(all(re.fullmatch(r"[0-9a-f]{40}", v) for v in
             (args.head, args.base, args.checkout)), "invalid commit identity")
    need(args.base == BASE, "unexpected integrated G base")
    need(all(re.fullmatch(r"[1-9][0-9]*", v) for v in
             (args.run_id, args.attempt)), "invalid run identity")


def metadata(args, arch, raw):
    identity(args)
    need(arch in ARCHES, "unsupported architecture")
    return {"experiment": "CNEH-EXP-06H", "head_sha": args.head,
            "base_sha": args.base, "checkout_sha": args.checkout,
            "run_id": args.run_id, "run_attempt": args.attempt, "arch": arch,
            "python": PYTHON, "parent_sha256": PARENT_SHA256,
            "payload_sha256": sha(raw), "scientific_promotion_authorized": False}


def validate(value):
    need(value["qualification"] == p.QUALIFIED and value["failures"] == [],
         "H engineering admission failed")
    need(value["scope"] == h.SCOPE, "scope mismatch")
    need(all(type(value.get(k)) is type(v) and value[k] == v
             for k, v in h.NEGATIVE.items()), "negative evidence changed")
    certificate = value["diameter_certificate"]
    need(certificate == h.diameter_certificate() and
         F(certificate["max_diameter_upper"]) <= h.WIDTH and
         len(certificate["full_tau_cover"]) == 19, "global diameter certificate")
    need(value["gamma_ablation"] == p.gamma_ablation() and
         value["gamma_ablation"]["separation"] == "1/2", "gamma ablation lost")
    need(value["g_witness_recovery"] == p.g_witness_recovery(),
         "historical gauge recovery mismatch")
    need(value["negative_controls"] == p.negative_controls() and
         len(value["negative_controls"]) == 21, "negative control roster")
    rows = value["cases"]
    expected = {(i, tuple(world), sign) for i in p.TRUTHS for world in p.worlds()
                for sign in p.SIGNS}
    actual = {(row["truth_id"], tuple(map(F, row["nuisance"])), row["sign"])
              for row in rows}
    need(len(rows) == len(actual) == 272 and actual == expected, "case roster")
    widths = []
    for row in rows:
        v = F(row["record"]["voltage_mV"])
        truth = tuple(map(F, row["truth"]))
        known = row["estimate"]
        unknown = row["unverified"]
        need(v == F(known["voltage_mV"]) and p.contains(known, truth), "truth excluded")
        bounds = [tuple(map(F, interval)) for interval in known["normalized_bounds"]]
        width = max(hi-lo for lo, hi in bounds)
        need(all(0 <= lo <= hi <= 1 for lo, hi in bounds) and width <= h.WIDTH and
             width == F(known["max_width"]) and
             known["status"] == "CONDITIONAL_NARROW_ENCLOSURE", "width contract")
        widths.append(width)
        need(unknown["status"] == "CALIBRATION_UNVERIFIED" and
             unknown["normalized_bounds"] == [["0/1", "1/1"]]*4 and
             F(unknown["max_width"]) == 1, "unverified fallback")
        for result in (known, unknown):
            need(all(type(result.get(k)) is type(v) and result[k] == v
                     for k, v in h.NEGATIVE.items()), "authority leak")
        certs = row["current_certificates"]
        need(tuple(c["t_ms"] for c in certs) == h.TIMES and
             all(0 <= F(c["worst_code_error_pA"]) <= h.E and
                 0 <= F(c["jitter_ms"]) <= h.J for c in certs), "current evidence roster")
        errors = row["reference_code_errors"]
        need(set(errors) == set(h.REFS) and all(0 <= F(x) <= h.R for x in errors.values()),
             "reference error contract")
    need(max(widths) == F(value["panel_max_width"]), "panel maximum mismatch")


def write(args, value):
    raw = canonical(value)
    args.out.mkdir(parents=True, exist_ok=False)
    receipt = metadata(args, args.arch, raw)
    (args.out/"payload.json").write_bytes(raw)
    (args.out/"receipt.json").write_bytes(canonical(receipt))
    print(canonical(receipt).decode("ascii"), end="")


def native(args):
    identity(args)
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "G archive digest mismatch")
    need(platform.python_version() == PYTHON and platform.machine() == args.arch,
         "native execution profile mismatch")
    value = None
    try:
        value = p.report()
        validate(value)
    except Exception as exc:
        write(args, {"experiment": "CNEH-EXP-06H", "qualification": "FAIL_ENGINEERING_GATE",
                     "error_type": type(exc).__name__, "error": str(exc),
                     "unadmitted_observation": value, **h.NEGATIVE})
        print("FAIL_ENGINEERING_GATE:", type(exc).__name__, str(exc))
        return 1
    write(args, value)
    print(p.QUALIFIED)
    return 0


def verify_profiles(args, expected):
    directory(args.profiles, {"cneh06h-"+arch for arch in ARCHES})
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cneh06h-"+arch)
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
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "G archive digest mismatch")
    need(platform.python_version() == PYTHON, "locked Python mismatch")
    value = p.report()
    validate(value)
    raw = canonical(value)
    receipts = verify_profiles(args, raw)
    summary = {"experiment": "CNEH-EXP-06H", "qualification": p.QUALIFIED,
               "scope": h.SCOPE, "head_sha": args.head, "base_sha": args.base,
               "checkout_sha": args.checkout, "run_id": args.run_id, "run_attempt": args.attempt,
               "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
               "native_receipts": receipts, "native_process_receipts": 4,
               "native_exact_payload_pairs": 1, "independent_reconstructions": 1,
               "native_cases": 2*len(value["cases"]),
               "native_current_checks": 2*sum(len(row["current_certificates"]) for row in value["cases"]),
               "native_reference_checks": 2*sum(len(row["reference_code_errors"]) for row in value["cases"]),
               "native_negative_controls": 2*len(value["negative_controls"]),
               "native_narrow_truth_enclosures": 2*len(value["cases"]),
               "native_unverified_full_priors": 2*len(value["cases"]),
               "panel_max_width": value["panel_max_width"],
               "diameter_certificate": value["diameter_certificate"],
               "gamma_ablation_separation": value["gamma_ablation"]["separation"],
               "g_alias_recovered_worlds_per_arch": len(value["g_witness_recovery"]["reference_assisted_recovery"]),
               **h.NEGATIVE}
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
