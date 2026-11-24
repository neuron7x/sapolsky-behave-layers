"""Native evidence generation and independent aggregate reconstruction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06c.algebra import need
from experiments.cneh_exp_06e import quotient

PARENT_SHA256 = "2cc2ed3254a9467a32830976e0e0f6373f9e6d8e9904073d60dbb2c12bd02f49"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False)+"\n").encode("ascii")


def metadata(head, run_id, arch, payload):
    need(re.fullmatch(r"[0-9a-f]{40}", head) is not None, "invalid head SHA")
    need(re.fullmatch(r"[1-9][0-9]*", run_id) is not None, "invalid run ID")
    need(arch in ARCHES, "unsupported architecture")
    return {
        "experiment": "CNEH-EXP-06E",
        "head_sha": head,
        "run_id": run_id,
        "arch": arch,
        "python": PYTHON,
        "parent_sha256": PARENT_SHA256,
        "payload_sha256": sha(payload),
        "scientific_promotion_authorized": False,
    }


def verify_parent(path):
    need(sha(path.read_bytes()) == PARENT_SHA256, "parent archive digest mismatch")


def native(args):
    verify_parent(args.parent)
    need(platform.machine() == args.arch, "native machine mismatch")
    need(platform.python_version() == PYTHON, "locked Python mismatch")
    payload = canonical(quotient.report())
    receipt = metadata(args.head, args.run_id, args.arch, payload)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(payload)
    (args.out/"receipt.json").write_bytes(canonical(receipt))
    print(canonical(receipt).decode("ascii"), end="")


def aggregate(args):
    verify_parent(args.parent)
    need(platform.python_version() == PYTHON, "locked Python mismatch")
    expected_report = quotient.report()
    expected = canonical(expected_report)
    need({p.name for p in args.profiles.iterdir()} ==
         {"cneh06e-"+arch for arch in ARCHES}, "native profile roster")
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cneh06e-"+arch)
        need({p.name for p in root.iterdir()} == {"receipt.json", "payload.json"},
             "native evidence file roster")
        raw = (root/"payload.json").read_bytes()
        need(raw == expected, "native raw payload differs from fresh reconstruction")
        receipt = metadata(args.head, args.run_id, arch, raw)
        need((root/"receipt.json").read_bytes() == canonical(receipt),
             "native receipt mismatch")
        receipts.append(receipt)
    summary = {
        "experiment": "CNEH-EXP-06E",
        "qualification": "PASS_EXACT_SYNTHETIC_QUOTIENT_ONLY",
        "head_sha": args.head,
        "run_id": args.run_id,
        "parent_sha256": PARENT_SHA256,
        "payload_sha256": sha(expected),
        "native_receipts": receipts,
        "native_lifts": 2*len(expected_report["cases"]),
        "native_sample_checks": 2*sum(x["decimal_samples_checked"]
                                      for x in expected_report["cases"]),
        "native_negative_controls": 2*len(expected_report["negative_controls"]),
        "native_exact_payload_pairs": 1,
        "historical_count_observability": "FAIL_PRESERVED",
        "historical_nominal_ood": "FAIL_PRESERVED",
        "historical_noise_width": "FAIL_PRESERVED",
        "historical_2ms_reachability": "FAIL_PRESERVED",
        "scientific_promotion": "BLOCKED",
        "scientific_promotion_authorized": False,
        "closed_loop_efficacy": "BLOCKED",
        "blind_causal_cohort": "BLOCKED",
        "calibration": "NOT_TESTED",
    }
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(expected)
    (args.out/"report.json").write_bytes(canonical(summary))
    roster = ("payload.json", "report.json")
    sums = "".join(sha((args.out/name).read_bytes())+"  "+name+"\n" for name in roster)
    (args.out/"SHA256SUMS").write_text(sums, encoding="ascii")
    print(canonical(summary).decode("ascii"), end="")


def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("native", "aggregate"):
        sub = subs.add_parser(name)
        sub.add_argument("--parent", type=Path, required=True)
        sub.add_argument("--head", required=True)
        sub.add_argument("--run-id", required=True)
        sub.add_argument("--out", type=Path, required=True)
        if name == "native":
            sub.add_argument("--arch", choices=ARCHES, required=True)
        else:
            sub.add_argument("--profiles", type=Path, required=True)
    args = parser.parse_args()
    (native if args.command == "native" else aggregate)(args)


if __name__ == "__main__":
    main()
