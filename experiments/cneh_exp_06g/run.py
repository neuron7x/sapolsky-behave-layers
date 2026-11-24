"""Attempt-bound execution of the frozen joint-gauge diagnostic."""
from __future__ import annotations

import argparse
from fractions import Fraction as F
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06c.algebra import need
from experiments.cneh_exp_06f.run import canonical, directory, read_receipt, sha
from experiments.cneh_exp_06g import experiment as e, gauge as g

BASE = "18998f51fafdb710bba7e4cf08a4985b3d42ce41"
PARENT_SHA256 = "b240ccf85af8c81777f42dee888263c3b94f67642b279b948939867573eb50ee"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"


def identity(args):
    need(all(re.fullmatch(r"[0-9a-f]{40}", s) for s in
             (args.head, args.base, args.checkout)), "invalid commit identity")
    need(args.base == BASE, "unexpected integrated F base")
    need(all(re.fullmatch(r"[1-9][0-9]*", s) for s in
             (args.run_id, args.attempt)), "invalid run identity")


def metadata(args, arch, raw):
    identity(args)
    need(arch in ARCHES, "unsupported architecture")
    return {"experiment": "CNEH-EXP-06G", "head_sha": args.head,
            "base_sha": args.base, "checkout_sha": args.checkout,
            "run_id": args.run_id, "run_attempt": args.attempt, "arch": arch,
            "python": PYTHON, "parent_sha256": PARENT_SHA256,
            "payload_sha256": sha(raw), "scientific_promotion_authorized": False}


def validate(value):
    need(value["qualification"] == e.QUALIFIED and value["failures"] == [],
         "G engineering admission failed")
    need(all(type(value.get(k)) is type(v) and value[k] == v
             for k, v in g.NEGATIVE.items()), "negative evidence changed")
    need(value["scope"] == e.SCOPE and value["minimal_samples"] == e.theorem(),
         "theorem scope changed")
    need(value["sharp_certificate"] == g.sharp_certificate(), "sharp certificate mismatch")
    need(value["finite_witnesses"] == [g.finite_witness(n) for n in
         ("ZERO_DELAY", "SHARP_DELAY")], "finite witness mismatch")
    need(value["noiseless_latent_identifiability"] == "FAIL_COUNTEREXAMPLE",
         "negative identifiability evidence lost")
    need(value["negative_controls"] == e.negative_controls() and
         len(value["negative_controls"]) == 17, "negative control roster")
    rows = value["panel"]
    identities = {(x["anchor"], x["gain"], x["gamma"], x["delay_ms"], x["tau_ms"])
                  for x in rows}
    need(len(rows) == len(identities) == 48 and
         sum(len(x["absolute_errors_pA"]) for x in rows) == 336, "lift roster")
    need(all(x["times_ms"] == list(g.TIMES) and
             all(0 <= F(v) <= g.TOL for v in x["absolute_errors_pA"])
             for x in rows), "lift diagnostic threshold")
    need(value["sample_witnesses"] == [e.sample_witness(False), e.sample_witness(True)],
         "sample witness mismatch")


def write(args, value):
    raw = canonical(value)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    (args.out/"receipt.json").write_bytes(canonical(metadata(args, args.arch, raw)))
    print(canonical(metadata(args, args.arch, raw)).decode("ascii"), end="")


def native(args):
    identity(args)
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "F archive digest mismatch")
    need(platform.python_version() == PYTHON and platform.machine() == args.arch,
         "native execution profile mismatch")
    value = None
    try:
        value = e.report()
        validate(value)
    except Exception as exc:
        write(args, {"experiment": "CNEH-EXP-06G", "qualification": "FAIL_ENGINEERING_GATE",
                     "error_type": type(exc).__name__, "error": str(exc),
                     "unadmitted_observation": value, **g.NEGATIVE})
        print("FAIL_ENGINEERING_GATE:", type(exc).__name__, str(exc))
        return 1
    write(args, value)
    print(e.QUALIFIED)
    return 0


def verify_profiles(args, expected):
    directory(args.profiles, {"cneh06g-"+arch for arch in ARCHES})
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cneh06g-"+arch)
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
    need(sha(read_receipt(args.parent)) == PARENT_SHA256, "F archive digest mismatch")
    need(platform.python_version() == PYTHON, "locked Python mismatch")
    value = e.report()
    validate(value)
    raw = canonical(value)
    receipts = verify_profiles(args, raw)
    summary = {"experiment": "CNEH-EXP-06G", "qualification": e.QUALIFIED,
               "head_sha": args.head, "base_sha": args.base, "checkout_sha": args.checkout,
               "run_id": args.run_id, "run_attempt": args.attempt,
               "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
               "native_receipts": receipts, "native_process_receipts": 4,
               "native_exact_payload_pairs": 1, "independent_reconstructions": 1,
               "native_lifts": 2*len(value["panel"]),
               "native_sample_checks": 2*sum(len(row["absolute_errors_pA"]) for row in value["panel"]),
               "native_negative_controls": 2*len(value["negative_controls"]),
               "sharp_certificate": value["sharp_certificate"],
               "finite_witness_separations": {row["name"]: row["separation"] for row in value["finite_witnesses"]},
               "minimal_samples": value["minimal_samples"],
               "sample_diagnostic_extra_residuals_pA": {row["kind"]: row["extra_absolute_residual_pA"]
                                                       for row in value["sample_witnesses"]},
               "noiseless_latent_identifiability": "FAIL_COUNTEREXAMPLE",
               **g.NEGATIVE}
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
