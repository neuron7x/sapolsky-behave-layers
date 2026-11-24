"""Externally anchored admission and independent equation verification of EXP05D."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import stat
import zipfile

from experiments.cneh_exp_05v import oracle as o
from experiments.cneh_exp_05d import run as legacy

EXPERIMENT = "CNEH-EXP-05V"
ANCHORS = {
    ("A", "DEFAULT"): (14896119541, "ebf34e36809c2fd9d9d785286f04f6627972bf70517c3d7451235648a770bdb8"),
    ("A", "BASELINE"): (14897032523, "05d42e3e9dd305cb82e006cfb0c8c4f2021366b14875585d0141d558750464de"),
    ("B", "DEFAULT"): (14896982017, "6eb1feaed048b36f28065a82da930703078d13e998a644638ffccd4b96d4ff95"),
    ("B", "BASELINE"): (14896567844, "26e79f5b03176b6fb9dc3ce2891559627c10456eb34a4e3e4af126424c19120e"),
    ("AGGREGATE",): (14896977776, "da12476c2e8d26fdf35d825d42e3a82fee42b6da504d764209e5b18723a112c6"),
    ("WITNESS",): (14896203693, "faea2bd5bd390a630464727b150111cc0726fcfd4c2373c4eaf9d6c80358b23e"),
}
PANEL_NAMES = {"install.json", "panel-1.json.gz", "panel-2.json.gz",
               "receipt-1.json", "receipt-2.json", "SHA256SUMS"}
ONSETS = ((92001, "WAIT", 150), (92001, "G1", 331), (92002, "WAIT", 183),
          (92002, "WAIT", 265), (92002, "G1", 268), (92002, "ALTERNATE", 242))
ROSTER = tuple(itertools.product((93001, 93002), o.ARMS))
MAX_RAW = 128 * 1024 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            o.need(key not in out, "duplicate JSON key")
            out[key] = value
        return out

    def bad(token):
        raise ValueError("nonfinite JSON: " + token)

    def finite(token):
        value = float(token)
        o.need(math.isfinite(value), "nonfinite JSON number")
        return value

    return json.loads(raw, object_pairs_hook=unique, parse_constant=bad, parse_float=finite)


def read_zip(raw, expected, names):
    import io
    o.need(sha(raw) == expected, "external artifact digest mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        o.need(len(infos) == len(names) and {i.filename for i in infos} == names, "ZIP roster")
        o.need(all(not i.is_dir() and stat.S_IFMT(i.external_attr >> 16) in (0, stat.S_IFREG)
                   and i.file_size <= MAX_RAW for i in infos), "ZIP member")
        files = {i.filename: z.read(i) for i in infos}
    manifest = "".join(sha(files[k]) + "  " + k + "\n" for k in sorted(names - {"SHA256SUMS"}))
    o.need(files["SHA256SUMS"] == manifest.encode(), "inner manifest mismatch")
    return files


def load_zip(root, key):
    aid, digest = ANCHORS[key]
    names = ({"report.json", "SHA256SUMS"} if key == ("AGGREGATE",) else
             {"default.json", "baseline.json", "no-icl.json", "install.json", "SHA256SUMS"}
             if key == ("WITNESS",) else PANEL_NAMES)
    path = root / (str(aid) + ".zip")
    o.need(path.is_file() and not path.is_symlink(), "artifact path")
    return read_zip(path.read_bytes(), digest, names)


def panel_raw(files, key, attempt):
    import io
    receipt = strict_json(files[f"receipt-{attempt}.json"])
    o.need((receipt["worker"], receipt["profile"], receipt["attempt"]) == (*key, attempt), "receipt identity")
    packed = files[f"panel-{attempt}.json.gz"]
    o.need(sha(packed) == receipt["compressed_sha256"], "compressed panel hash")
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(MAX_RAW+1)
    o.need(len(raw) <= MAX_RAW and sha(raw) == receipt["panel_sha256"], "raw panel hash")
    o.need(receipt["fingerprint"]["install_report_sha256"] == sha(files["install.json"]), "install binding")
    return raw, receipt


def admit(root):
    aggregate = strict_json(load_zip(root, ("AGGREGATE",))["report.json"])
    o.need(aggregate["qualification"] == "PASS_PANEL_ONLY" and aggregate["reports"] == 8
           and aggregate["full_states"] == 32832 and aggregate["scientific_promotion_authorized"] is False
           and aggregate["historical_native_replay"] == "FAIL_PRESERVED", "aggregate scope")
    reference = None
    receipts = []
    for key in (("A", "DEFAULT"), ("A", "BASELINE"), ("B", "DEFAULT"), ("B", "BASELINE")):
        files = load_zip(root, key)
        for attempt in (1, 2):
            raw, receipt = panel_raw(files, key, attempt)
            if reference is None:
                reference = raw
            o.need(raw == reference, "nonidentical sealed panel")
            receipts.append(receipt)
    value = strict_json(reference)
    o.need(o.canonical(value) == reference and set(value) == {"fixtures", "witnesses", "records", "counts"}, "panel encoding")
    comparisons = {(x["worker"], x["profile"], x["attempt"]): x for x in aggregate["comparisons"]}
    o.need(len(aggregate["comparisons"]) == len(comparisons) == 8, "aggregate comparison roster")
    for receipt in receipts:
        key = (receipt["worker"], receipt["profile"], receipt["attempt"])
        comp = comparisons[key]
        o.need(comp["difference"] is None and comp["panel_sha256"] == receipt["panel_sha256"]
               and comp["fingerprint"] == receipt["fingerprint"], "aggregate receipt mismatch")
        o.need(receipt["fixture_count"] == len(value["fixtures"]) == 650
               and receipt["operation_counts"] == value["counts"]["operation_counts"]
               and receipt["certificate_precisions"] == value["counts"]["certificate_precisions"], "count binding")
    o.need(aggregate["counts_per_report"] == value["counts"], "aggregate operation count")
    witness = strict_json(load_zip(root, ("WITNESS",))["default.json"])
    o.need((witness["worker"], witness["profile"]) == ("A", "DEFAULT"), "witness identity")
    return value, witness["cases"], sha(reference)


def verify_records(records, arithmetic):
    o.need(tuple((r["episode"]["seed"], r["episode"]["arm"]) for r in records) == ROSTER, "episode roster")
    # Reuse the historical structural checks as a separate layer, never as
    # the arithmetic oracle. They are also the target of the counterexample.
    legacy.validate_full(records)
    count = 0
    for rec in records:
        ep, states = rec["episode"], rec["full_states"]
        o.need(len(states) == len(ep["trace"]) == 513, "state/trace length")
        for t in range(512):
            o.check_transition(states[t], states[t+1], ep["trace"][t]["metrics"], ep["arm"], arithmetic)
            count += 1
    return count


def verify_witnesses(cases, corrected, arithmetic):
    for rows in (cases, corrected):
        o.need(tuple((x["seed"], x["arm"], x["tick"]) for x in rows) == ONSETS, "witness roster")
    for case, row in zip(cases, corrected, strict=True):
        pre, post = case["pre"]["data"], row["post"]["data"]
        o.need(case["pre_expected"] == case["pre"]["sha256"] == row["pre_sha256"] == o.digest(pre), "witness prestate anchor")
        o.need(row["post"]["sha256"] == o.digest(post) and post["tick"] == row["tick"], "witness poststate anchor")
        o.need(row["matches_historical_baseline"] is (row["post"]["sha256"] == case["A_expected"]), "witness historical comparison")
        o.check_transition(pre, post, row["metrics"], row["arm"], arithmetic)
    return len(cases)


def verify_fixtures(fixtures, arithmetic):
    o.need(len(fixtures) == 650 and len({x["input"] for x in fixtures}) == 650, "fixture roster")
    for x in fixtures:
        o.need(arithmetic.exp(o.f(x["input"])).hex() == x["output"], "independent exp fixture mismatch")


def bump(value):
    return math.nextafter(o.f(value), math.inf).hex()


def reject(call):
    try:
        call()
    except (ValueError, TypeError, KeyError, OverflowError, zipfile.BadZipFile) as exc:
        return str(exc)
    raise ValueError("adversarial mutation escaped")


def attacks(records, root):
    # A real archived interior state with every local digest recomputed.
    # Preserve original external archive; legacy semantic validation is invoked
    # on a temporary in-memory copy only.
    rec = records[0]
    ep = rec["episode"]
    old, oldrow = rec["full_states"][1], ep["trace"][1]
    forged = copy.deepcopy(old)
    forged["arrays"]["V"][0] = bump(forged["arrays"]["V"][0])
    forged["physical_sha256"] = o.physical_sha(forged)
    forged_row = {**legacy.n.row(forged), "group": oldrow["group"], "metrics": oldrow["metrics"]}
    try:
        rec["full_states"][1], ep["trace"][1] = forged, forged_row
        legacy.validate_full(records)
        old_admits = True
    finally:
        rec["full_states"][1], ep["trace"][1] = old, oldrow
    pre, post = rec["full_states"][:2]
    metrics = ep["trace"][0]["metrics"]
    rejected = {}
    for name in o.ARRAYS:
        q = copy.deepcopy(post)
        q["arrays"][name][0] = bump(q["arrays"][name][0])
        q["physical_sha256"] = o.physical_sha(q)
        rejected[name] = reject(lambda: o.check_transition(pre, q, metrics, ep["arm"], o.Arithmetic()))
    for name in ("rng", "mode", "configuration", "spikes", "gain", "branch", "metric"):
        q, m = copy.deepcopy(post), copy.deepcopy(metrics)
        if name == "rng":
            q["rng"]["state"]["state"] ^= 1
        elif name == "mode":
            q["mode"], q["matrix_sha256"] = 1, o.MATRICES[1]
        elif name == "configuration":
            q["configuration"]["adex"]["C_pF"] = 151.
        elif name == "spikes":
            q["spikes"][0] = not q["spikes"][0]
        elif name == "gain":
            q["gain"] = q["sigma_gain"] = bump(q["gain"])
        elif name == "branch":
            q["branch"]["_sigma_ema"] = bump(q["branch"]["_sigma_ema"])
        else:
            m["gain"] = bump(m["gain"])
        q["physical_sha256"] = o.physical_sha(q)
        rejected[name] = reject(lambda: o.check_transition(pre, q, m, ep["arm"], o.Arithmetic()))
    for name, val in (("exp_nan", float("nan")), ("exp_inf", float("inf")), ("exp_domain", 33.), ("exp_type", 1)):
        rejected[name] = reject(lambda: o.certificate(val))
    rejected["duplicate_json"] = reject(lambda: strict_json(b'{"x":1,"x":2}'))
    rejected["nonfinite_json"] = reject(lambda: strict_json(b'{"x":1e999}'))
    rejected["missing_episode"] = reject(lambda: verify_records(records[:-1], o.Arithmetic()))
    aid, anchor = ANCHORS["A", "DEFAULT"]
    raw = (root / (str(aid)+".zip")).read_bytes()
    rejected["external_tamper"] = reject(lambda: read_zip(raw+b"tamper", anchor, PANEL_NAMES))
    o.need(old_admits and len(rejected) == 21, "negative control roster")
    return {"legacy_structural_false_acceptance": old_admits, "rejected": rejected}


def audit(root):
    panel, cases, digest = admit(root)
    arithmetic = o.Arithmetic()
    transitions = verify_records(panel["records"], arithmetic)
    witness_count = verify_witnesses(cases, panel["witnesses"], arithmetic)
    verify_fixtures(panel["fixtures"], arithmetic)
    o.need(transitions == 4096 and witness_count == 6 and arithmetic.count == 275484, "oracle count")
    attack_report = attacks(panel["records"], root)
    return {"experiment": EXPERIMENT, "scientific_promotion_authorized": False,
            "scientific_promotion": "BLOCKED", "historical_native_replay": "FAIL_PRESERVED",
            "scope": "EXACT_DISCRETE_TRANSITIONS_CONDITIONAL_ON_SEALED_INITIAL_STATES",
            "external_archives": len(ANCHORS), "producer_reports": 8, "unique_raw_panels": 1,
            "panel_sha256": digest, "fresh_seeds": 2, "arms": 4, "unique_transitions": transitions,
            "sealed_witness_transitions": witness_count, "exp_fixtures": 650,
            "independent_exp_evaluations": arithmetic.count, "precision_histogram": arithmetic.precisions,
            "attacks": attack_report,
            "unqualified": ["seed_to_initial_state", "continuous_time_convergence", "biophysical_validity",
                            "multiscale_coherence", "closed_loop_causal_efficacy", "scientific_promotion"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archives", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    raw = o.canonical(audit(args.archives))
    if args.verify:
        o.need(args.out.read_bytes() == raw, "audit replay mismatch")
    else:
        with args.out.open("xb") as f:
            f.write(raw)
    print(raw.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
