"""Read-only retrospective attribution of the immutable EXP04D trace."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d

HERE = Path(__file__).resolve().parent
RUN = 45262910203
ARTIFACT = 14862245545
HEAD = "5a6920609579f87008affe8a2bf90b8b8e8e9ac2"
ARCHIVE_SHA = "2cdc9b23dc7521368dc54c63ea91009ae83c7ad05307ca082a54d46225bd5615"
NAMES = {"episodes.json.gz", "worlds.json", "verdict.json", "implementation.json", "preregistration.md"}
CLASSES = ("NO_SPIKES", "ALIAS", "ERASURE_BLOCKED", "OBSERVED_EXCLUSION")


def sha_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def classify(mode: int, other: int, counts: tuple[int, int], observed: set[int]) -> str:
    require(mode in observed and other != mode, "invalid pair attribution")
    truth = sum(a*b for a,b in zip(q.MODES[mode], counts, strict=True))
    alternative = sum(a*b for a,b in zip(q.MODES[other], counts, strict=True))
    if truth == alternative:
        require(other in observed, "equal arrival predictions separated")
        return "NO_SPIKES" if not any(counts) else "ALIAS"
    return "ERASURE_BLOCKED" if other in observed else "OBSERVED_EXCLUSION"


def longest(flags: list[bool]) -> int:
    best = streak = 0
    for flag in flags:
        streak = streak+1 if flag else 0
        best = max(best, streak)
    return best


def segment(rows: list[dict], arm: str, start: int, end: int, mode: int) -> dict:
    require(0 <= start < end <= d.STEPS, "segment boundary")
    actual = rows[start+1:end+1]
    actions = rows[start:end]
    require(all(row["transition_mode"] == mode for row in actual)
            and all(row["next_mode"] == mode for row in actions), "wrong mode boundary")
    band = [.4 <= math.fsum(float.fromhex(x) for x in row["true_gaba"])/16 <= .6 for row in actual]
    result = {"start": start, "end_exclusive": end, "mode": mode,
              "reachable": mode != 3, "ticks": end-start,
              "in_band_ticks": sum(band), "longest_in_band": longest(band),
              "tracking_ticks": sum(row["kind"] == "TRACK" for row in actions),
              "source_effort_pA_ticks": 2000*sum(row["group"] is not None for row in actions)}
    if arm not in d.ADAPTIVE:
        return result
    counts = Counter({key: 0 for key in CLASSES})
    pair_counts = {str(i): Counter({key: 0 for key in CLASSES}) for i in d.ALL if i != mode}
    observed_history, full_history = set(d.ALL), set(d.ALL)
    observed_single, full_single, correct = [], [], []
    renew_expansions = contradiction_expansions = retained_false_ticks = stale_ticks = 0
    group_stats = [{"active_probe_ticks": 0, "informative_opportunity_ticks": 0,
                    "tied_selected_ticks": 0, "untied_selected_ticks": 0,
                    "probe_spikes_next": 0, "probe_zero_spike_next": 0,
                    "other_ticks": 0, "other_spikes_next": 0, "other_zero_spike_next": 0}
                   for _ in range(2)]
    probe_sequences = [[], []]
    for previous, row in zip(actions, actual, strict=True):
        old = d.parse_obs(previous)
        now = d.parse_obs(row)
        require(now.tick == old.tick+1, "nonconsecutive observations")
        true_bits = tuple(previous["true_bits"])
        require(len(true_bits) == 8 and all(type(x) is int and x in (0, 1) for x in true_bits),
                "bad true bits")
        require(all(x is None or x == y for x,y in zip(old.bits,true_bits,strict=True)),
                "erasure changed a spike")
        residual = q.observed_residual(old.gaba, now.gaba)
        observed = set(q.support(d.ALL, old.bits, residual))
        full = set(q.support(d.ALL, true_bits, residual))
        source_counts = (sum(true_bits[:4]), sum(true_bits[4:]))
        predicted = [sum(a*b for a,b in zip(m,source_counts,strict=True)) for m in q.MODES]
        require(full == {i for i in d.ALL if predicted[i] == predicted[mode]}, "full-bit support disagrees")
        require(mode in full and full <= observed and observed == set(row["instant"]), "support invariant")
        for other in d.ALL:
            if other != mode:
                label = classify(mode,other,source_counts,observed)
                counts[label] += 1
                pair_counts[str(other)][label] += 1
        observed_history.intersection_update(observed)
        full_history.intersection_update(full)
        require(mode in full_history and full_history <= observed_history, "segment history lost truth")
        candidates = set(row["candidates"])
        prior_candidates = set(previous["candidates"])
        require(bool(candidates) and candidates <= set(d.ALL), "invalid epoch state")
        expanded = bool(candidates-prior_candidates)
        renew_expansions += expanded and row["event"] == d.RENEWAL
        contradiction_expansions += expanded and row["event"] == d.CONTRADICTION
        retained_false_ticks += bool((candidates-observed_history)-{mode})
        stale_ticks += mode not in candidates
        observed_single.append(observed_history == {mode})
        full_single.append(full_history == {mode})
        correct.append(candidates == {mode})
        decision = tuple(previous["candidates"])
        scores = [sum(q.MODES[i][g] != q.MODES[j][g]
                      for i,j in itertools.combinations(decision,2)) for g in range(2)]
        next_bits = tuple(row["true_bits"])
        require(len(next_bits) == 8 and all(type(x) is int and x in (0,1) for x in next_bits), "bad next bits")
        for group, stats in enumerate(group_stats):
            active = previous["kind"] == "ACTIVE_PROBE" and previous["group"] == group
            spikes = sum(next_bits[group*4:group*4+4])
            stats["informative_opportunity_ticks"] += len(decision)>1 and scores[group]>0
            probe_sequences[group].append(active)
            if active:
                require(len(decision)>1 and scores[group]>0, "non-discriminating active probe")
                stats["active_probe_ticks"] += 1
                stats["tied_selected_ticks"] += scores[0] == scores[1]
                stats["untied_selected_ticks"] += scores[0] != scores[1]
                stats["probe_spikes_next"] += spikes
                stats["probe_zero_spike_next"] += spikes == 0
            else:
                stats["other_ticks"] += 1
                stats["other_spikes_next"] += spikes
                stats["other_zero_spike_next"] += spikes == 0
    require(sum(counts.values()) == 3*(end-start), "pair partition incomplete")
    ticks = list(range(start+1,end+1))
    for group, stats in enumerate(group_stats):
        stats["longest_active_probe_streak"] = longest(probe_sequences[group])
        stats["opportunity_without_active_probe"] = bool(stats["informative_opportunity_ticks"] and not stats["active_probe_ticks"])
    result.update(pair_partition=dict(counts), pair_by_alternative={k: dict(v) for k,v in pair_counts.items()},
                  observed_segment_first_singleton=d.first_run(observed_single,ticks,1),
                  observed_segment_first_20=d.first_run(observed_single,ticks,20),
                  full_segment_first_singleton=d.first_run(full_single,ticks,1),
                  full_segment_first_20=d.first_run(full_single,ticks,20),
                  actual_first_20=d.first_run(correct,ticks,20),
                  correct_singleton_ticks=sum(correct),
                  correct_and_band_ticks=sum(c and b for c,b in zip(correct,band,strict=True)),
                  actual_first_recovery_10=d.first_run([c and b for c,b in zip(correct,band,strict=True)],ticks,10) if mode != 3 else None,
                  stale_ticks=stale_ticks, retained_false_ticks=retained_false_ticks,
                  scheduled_reexpansions=renew_expansions, contradiction_reexpansions=contradiction_expansions,
                  groups=group_stats)
    return result


def load_archive(path: Path) -> tuple[list, list, dict]:
    require(path.is_file() and not path.is_symlink() and sha_file(path)==ARCHIVE_SHA, "archive digest mismatch")
    with zipfile.ZipFile(path) as z:
        names = [i.filename for i in z.infolist() if not i.is_dir()]
        expected = NAMES | {"SHA256SUMS"}
        prefix = "cneh04d/"
        require(len(names)==len(set(names)) and set(names)=={prefix+x for x in expected}|{"cneh04d-install.json"}, "archive roster mismatch")
        hashes = {}
        for name in sorted(NAMES):
            with z.open(prefix+name) as stream:
                hashes[name] = hashlib.file_digest(stream,"sha256").hexdigest()
        manifest = "".join(f"{hashes[k]}  {k}\n" for k in sorted(hashes)).encode("ascii")
        require(z.read(prefix+"SHA256SUMS")==manifest, "inner manifest mismatch")
        implementation = json.loads(z.read(prefix+"implementation.json"))
        paths = {"runner_sha256": Path(d.__file__), "support_filter_sha256": Path(q.__file__),
                 "neural_runner_sha256": Path(d.neural.__file__),
                 "runtime_lock_sha256": HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"}
        require(all(implementation[k]==sha_file(p) for k,p in paths.items()), "frozen code drift")
        require(hashes["preregistration.md"]==sha_file(Path(d.__file__).parent/"PREREGISTRATION.md"), "parent protocol drift")
        with z.open(prefix+"episodes.json.gz") as compressed, gzip.GzipFile(fileobj=compressed) as raw:
            episodes = json.load(raw)
        return episodes, json.loads(z.read(prefix+"worlds.json")), json.loads(z.read(prefix+"verdict.json"))


def audit(episodes: list, worlds: list, verdict: dict) -> dict:
    require(verdict["all_instrument_checks_passed"] is True and verdict["valid_worlds"]==12, "parent instrument failed")
    require(len(worlds)==len(d.SEEDS) and {w["seed"] for w in worlds}==set(d.SEEDS), "world roster mismatch")
    require(len(episodes)==len(d.SEEDS)*len(d.ARMS) and {(e["seed"],e["arm"]) for e in episodes}==set(itertools.product(d.SEEDS,d.ARMS)), "episode roster mismatch")
    by_world = {w["seed"]: w for w in worlds}
    results = []
    for e in episodes:
        seed, arm, rows = e["seed"],e["arm"],e["trace"]
        w = d.world(seed)
        recorded = by_world[seed]
        require(e["valid"] is True and recorded["valid"] is True and recorded["exact_emulator_equal"] is True, "invalid evidence")
        require(recorded["schedule"] == [list(x) for x in w["schedule"]], "schedule mismatch")
        require(len(rows)==d.STEPS+1 and [x["tick"] for x in rows]==list(range(d.STEPS+1)), "trace roster mismatch")
        if arm!="ORACLE":
            d.audit_policy_tape(rows,arm)
        schedule = w["schedule"]
        segs = [segment(rows,arm,tau,schedule[i+1][0] if i+1<len(schedule) else d.STEPS,mode)
                for i,(tau,mode) in enumerate(schedule)]
        for actual, original in zip(segs,e["segments"],strict=True):
            require(actual["tracking_ticks"]==original["tracking_ticks"] and actual["source_effort_pA_ticks"]==original["source_current_l1_pA_ticks"], "parent segment metric mismatch")
            if arm in d.ADAPTIVE:
                require(actual["actual_first_20"]==(None if original["identification_latency"] is None else actual["start"]+original["identification_latency"]), "parent identification mismatch")
                require(actual["actual_first_recovery_10"]==(None if original["control_recovery_latency"] is None else actual["start"]+original["control_recovery_latency"]), "parent recovery mismatch")
        contradictions = sum(row["event"]==d.CONTRADICTION for row in rows)
        require(bool(schedule) or contradictions==0,"no-change contradiction")
        results.append({"seed":seed,"arm":arm,"segments":segs,"contradictions":contradictions})
    summary = {}
    for arm in d.ARMS:
        segs = [s for e in results if e["arm"]==arm for s in e["segments"]]
        reachable = [s for s in segs if s["reachable"]]
        entry = {"segments":len(segs),"reachable_segments":len(reachable),
                 "reachable_band_10_segments":sum(s["longest_in_band"]>=10 for s in reachable),
                 "disconnected_tracking_ticks":sum(s["tracking_ticks"] for s in segs if not s["reachable"])}
        if arm in d.ADAPTIVE:
            entry.update(pair_partition={k:sum(s["pair_partition"][k] for s in segs) for k in CLASSES},
                         observed_ceiling_20=sum(s["observed_segment_first_20"] is not None for s in segs),
                         full_spike_ceiling_20=sum(s["full_segment_first_20"] is not None for s in segs),
                         actual_identified_20=sum(s["actual_first_20"] is not None for s in segs),
                         actual_recovered_10=sum(s["actual_first_recovery_10"] is not None for s in reachable),
                         stale_ticks=sum(s["stale_ticks"] for s in segs),
                         retained_false_ticks=sum(s["retained_false_ticks"] for s in segs),
                         scheduled_reexpansions=sum(s["scheduled_reexpansions"] for s in segs),
                         contradiction_reexpansions=sum(s["contradiction_reexpansions"] for s in segs),
                         unprobed_informative_segments=[sum(s["groups"][g]["opportunity_without_active_probe"] for s in segs) for g in range(2)],
                         active_probe_ticks=[sum(s["groups"][g]["active_probe_ticks"] for s in segs) for g in range(2)])
            require(entry["actual_identified_20"]==verdict["arm_metrics"][arm]["identified_segments"] and entry["actual_recovered_10"]==verdict["arm_metrics"][arm]["recovered_reachable_segments"],"parent aggregate mismatch")
        summary[arm] = entry
    return {"experiment":"CNEH-EXP-04E","authority":"RETROSPECTIVE_TRACE_DIAGNOSTIC_ONLY",
            "source_run":RUN,"source_artifact":ARTIFACT,"source_head":HEAD,"archive_sha256":ARCHIVE_SHA,
            "protocol_sha256":sha_file(HERE/"PROTOCOL.md"),"implementation_sha256":sha_file(Path(__file__)),
            "episodes":len(results),"summary":summary,"per_episode":results,
            "scientific_promotion_authorized":False,"external_replication":"NOT_TESTED","physical_energy":"INSTRUMENT_INVALID"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    args = parser.parse_args()
    data = (json.dumps(audit(*load_archive(args.archive)),sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    if args.verify:
        require(args.out.is_file() and not args.out.is_symlink() and args.out.read_bytes()==data,"diagnostic replay mismatch")
    else:
        with args.out.open("xb") as stream:
            stream.write(data)
    print(json.dumps(json.loads(data)["summary"],sort_keys=True))


if __name__ == "__main__":
    main()
