from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import (
    OUT,
    SEEDS,
    EXPERIMENT_ID,
    cohort_gate,
    evaluate_cell,
    evaluate_rows,
    final_verdict,
    load_model,
    make_calibration_policy,
    sha256_file,
    train_model,
    validate_seed_contract,
    verify_data_hashes,
)


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def checkpoint_path(seed: int) -> Path:
    return OUT / "checkpoints" / f"seed{seed}.pt"


def ensure_model(seed: int) -> dict[str, Any]:
    p = checkpoint_path(seed)
    meta = p.with_suffix(".meta.json")
    if p.exists() and meta.exists():
        m = json.loads(meta.read_text())
        if m["sha256"] != sha256_file(p):
            raise RuntimeError(f"checkpoint drift seed={seed}")
        return m
    m = train_model(seed, p)
    dump(meta, m)
    return m


def calibration() -> dict[str, Any]:
    validate_seed_contract(); verify_data_hashes()
    seed = SEEDS["CALIBRATION"][0]
    meta = ensure_model(seed)
    model = load_model(checkpoint_path(seed))
    rows = {fam: evaluate_rows(model, fam, "CALIBRATION") for fam in ("PROSE", "CODE")}
    policy = make_calibration_policy(rows, meta)
    policy["calibration_rows"] = {
        fam: [{"case_id": r.case_id, "loss1": r.loss1, "loss2": r.loss2, "gain": r.gain} for r in rs]
        for fam, rs in rows.items()
    }
    dump(OUT / "CALIBRATION_POLICY.json", policy)
    print(f"{EXPERIMENT_ID} CALIBRATION frozen: {OUT / 'CALIBRATION_POLICY.json'}")
    for fam in ("PROSE", "CODE"):
        f = policy["frontier"][fam]
        print(f"  {fam}: L1={f['loss1']:.6f} L2={f['loss2']:.6f} slope={f['gain_per_flop']:.3e}")
    return policy


def scientific_run() -> dict[str, Any]:
    validate_seed_contract(); verify_data_hashes()
    policy_path = OUT / "CALIBRATION_POLICY.json"
    if not policy_path.is_file():
        raise RuntimeError("CALIBRATION_POLICY.json must be frozen before scientific run")
    policy = json.loads(policy_path.read_text())
    all_cells: dict[str, list[dict[str, Any]]] = {"PRIMARY": [], "REPLICATION": []}
    checkpoint_meta: dict[str, Any] = {}
    for cohort in ("PRIMARY", "REPLICATION"):
        for seed in SEEDS[cohort]:
            meta = ensure_model(seed); checkpoint_meta[str(seed)] = meta
            model = load_model(checkpoint_path(seed))
            for fam in ("PROSE", "CODE"):
                cell = evaluate_cell(evaluate_rows(model, fam, cohort), policy)
                cell["seed"] = seed
                all_cells[cohort].append(cell)
                dump(OUT / "raw" / f"{cohort.lower()}_{fam.lower()}_seed{seed}.json", cell)
                adv = cell["candidate_advantage_vs_fixed_frontier"]
                print(f"[{cohort} {fam} s{seed}] pass={cell['passed']} q={cell['continue_rate']:.3f} "
                      f"adv={adv if adv is not None else 'OUTSIDE'}")
    p = cohort_gate(all_cells["PRIMARY"], "PRIMARY")
    r = cohort_gate(all_cells["REPLICATION"], "REPLICATION")
    verdict = final_verdict(p, r)
    result = {
        "experiment": EXPERIMENT_ID,
        "verdict": verdict,
        "tier": "REAL-DATA / SMALL-MODEL / INTERNAL-CORPUS MECHANISM GATE",
        "primary": p,
        "replication": r,
        "cells": all_cells,
        "checkpoints": checkpoint_meta,
        "calibration_policy_sha256": sha256_file(policy_path),
        "data_sha256": verify_data_hashes(),
        "non_promotion_boundary": {
            "external_transfer": False,
            "mod_moe_superiority": False,
            "large_model_scaling": False,
            "architecture_l7": False,
            "independent_replication": False,
        },
    }
    dump(OUT / "verdict.json", result)
    print(f"{EXPERIMENT_ID} VERDICT: {verdict}")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("calibrate", "run"))
    args = ap.parse_args()
    calibration() if args.mode == "calibrate" else scientific_run()


if __name__ == "__main__":
    main()
