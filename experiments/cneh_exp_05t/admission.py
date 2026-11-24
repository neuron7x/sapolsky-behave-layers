"""Independent sealed EXP05N artifact semantics; no native replay authority."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import stat
import struct
import zipfile

EXPERIMENT = "CNEH-EXP-05T"
ARTIFACTS = {
    ("A", "DEFAULT"): (14895699328, "2d1eced3a3e6444a2d1d088bdec586e72464ca6b353f09cda85fcd30529e0422"),
    ("A", "BASELINE"): (14896296016, "ce61695709a2a6879eb1e92d065c79864777cf748f35102427c921faf0e91dbf"),
    ("B", "DEFAULT"): (14896011684, "31f90b4bf129a274c9510f6001f020c7bdb8b6454c15c1b97ae3f6bbb57c6466"),
    ("B", "BASELINE"): (14896261054, "b4e3078754cad30170c6895453ae7319bfa8d8958eff088eb8ae428aff85811b"),
    ("AGGREGATE",): (14896181291, "c3caa1cb704cc595b6e6be3aebdafcac1f6841c45ac44404a9dc082d226ac656"),
}
SEEDS = (92001, 92002)
ARMS = ("WAIT", "G0", "G1", "ALTERNATE")
STEPS = 512
CHECKPOINTS = (0, 128, 256, 384, 480)
MODES = ((1, 0), (0, 1), (1, 1), (0, 0))
ARRAYS = ("V", "w", "g_ampa", "g_nmda", "g_gabaa", "I_ext")
CP_FIELDS = set("A_prev arrays branch configuration gain is_inhib matrix_sha256 mode physical_sha256 rng sigma_gain spikes tick".split())
PARTS = (CP_FIELDS - {"arrays"}) | set(ARRAYS)
ROW_FIELDS = {"tick", "mode", "state_sha256", "rng_sha256", "matrix_sha256", "physical_sha256", "parts"}
METRICS = {"A_t", "A_t1", "sigma", "gain", "spike_rate_hz"}
ONSETS = ((92001, "WAIT", 150), (92001, "G1", 331), (92002, "WAIT", 183),
          (92002, "WAIT", 265), (92002, "G1", 268), (92002, "ALTERNATE", 242))
MAX_MEMBER = 64 * 1024 * 1024


def need(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(canonical(value))


def file_sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def strict_json(raw):
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            need(k not in obj, "duplicate JSON key")
            obj[k] = v
        return obj

    def finite(token):
        raise ValueError("nonfinite JSON: " + token)

    return json.loads(raw, object_pairs_hook=unique, parse_constant=finite)


def hash_string(x):
    need(type(x) is str and re.fullmatch("[0-9a-f]{64}", x) is not None, "invalid SHA256")
    return x


def exact_float(x):
    need(type(x) is str, "non-string native float")
    v = float.fromhex(x)
    need(math.isfinite(v) and v.hex() == x, "nonfinite or noncanonical native float")
    return v


def mode_before(tick):
    return sum(tick > t for t in (128, 256, 384))


def group_at(arm, tick):
    return None if arm == "WAIT" else 0 if arm == "G0" else 1 if arm == "G1" else (tick // 64) % 2


def matrix_sha(mode):
    # Independent topology serialization, as pinned in EXP05I.
    vals = [0.] * (32 * 24) + [.5 * MODES[mode][j // 4] if i < 16 else 0.
                                for i in range(32) for j in range(8)]
    return sha(struct.pack(">" + "d" * len(vals), *vals))


MATRICES = tuple(matrix_sha(i) for i in range(4))


def physical_sha(data):
    raw = b""
    for key in ("V", "w", "g_ampa", "g_nmda", "g_gabaa"):
        values = data["arrays"][key]
        raw += struct.pack(">32d", *(exact_float(x) for x in values))
    return sha(raw + bytes(data["spikes"]) + struct.pack(">d", exact_float(data["gain"])))


def validate_checkpoint(cp, row):
    need(type(cp) is dict and set(cp) == {"data", "sha256"}, "checkpoint envelope")
    x = cp["data"]
    need(type(x) is dict and set(x) == CP_FIELDS, "checkpoint field roster")
    need(cp["sha256"] == digest(x) == row["state_sha256"], "checkpoint state anchor")
    need(type(x["tick"]) is int and x["tick"] == row["tick"] and type(x["mode"]) is int
         and x["mode"] == row["mode"], "checkpoint timing")
    need(x["matrix_sha256"] == MATRICES[x["mode"]] == row["matrix_sha256"], "checkpoint topology")
    need(set(x["arrays"]) == set(ARRAYS), "checkpoint array roster")
    for arr in x["arrays"].values():
        need(type(arr) is list and len(arr) == 32, "checkpoint array shape")
        for val in arr:
            exact_float(val)
    for key in ("spikes", "is_inhib"):
        need(type(x[key]) is list and len(x[key]) == 32 and all(type(v) is bool for v in x[key]), "checkpoint bit array")
    need(x["is_inhib"] == [False] * 24 + [True] * 8, "checkpoint population mask")
    need(set(x["branch"]) == {"eps", "ema_alpha", "_sigma_ema"}, "branch roster")
    for v in (*x["branch"].values(), x["gain"], x["A_prev"], x["sigma_gain"]):
        exact_float(v)
    rng = x["rng"]
    need(set(rng) == {"bit_generator", "has_uint32", "state", "uinteger"} and rng["bit_generator"] == "PCG64"
         and set(rng["state"]) == {"state", "inc"}, "RNG roster")
    need(all(type(v) is int and 0 <= v < 2**128 for v in rng["state"].values())
         and rng["state"]["inc"] % 2 == 1 and type(rng["has_uint32"]) is int
         and rng["has_uint32"] in (0, 1) and type(rng["uinteger"]) is int
         and 0 <= rng["uinteger"] < 2**32, "invalid PCG64 state")
    need(physical_sha(x) == x["physical_sha256"] == row["physical_sha256"], "physical checkpoint bytes mismatch")
    need(digest(rng) == row["rng_sha256"], "checkpoint RNG mismatch")
    expected = {k: digest(v) for k, v in x.items() if k != "arrays"} | {k: digest(v) for k, v in x["arrays"].items()}
    need(expected == row["parts"], "checkpoint constituent mismatch")


def validate_episode(ep, seed, arm):
    need(set(ep) == {"seed", "arm", "trace", "checkpoints", "restored_transitions"}
         and type(ep["seed"]) is int and (ep["seed"], ep["arm"]) == (seed, arm), "episode roster")
    rows = ep["trace"]
    need(type(rows) is list and len(rows) == STEPS + 1, "trace length")
    sigma, gain, activity = 1., 1., 0.
    for t, row in enumerate(rows):
        need(type(row) is dict and set(row) == (ROW_FIELDS | ({"group", "metrics"} if t < STEPS else set())), "row field roster")
        need(type(row["tick"]) is int and row["tick"] == t, "row tick")
        mode = mode_before(t)
        need(type(row["mode"]) is int and row["mode"] == mode and row["matrix_sha256"] == MATRICES[mode], "row topology schedule")
        for k in ("state_sha256", "rng_sha256", "matrix_sha256", "physical_sha256"):
            hash_string(row[k])
        parts = row["parts"]
        need(type(parts) is dict and set(parts) == PARTS, "row constituent roster")
        for v in parts.values():
            hash_string(v)
        need(parts["tick"] == digest(t) and parts["mode"] == digest(mode)
             and parts["matrix_sha256"] == digest(row["matrix_sha256"])
             and parts["physical_sha256"] == digest(row["physical_sha256"])
             and parts["rng"] == row["rng_sha256"], "row constituent semantic link")
        need(parts["gain"] == parts["sigma_gain"] == digest(gain.hex())
             and parts["A_prev"] == digest((1. if t == 0 else activity).hex()), "controller state link")
        need(parts["branch"] == digest({"eps": (1e-9).hex(), "ema_alpha": (.05).hex(),
                                        "_sigma_ema": sigma.hex()}), "branch state link")
        if t == STEPS:
            break
        group = row["group"]
        need((group is None or type(group) is int) and group == group_at(arm, t), "wrong action")
        need(type(row["metrics"]) is dict and set(row["metrics"]) == METRICS, "metric roster")
        m = {k: exact_float(v) for k, v in row["metrics"].items()}
        need(m["A_t"] == activity and 0 <= m["A_t1"] <= 32 and m["A_t1"].is_integer(), "activity recurrence")
        activity = m["A_t1"]
        sigma = (1. - .05) * sigma + .05 * (max(activity, 1.) / max(m["A_t"], 1.))
        gain = min(5., max(.2, gain - .001 * (sigma - 1.)))
        need(m["sigma"].hex() == sigma.hex() and m["gain"].hex() == gain.hex()
             and m["spike_rate_hz"].hex() == (activity / 32 / (.1 / 1000.)).hex(), "native metric recurrence")
    cps = ep["checkpoints"]
    need(type(cps) is list and tuple(cp["data"]["tick"] for cp in cps) == CHECKPOINTS
         and type(ep["restored_transitions"]) is int and ep["restored_transitions"] == 160, "checkpoint roster")
    for cp in cps:
        validate_checkpoint(cp, rows[cp["data"]["tick"]])


def validate_panel(value, worker, profile, attempt):
    need(set(value) == {"worker", "profile", "attempt", "fingerprint", "source", "native_attacks", "episodes", "panel_sha256"}, "report field roster")
    need(type(value["attempt"]) is int and (value["worker"], value["profile"], value["attempt"]) == (worker, profile, attempt), "report identity")
    need(value["source"]["commit"] == "c1de425ce4ece362e7f2feb2d9f24da5d3231014", "source identity")
    episodes = value["episodes"]
    need(len(episodes) == 8 and digest(episodes) == value["panel_sha256"], "panel roster/hash")
    for ep, (seed, arm) in zip(episodes, itertools.product(SEEDS, ARMS), strict=True):
        validate_episode(ep, seed, arm)
    for i in (0, 4):
        ref = episodes[i]["trace"]
        for ep in episodes[i:i+4]:
            need(ep["trace"][0]["state_sha256"] == ref[0]["state_sha256"] and
                 [r["rng_sha256"] for r in ep["trace"]] == [r["rng_sha256"] for r in ref], "paired initial/RNG mismatch")


def read_archive(path, key):
    aid, expected = ARTIFACTS[key]
    need(path.is_file() and not path.is_symlink() and file_sha(path) == expected, "external ZIP digest mismatch")
    names = {"report.json", "SHA256SUMS"} if key == ("AGGREGATE",) else {"run-1.json", "run-2.json", "install.json", "SHA256SUMS"}
    with zipfile.ZipFile(path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        need(len(infos) == len(names) and {i.filename for i in infos} == names, "ZIP roster")
        need(all(stat.S_IFMT(i.external_attr >> 16) in (0, stat.S_IFREG) and i.file_size <= MAX_MEMBER
                 for i in infos), "invalid ZIP member")
        raw = {name: z.read(name) for name in names}
    manifest = "".join(sha(raw[name]) + "  " + name + "\n" for name in sorted(names - {"SHA256SUMS"}))
    need(raw["SHA256SUMS"] == manifest.encode(), "inner manifest mismatch")
    need(file_sha(path) == expected, "archive changed while reading")
    return raw


def load(root):
    results = {}
    for key, (aid, _) in ARTIFACTS.items():
        raw = read_archive(root / (str(aid) + ".zip"), key)
        if key == ("AGGREGATE",):
            aggregate = strict_json(raw["report.json"])
            continue
        for attempt in (1, 2):
            value = strict_json(raw["run-" + str(attempt) + ".json"])
            validate_panel(value, *key, attempt)
            need(value["fingerprint"]["install_report_sha256"] == sha(raw["install.json"]), "pip report digest mismatch")
            results[(*key, attempt)] = value
    need(aggregate["native_panel_status"] == "FAIL_PANEL" and aggregate["scientific_promotion_authorized"] is False, "sealed verdict changed")
    return results


def analyze(records):
    a = records["A", "DEFAULT", 1]["episodes"]
    b = records["B", "DEFAULT", 1]["episodes"]
    comparisons = []
    for (ka, va), (kb, vb) in itertools.combinations(sorted(records.items()), 2):
        comparisons.append({"left": list(ka), "right": list(kb), "equal": va["episodes"] == vb["episodes"]})
    episodes = []
    onsets = []
    for x, y in zip(a, b, strict=True):
        ticks = []
        differences = []
        for p, q in zip(x["trace"], y["trace"], strict=True):
            if p == q:
                continue
            t = p["tick"]
            need(p["rng_sha256"] == q["rng_sha256"], "RNG mismatch")
            differences.append({"tick": t, "parts": sorted(k for k in PARTS if p["parts"][k] != q["parts"][k])})
            if not ticks or t != ticks[-1] + 1:
                need(t > 0 and x["trace"][t-1] == y["trace"][t-1], "onset without common preceding state")
                onsets.append((x["seed"], x["arm"], t))
            ticks.append(t)
        episodes.append({"seed": x["seed"], "arm": x["arm"], "differences": differences,
                         "all_scheduled_checkpoints_equal": x["checkpoints"] == y["checkpoints"],
                         "terminal_equal": x["trace"][-1] == y["trace"][-1]})
    need(tuple(onsets) == ONSETS, "frozen onset roster disagreement")
    return {"experiment": EXPERIMENT, "scientific_promotion_authorized": False,
            "scientific_promotion": "BLOCKED", "scope": "SEALED_HISTORICAL_STRUCTURAL_ADMISSION_ONLY",
            "native_panel_status": "FAIL_PRESERVED", "comparisons": comparisons,
            "episodes": episodes, "onsets": [list(x) for x in onsets],
            "digest_only_state_content": "NOT_INDEPENDENTLY_RECONSTRUCTIBLE",
            "archive_count": len(ARTIFACTS), "report_count": len(records),
            "mismatched_ticks": sum(len(x["differences"]) for x in episodes),
            "mismatched_episodes": sum(bool(x["differences"]) for x in episodes)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archives", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    report = analyze(load(args.archives))
    raw = canonical(report)
    if args.verify:
        need(args.out.read_bytes() == raw, "exact audit replay mismatch")
    else:
        with args.out.open("xb") as out:
            out.write(raw)
    print(raw.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
