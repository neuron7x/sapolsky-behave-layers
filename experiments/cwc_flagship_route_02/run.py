from __future__ import annotations

import argparse, json
from pathlib import Path
from typing import Any

from . import core


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def checkpoint_path(seed: int) -> Path:
    return core.OUT / "checkpoints" / f"seed{seed}.pt"


def policy_path(seed: int) -> Path:
    return core.OUT / "policies" / f"seed{seed}.json"


def ensure_model(seed: int) -> dict[str, Any]:
    p, meta = checkpoint_path(seed), checkpoint_path(seed).with_suffix(".meta.json")
    if p.exists() and meta.exists():
        m = json.loads(meta.read_text())
        if m["sha256"] != core.sha256_file(p) or int(m["seed"]) != seed:
            raise RuntimeError(f"checkpoint drift seed={seed}")
        return m
    m = core.train_model(seed, p); dump(meta, m); return m


def calibrate() -> dict[str, Any]:
    core.validate_seed_contract(); core.verify_data_hashes(); anti = core.assert_no_r1_overlap()
    records = []
    for cohort in ("PRIMARY", "REPLICATION"):
        for seed in core.SEEDS[cohort]:
            meta = ensure_model(seed)
            model = core.load_model(checkpoint_path(seed), expected_seed=seed)
            rows = {fam: core.evaluate_rows(model, fam, "CALIBRATION") for fam in ("PROSE", "CODE")}
            pol = core.make_seed_policy(seed, rows, meta)
            pol["calibration_rows"] = {
                fam: [{"case_id": r.case_id, "loss1": r.loss1, "loss2": r.loss2, "gain": r.gain} for r in rs]
                for fam, rs in rows.items()
            }
            dump(policy_path(seed), pol)
            records.append({"cohort": cohort, "seed": seed, "checkpoint_sha256": meta["sha256"],
                            "policy_sha256": core.sha256_file(policy_path(seed))})
            print(f"[CAL {cohort} s{seed}] prose_slope={pol['frontier']['PROSE']['gain_per_flop']:.3e} "
                  f"code_slope={pol['frontier']['CODE']['gain_per_flop']:.3e}")
    lock = {"experiment": core.EXPERIMENT_ID, "status": "CALIBRATION_COMPLETE_NO_SCIENTIFIC_EVAL",
            "anti_reuse": anti, "records": records, "data_sha256": core.verify_data_hashes()}
    dump(core.OUT / "CALIBRATION_LOCK.json", lock)
    return lock


def scientific_run() -> dict[str, Any]:
    core.validate_seed_contract(); core.verify_data_hashes(); anti = core.assert_no_r1_overlap()
    lockp = core.OUT / "CALIBRATION_LOCK.json"
    if not lockp.is_file(): raise RuntimeError("CALIBRATION_LOCK.json missing")
    all_cells = {"PRIMARY": [], "REPLICATION": []}
    for cohort in ("PRIMARY", "REPLICATION"):
        for seed in core.SEEDS[cohort]:
            cp, pp = checkpoint_path(seed), policy_path(seed)
            if not cp.is_file() or not pp.is_file(): raise RuntimeError(f"frozen calibration missing seed={seed}")
            policy = json.loads(pp.read_text())
            model = core.load_model(cp, expected_seed=seed)
            for fam in ("PROSE", "CODE"):
                cell = core.evaluate_cell(core.evaluate_rows(model, fam, cohort), policy, expected_seed=seed)
                all_cells[cohort].append(cell)
                dump(core.OUT / "raw" / f"{cohort.lower()}_{fam.lower()}_seed{seed}.json", cell)
                print(f"[{cohort} {fam} s{seed}] pass={cell['passed']} q={cell['continue_rate']:.3f} "
                      f"adv={cell['candidate_advantage_vs_fixed_frontier']}")
    p, r = core.cohort_gate(all_cells["PRIMARY"], "PRIMARY"), core.cohort_gate(all_cells["REPLICATION"], "REPLICATION")
    verdict = core.final_verdict(p, r)
    out = {"experiment": core.EXPERIMENT_ID, "verdict": verdict,
           "tier": "REAL-DATA / SMALL-MODEL / FINAL TWO-EXIT MECHANISM RESCUE",
           "primary": p, "replication": r, "cells": all_cells, "anti_reuse": anti,
           "data_sha256": core.verify_data_hashes(),
           "programme_rule": "R2 failure closes current two-exit learned adaptive-depth subprogramme; no R3 rescue."}
    dump(core.OUT / "verdict.json", out)
    print(f"{core.EXPERIMENT_ID} VERDICT: {verdict}")
    return out


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("mode", choices=("calibrate","run")); a=ap.parse_args()
    calibrate() if a.mode=="calibrate" else scientific_run()
if __name__ == "__main__": main()
