from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from experiments.cwc_flagship_route_02 import core as r2
from experiments.dgc_03_local_model import core


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    r2.validate_seed_contract()
    data_sha = r2.verify_data_hashes()
    anti = r2.assert_no_r1_overlap()
    cells: dict[str, list[dict[str, Any]]] = {"PRIMARY": [], "REPLICATION": []}
    calibrations: list[dict[str, Any]] = []
    checkpoint_records: list[dict[str, Any]] = []

    for cohort in ("PRIMARY", "REPLICATION"):
        for seed in r2.SEEDS[cohort]:
            cp = r2.OUT / "checkpoints" / f"seed{seed}.pt"
            meta_path = cp.with_suffix(".meta.json")
            policy_path = r2.OUT / "policies" / f"seed{seed}.json"
            if not cp.is_file() or not meta_path.is_file() or not policy_path.is_file():
                raise RuntimeError(f"frozen R2 assets missing seed={seed}")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sha256") != _sha256(cp) or int(meta.get("seed", -1)) != seed:
                raise RuntimeError(f"checkpoint integrity mismatch seed={seed}")
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            if int(policy.get("seed", -1)) != seed or policy.get("experiment") != r2.EXPERIMENT_ID:
                raise RuntimeError(f"R2 policy identity mismatch seed={seed}")
            model = r2.load_model(cp, expected_seed=seed)
            cal_rows = {fam: r2.evaluate_rows(model, fam, "CALIBRATION") for fam in ("PROSE", "CODE")}
            calibration = core.make_calibration(seed, cal_rows)
            calibrations.append(asdict(calibration))
            checkpoint_records.append({
                "cohort": cohort,
                "seed": seed,
                "checkpoint": str(cp.relative_to(core.ROOT)),
                "checkpoint_sha256": _sha256(cp),
                "policy_sha256": _sha256(policy_path),
            })
            for family in ("PROSE", "CODE"):
                rows = r2.evaluate_rows(model, family, cohort)
                cells[cohort].append(core.evaluate_cell(rows=rows, calibration=calibration, r2_policy=policy))

    primary = core.cohort_summary(cells["PRIMARY"], "PRIMARY")
    replication = core.cohort_summary(cells["REPLICATION"], "REPLICATION")
    verdict = core.final_verdict(primary, replication)
    out = {
        "experiment": core.EXPERIMENT_ID,
        "status": "REAL_DATA_SMALL_LOCAL_MODEL_FINITE_WORKLOAD",
        "preregistration_sha256": _sha256(core.ROOT / "experiments/dgc_03_local_model/PREREGISTRATION.md"),
        "data_sha256": data_sha,
        "anti_reuse": anti,
        "checkpoint_records": checkpoint_records,
        "calibrations": calibrations,
        "primary": primary,
        "replication": replication,
        "verdict": verdict,
        "authority": {
            "openai_anthropic_client_claim": False,
            "external_2026_router_superiority": False,
            "commercial_claim_allowed": False,
            "old_r2_programme_rescued": False,
        },
    }
    core.OUT.mkdir(parents=True, exist_ok=True)
    _write(core.OUT / "verdict.json", out)
    _write(core.OUT / "cells.json", cells)
    print(json.dumps({"verdict": verdict, "primary": primary, "replication": replication}, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    run()
