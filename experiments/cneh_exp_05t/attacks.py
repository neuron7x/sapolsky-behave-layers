"""Attack copies of sealed evidence, not the immutable source archives."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import tempfile
import zipfile

from experiments.cneh_exp_05t import admission as a


def rejected(action):
    try:
        action()
    except (ValueError, KeyError, TypeError, OverflowError, zipfile.BadZipFile):
        return True
    return False


def attack(root):
    key = ("A", "DEFAULT")
    original = root / (str(a.ARTIFACTS[key][0]) + ".zip")
    raw = a.read_archive(original, key)
    value = a.strict_json(raw["run-1.json"])
    original_ep = value["episodes"][0]
    mutations = {
        "WRONG_ACTION": lambda e: e["trace"][150].update(group=1),
        "WRONG_ROUTE": lambda e: e["trace"][150].update(mode=99),
        "MISSING_METRICS": lambda e: e["trace"][150].pop("metrics"),
        "INVALID_METRIC": lambda e: e["trace"][150]["metrics"].update(gain="not-a-float"),
        "MISSING_COMPONENT": lambda e: e["trace"][150]["parts"].pop("V"),
        "FORGED_CHECKPOINT_DIGEST": lambda e: e["trace"][128].update(state_sha256="0"*64),
        "OUT_OF_ROSTER_SEED": lambda e: e.update(seed=99999),
        "INCONSISTENT_PHYSICAL_HASH": lambda e: e["trace"][150].update(physical_sha256="0"*64),
    }
    results = {}
    for name, mutate in mutations.items():
        ep = copy.deepcopy(original_ep)
        mutate(ep)
        results[name] = rejected(lambda: a.validate_episode(ep, 92001, "WAIT"))
    results["DUPLICATE_JSON"] = rejected(lambda: a.strict_json(b'{"gain":1,"gain":2}'))
    # Deliberately syntactically valid state hash at a noncheckpoint: structural
    # admission cannot reconstruct latent bytes that were never archived.
    ep = copy.deepcopy(original_ep)
    ep["trace"][150]["state_sha256"] = "0"*64
    a.validate_episode(ep, 92001, "WAIT")
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "mutated.zip"
        target.write_bytes(original.read_bytes() + b"tamper")
        results["OUTER_TAMPER"] = rejected(lambda: a.read_archive(target, key))
        # Rehash every locally mutated report and inner manifest. The external
        # ZIP trust anchor must still reject all eight producer-copy attempts.
        forged_count = 0
        for (worker, profile), (aid, _) in ((k, v) for k, v in a.ARTIFACTS.items() if len(k) == 2):
            original_raw = a.read_archive(root / (str(aid) + ".zip"), (worker, profile))
            copied = {}
            for attempt in (1, 2):
                report = copy.deepcopy(value)
                report.update(worker=worker, profile=profile, attempt=attempt)
                report["episodes"][0]["trace"][150]["state_sha256"] = "0"*64
                report["panel_sha256"] = a.digest(report["episodes"])
                copied["run-" + str(attempt) + ".json"] = a.canonical(report)
                forged_count += 1
            copied["install.json"] = original_raw["install.json"]
            copied["SHA256SUMS"] = "".join(a.sha(copied[k]) + "  " + k + "\n" for k in sorted(copied)).encode()
            with zipfile.ZipFile(target, "w") as z:
                for name, data in copied.items():
                    z.writestr(name, data)
            results["REHASHED_" + worker + "_" + profile] = rejected(lambda: a.read_archive(target, (worker, profile)))
    a.need(all(results.values()) and forged_count == 8, "admission attack survived")
    return {"experiment": a.EXPERIMENT, "scientific_promotion_authorized": False,
            "scientific_promotion": "BLOCKED", "scope": "IMMUTABLE_ARTIFACT_AND_STRUCTURAL_ATTACKS",
            "rejected_attacks": results, "jointly_rehashed_reports": forged_count,
            "digest_only_state_limitation": "STRUCTURALLY_VALID_FORGERY_REQUIRES_EXTERNAL_ANCHOR"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archives", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    raw = a.canonical(attack(args.archives))
    if args.verify:
        a.need(args.out.read_bytes() == raw, "attack report replay")
    else:
        with args.out.open("xb") as handle:
            handle.write(raw)
    print(raw.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
