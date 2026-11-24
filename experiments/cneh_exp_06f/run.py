"""Attempt-bound native execution and independent raw-evidence reconstruction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06c.algebra import need
from experiments.cneh_exp_06f import panel

BASE = "295b615dcdca355937bcd54c5e6c42a85df722b6"
PARENT_SHA256 = "156f3a735142e4b521371b50bfac31ba8c25a5c2be9d15c0d57d3f249426774a"
ARCHES = ("x86_64", "aarch64")
PYTHON = "3.12.16"
LIMIT = 16*1024*1024
QUALIFIED = "PASS_CONDITIONAL_CHANNEL_ENCLOSURE_ONLY"


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False)+"\n").encode("ascii")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_receipt(path):
    need(path.is_file() and not path.is_symlink(), "nonregular evidence file")
    need(path.stat().st_size <= LIMIT, "evidence size budget")
    with path.open("rb") as handle:
        data = handle.read(LIMIT+1)
    need(len(data) <= LIMIT, "evidence size budget")
    return data


def verify_parent(path):
    need(sha(read_receipt(path)) == PARENT_SHA256, "parent archive digest mismatch")


def identity(args):
    need(all(re.fullmatch(r"[0-9a-f]{40}", s) for s in
             (args.head, args.checkout, args.base)), "invalid commit identity")
    need(args.base == BASE, "unexpected qualified base")
    need(all(re.fullmatch(r"[1-9][0-9]*", s) for s in
             (args.run_id, args.attempt)), "invalid run identity")


def metadata(args, arch, raw):
    identity(args)
    need(arch in ARCHES, "unsupported architecture")
    return {"experiment": "CNEH-EXP-06F", "head_sha": args.head,
            "base_sha": args.base, "checkout_sha": args.checkout,
            "run_id": args.run_id, "run_attempt": args.attempt, "arch": arch,
            "python": PYTHON, "parent_sha256": PARENT_SHA256,
            "payload_sha256": sha(raw), "scientific_promotion_authorized": False}


def validate_report(value):
    need(value["qualification"] == QUALIFIED and value["failures"] == [],
         "channel panel not qualified")
    need(all(type(value.get(k)) is type(v) and value[k] == v
             for k, v in panel.NEGATIVE.items()), "negative evidence changed")
    cases = value["cases"]
    expected = {(s.name, i, signs) for s in panel.scenarios()
                for i in panel.TRUTHS for signs in panel.SIGNS}
    actual = {(x["scenario"], x["truth_id"], tuple(x["noise_signs"])) for x in cases}
    need(len(cases) == len(actual) == 384 and actual == expected, "case roster")
    need(sum(row["bounded_wide"] for row in cases) == 352 and
         sum(row["bounded_ideal"] for row in cases) == 32, "bounded roster")
    for row in cases:
        outcomes = row["outcomes"]
        need(set(outcomes) == {"C_NOMINAL", *panel.PROFILES}, "estimator roster")
        for result in outcomes.values():
            panel.no_authority(result["estimate"])
        for flag, profile in (("bounded_wide", "WIDE_SYNTHETIC"),
                              ("bounded_ideal", "IDEAL_QUANTIZED")):
            if row[flag]:
                need(outcomes[profile]["truth_enclosed"] is True and
                     profile in row["dewarped_certificates"], "compatible truth exclusion")
        unknown = outcomes["UNVERIFIED"]["estimate"]
        need(unknown["status"] == "CALIBRATION_UNVERIFIED" and
             unknown["normalized_bounds"] == [["0/1", "1/1"]]*4,
             "unverified fallback")
    need(len(value["negative_controls"]) == 18 and
         value["negative_controls"] == panel.negative_controls(), "negative control roster")
    need(value["sensor_width_identifiability"] == "FAIL_COUNTEREXAMPLE" and
         value["alias_witness"]["minimum_width"] == "1/12" and
         value["alias_witness"]["requested_width"] == "1/16",
         "alias no-go witness absent")
    need(value["scenario_summary"] == panel.summarize(cases), "summary mismatch")


def directory(path, expected):
    need(path.is_dir() and not path.is_symlink(), "nonregular evidence directory")
    need({p.name for p in path.iterdir()} == expected, "evidence roster")


def write_native(args, arch, value):
    raw = canonical(value)
    need(len(raw) <= LIMIT, "native evidence size budget")
    receipt = metadata(args, arch, raw)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    (args.out/"receipt.json").write_bytes(canonical(receipt))
    print(canonical(receipt).decode("ascii"), end="")


def native(args):
    identity(args)
    verify_parent(args.parent)
    need(platform.machine() == args.arch, "native machine mismatch")
    need(platform.python_version() == PYTHON, "locked Python mismatch")
    value = None
    try:
        value = panel.report()
        validate_report(value)
    except Exception as exc:
        # Preserve the unadmitted report, including incomplete cases.
        failed = {"experiment": "CNEH-EXP-06F", "qualification": "FAIL_ENGINEERING_GATE",
                  "error_type": type(exc).__name__, "error": str(exc),
                  "unadmitted_observation": value, **panel.NEGATIVE}
        write_native(args, args.arch, failed)
        print("FAIL_ENGINEERING_GATE:", type(exc).__name__, str(exc))
        return 1
    write_native(args, args.arch, value)
    print("PASS_CONDITIONAL_CHANNEL_ENCLOSURE_ONLY")
    return 0


def verify_profiles(args, expected):
    directory(args.profiles, {"cneh06f-"+arch for arch in ARCHES})
    receipts = []
    for arch in ARCHES:
        root = args.profiles/("cneh06f-"+arch)
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
    verify_parent(args.parent)
    need(platform.python_version() == PYTHON, "locked Python mismatch")
    value = panel.report()
    validate_report(value)
    raw = canonical(value)
    receipts = verify_profiles(args, raw)
    summary = {
        "experiment": "CNEH-EXP-06F", "qualification": QUALIFIED,
        "head_sha": args.head, "base_sha": args.base, "checkout_sha": args.checkout,
        "run_id": args.run_id, "run_attempt": args.attempt,
        "parent_sha256": PARENT_SHA256, "payload_sha256": sha(raw),
        "native_receipts": receipts, "native_process_receipts": 4,
        "native_exact_payload_pairs": 1, "independent_reconstructions": 1,
        "native_stress_cases": 2*len(value["cases"]),
        "native_bounded_wide_cases": 2*sum(x["bounded_wide"] for x in value["cases"]),
        "native_bounded_ideal_cases": 2*sum(x["bounded_ideal"] for x in value["cases"]),
        "native_negative_controls": 2*len(value["negative_controls"]),
        "sensor_width_identifiability": "FAIL_COUNTEREXAMPLE",
        "minimum_alias_width": value["alias_witness"]["minimum_width"],
        "scenario_summary": value["scenario_summary"],
        **panel.NEGATIVE,
    }
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
