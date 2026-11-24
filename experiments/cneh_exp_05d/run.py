"""Prospective full-state replay of the certified numerical lineage."""
from __future__ import annotations

import argparse
import decimal
import gzip
import itertools
import json
import math
from pathlib import Path
import random
import zipfile

from experiments.cneh_exp_05n import run as n
from experiments.cneh_exp_05t import admission as a
from experiments.cneh_exp_05d import certified as c

EXPERIMENT = "CNEH-EXP-05D"
SEEDS = (93001, 93002)
WITNESS_SHA = "faea2bd5bd390a630464727b150111cc0726fcfd4c2373c4eaf9d6c80358b23e"
PRE_ANCHORS = (
    "b8320ed406ce4ffe2fb1f625cc8af51049297475be452a008cb18250b2db0f82",
    "f148ccc4ce732be43e1b92f2d9e1954c04d0e7e24973c30191e28502be037670",
    "ef89a2b0355a42bde72a2f076b5f2f8a166d88a85c159d5a5c633fc37f1d8dda",
    "3932b6157e94226ea852ad9a43df04e70094b8fd62b0e3d1d0166791c0a97735",
    "61f146a8947854226cbd0d56cd02c132623c0396beb6155aab4f6d04d03206d0",
    "0004af626f5e0fa48c6cc7603474d4ae5efc87d736bd10e7fad16d7ecfa353b0",
)


def witnesses(path):
    a.need(a.file_sha(path) == WITNESS_SHA, "sealed witness ZIP identity")
    with zipfile.ZipFile(path) as z:
        names = {"baseline.json", "default.json", "no-icl.json", "install.json", "SHA256SUMS"}
        a.need(len(z.namelist()) == len(names) and set(z.namelist()) == names, "witness ZIP roster")
        raw = {name: z.read(name) for name in names}
    expected = "".join(a.sha(raw[k]) + "  " + k + "\n" for k in sorted(names - {"SHA256SUMS"}))
    a.need(raw["SHA256SUMS"] == expected.encode() and a.file_sha(path) == WITNESS_SHA, "witness manifest")
    record = a.strict_json(raw["default.json"])
    a.need((record["worker"], record["profile"]) == ("A", "DEFAULT"), "witness identity")
    cases = record["cases"]
    a.need(tuple((x["seed"], x["arm"], x["tick"]) for x in cases) == a.ONSETS, "witness roster")
    for row, anchor in zip(cases, PRE_ANCHORS, strict=True):
        a.need(row["status"] == "CAPTURED" and row["pre_expected"] == anchor
               and row["pre"]["sha256"] == a.digest(row["pre"]["data"]) == anchor
               and row["native"]["post"]["sha256"] == row["B_expected"], "witness state anchor")
    return cases


def fixtures(cases):
    values = {float.fromhex(x) for row in cases for call in row["native"]["exp"] for x in call["input"]["values"]}
    rng = random.Random(93000)
    values.update(rng.uniform(-32., 32.) for _ in range(256))
    values.update((-32., math.nextafter(-32., 0.), -20., -1., -0., 0.,
                   math.nextafter(0., 1.), math.nextafter(0., -1.), .1, 1., 20.,
                   math.nextafter(32., 0.), 32.))
    result = []
    for x in sorted(values):
        actual, precision = c.certificate(x)
        reference, terms = c.independent_taylor(x)
        a.need(actual == reference, "independent rational exp mismatch")
        result.append({"input": x.hex(), "output": c.from_bits(actual).hex(),
                       "certificate_precision": precision, "taylor_terms": terms})
    return result


def episode(seed, arm, rt):
    np = rt["np"]
    net, mode = n.initial(seed, rt), 0
    states, rows, checkpoints = [], [], []
    for t in range(n.STEPS + 1):
        state = n.snapshot(net, mode, t, np)
        states.append(state)
        row = n.row(state)
        if t in n.CHECKPOINTS:
            checkpoints.append(n.seal(state))
        if t < n.STEPS:
            row["group"] = n.action(arm, t)
            mode, row["metrics"] = n.step(net, mode, arm, t, np)
        rows.append(row)
    final = n.snapshot(net, mode, n.STEPS, np)
    for cp in checkpoints:
        start = cp["data"]["tick"]
        clone, clone_mode = n.restore(cp, rows[start]["state_sha256"], seed, start, rt)
        for t in range(start, start + n.SUFFIX + 1):
            a.need(n.snapshot(clone, clone_mode, t, np) == states[t], "full checkpoint suffix state mismatch")
            if t < start + n.SUFFIX:
                clone_mode, metrics = n.step(clone, clone_mode, arm, t, np)
                a.need(metrics == rows[t]["metrics"], "full checkpoint suffix metric mismatch")
    a.need(n.snapshot(net, mode, n.STEPS, np) == final, "checkpoint replay mutated reference")
    return {"episode": {"seed": seed, "arm": arm, "trace": rows, "checkpoints": checkpoints,
                        "restored_transitions": len(n.CHECKPOINTS) * n.SUFFIX},
            "full_states": states}


def validate_full(records):
    a.need([(v["episode"]["seed"], v["episode"]["arm"]) for v in records] ==
           list(itertools.product(SEEDS, n.ARMS)), "fresh full-state roster")
    for v in records:
        ep, states = v["episode"], v["full_states"]
        a.validate_episode(ep, ep["seed"], ep["arm"])
        a.need(len(states) == n.STEPS + 1, "full-state roster")
        for state, row in zip(states, ep["trace"], strict=True):
            a.validate_checkpoint({"data": state, "sha256": row["state_sha256"]}, row)
    for i in (0, 4):
        ref = records[i]["episode"]["trace"]
        for v in records[i:i+4]:
            rows = v["episode"]["trace"]
            a.need(rows[0]["state_sha256"] == ref[0]["state_sha256"] and
                   [r["rng_sha256"] for r in rows] == [r["rng_sha256"] for r in ref], "paired initial/RNG")


def witness_step(case, rt):
    seed, arm, tick = (case[k] for k in ("seed", "arm", "tick"))
    net, mode = n.restore(case["pre"], case["pre_expected"], seed, tick-1, rt)
    mode, metrics = n.step(net, mode, arm, tick-1, rt["np"])
    post = n.seal(n.snapshot(net, mode, tick, rt["np"]))
    return {"seed": seed, "arm": arm, "tick": tick, "pre_sha256": case["pre_expected"],
            "post": post, "metrics": metrics, "matches_historical_baseline": post["sha256"] == case["A_expected"]}


def run(args):
    lock = n.pinned.strict_json(n.LOCK.read_bytes())
    before = n.pinned.validate_source(args.source, lock)
    rt = n.pinned.load_runtime(args.source, lock)
    cases = witnesses(args.witness)
    fixture_report = fixtures(cases)
    with c.corrected_backend(rt) as counts:
        local = [witness_step(case, rt) for case in cases]
        records = [episode(seed, arm, rt) for seed, arm in itertools.product(SEEDS, n.ARMS)]
    total_steps = len(cases) + len(records) * (n.STEPS + len(n.CHECKPOINTS) * n.SUFFIX)
    a.need(counts["operation_counts"] == {"ADEX": 32 * total_steps, "NMDA": 32 * total_steps, "DECAY": 3 * total_steps},
           "corrected operation roster")
    a.need(sum(counts["certificate_precisions"].values()) == 67 * total_steps, "certificate count")
    validate_full(records)
    a.need(n.pinned.validate_source(args.source, lock) == before, "pinned source changed")
    panel = {"fixtures": fixture_report, "witnesses": local, "records": records, "counts": counts}
    raw = a.canonical(panel)
    fingerprint = n.fingerprint(rt, args.profile, args.install_report)
    fingerprint.update(decimal_version=decimal.__version__, libmpdec_version=decimal.__libmpdec_version__,
                       kernel_sha256=a.file_sha(Path(c.__file__)), runner_sha256=a.file_sha(Path(__file__)))
    with args.out.open("xb") as out:
        out.write(gzip.compress(raw, mtime=0))
    summary = {"worker": args.worker, "profile": args.profile, "attempt": args.attempt,
               "fingerprint": fingerprint, "panel_sha256": a.sha(raw),
               "compressed_sha256": a.file_sha(args.out), "fixture_count": len(fixture_report),
               "operation_counts": counts["operation_counts"], "certificate_precisions": counts["certificate_precisions"]}
    with args.receipt.open("xb") as out:
        out.write(a.canonical(summary))
    print(a.canonical({k: v for k, v in summary.items() if k != "fingerprint"}).decode(), end="")


def first_difference(ref, other):
    if ref == other:
        return None
    for a1, b1 in zip(ref["records"], other["records"], strict=True):
        for t, (x, y) in enumerate(zip(a1["full_states"], b1["full_states"], strict=True)):
            if x != y:
                return {"seed": a1["episode"]["seed"], "arm": a1["episode"]["arm"], "tick": t,
                        "fields": sorted(k for k in x if x[k] != y[k]),
                        "arrays": sorted(k for k in x["arrays"] if x["arrays"][k] != y["arrays"][k])}
        if a1 != b1:
            return {"seed": a1["episode"]["seed"], "arm": a1["episode"]["arm"], "scope": "metrics_or_checkpoint"}
    return {"scope": "fixtures_witnesses_or_operation_counts"}


def validate_witnesses(rows):
    a.need(tuple((x["seed"], x["arm"], x["tick"]) for x in rows) == a.ONSETS, "corrected witness roster")
    for row, anchor in zip(rows, PRE_ANCHORS, strict=True):
        state = row["post"]["data"]
        a.need(row["pre_sha256"] == anchor and state["tick"] == row["tick"], "corrected witness anchor")
        a.validate_checkpoint(row["post"], n.row(state))
        a.need(set(row["metrics"]) == a.METRICS, "corrected witness metric roster")
        for v in row["metrics"].values():
            a.exact_float(v)


def aggregate(root):
    comparisons, ref = [], None
    for worker, profile in itertools.product(n.WORKERS, n.PROFILES):
        folder = root / ("cneh-exp-05d-" + worker + "-" + profile)
        names = {"install.json", "panel-1.json.gz", "panel-2.json.gz", "receipt-1.json", "receipt-2.json", "SHA256SUMS"}
        a.need({p.name for p in folder.iterdir()} == names, "profile artifact roster")
        manifest = "".join(a.file_sha(folder / k) + "  " + k + "\n" for k in sorted(names - {"SHA256SUMS"}))
        a.need((folder / "SHA256SUMS").read_text() == manifest, "profile manifest mismatch")
        for attempt in n.ATTEMPTS:
            receipt = a.strict_json((folder / ("receipt-" + str(attempt) + ".json")).read_bytes())
            path = folder / ("panel-" + str(attempt) + ".json.gz")
            a.need((receipt["worker"], receipt["profile"], receipt["attempt"]) == (worker, profile, attempt)
                   and receipt["compressed_sha256"] == a.file_sha(path), "receipt identity")
            raw = gzip.decompress(path.read_bytes())
            a.need(a.sha(raw) == receipt["panel_sha256"], "panel digest")
            value = a.strict_json(raw)
            a.need(a.canonical(value) == raw, "noncanonical panel")
            validate_full(value["records"])
            validate_witnesses(value["witnesses"])
            a.need(receipt["fixture_count"] == len(value["fixtures"]) and receipt["operation_counts"] == value["counts"]["operation_counts"]
                   and receipt["certificate_precisions"] == value["counts"]["certificate_precisions"], "receipt count binding")
            for fixture in value["fixtures"]:
                x = a.exact_float(fixture["input"])
                a.need(c.certificate(x)[0] == c.bits(a.exact_float(fixture["output"])), "independent fixture replay")
            if ref is None:
                ref = value
            comparisons.append({"worker": worker, "profile": profile, "attempt": attempt,
                                "panel_sha256": receipt["panel_sha256"], "fingerprint": receipt["fingerprint"],
                                "difference": first_difference(ref, value)})
    a.need(len(comparisons) == 8, "complete panel roster")
    passed = all(x["difference"] is None for x in comparisons)
    return {"experiment": EXPERIMENT, "scientific_promotion_authorized": False,
            "scientific_promotion": "BLOCKED", "scope": "CORRECTED_FINITE_ENGINEERING_PANEL_ONLY",
            "historical_native_replay": "FAIL_PRESERVED", "qualification": "PASS_PANEL_ONLY" if passed else "FAIL_PANEL",
            "reports": len(comparisons), "full_states": len(comparisons) * 8 * (n.STEPS + 1),
            "witnesses_per_report": len(ref["witnesses"]), "fixture_count": len(ref["fixtures"]),
            "counts_per_report": ref["counts"], "comparisons": comparisons}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--source", type=Path, required=True)
    r.add_argument("--witness", type=Path, required=True)
    r.add_argument("--worker", choices=n.WORKERS, required=True)
    r.add_argument("--profile", choices=n.PROFILES, required=True)
    r.add_argument("--attempt", type=int, choices=n.ATTEMPTS, required=True)
    r.add_argument("--install-report", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--receipt", type=Path, required=True)
    g = sub.add_parser("aggregate")
    g.add_argument("--profiles", type=Path, required=True)
    g.add_argument("--out", type=Path, required=True)
    g.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.command == "run":
        run(args)
        return 0
    result = aggregate(args.profiles)
    raw = a.canonical(result)
    if args.verify:
        a.need(args.out.read_bytes() == raw, "exact aggregate replay mismatch")
    else:
        with args.out.open("xb") as out:
            out.write(raw)
    print(a.canonical({k: v for k, v in result.items() if k != "comparisons"}).decode(), end="")
    return 0 if result["qualification"] == "PASS_PANEL_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
