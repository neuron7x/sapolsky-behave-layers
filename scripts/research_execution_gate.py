#!/usr/bin/env python3
"""Bind ACT-R&D-01 pass-1 execution results to their declared scientific boundaries."""
from __future__ import annotations

import csv
import hashlib
import io
from itertools import product
import json
import math
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_sha_dir(path: Path, expected: set[str]) -> dict[str, bytes]:
    sums = path / "SHA256SUMS"
    if not sums.is_file() or sums.is_symlink():
        raise ValueError(f"missing regular checksum ledger: {sums}")
    verified = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if not separator or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError(f"malformed checksum ledger: {sums}")
        if name not in expected or name in verified:
            raise ValueError(f"unexpected or duplicate checksum target: {name}")
        target = path / name
        if not target.is_file() or target.is_symlink():
            raise ValueError(f"checksum target missing or irregular: {target}")
        raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"checksum mismatch: {target}")
        verified[name] = raw
    if set(verified) != expected:
        raise ValueError(f"incomplete checksum ledger: {sums}")
    return verified


S01_CONTEXTS = {"TRAIN_CONFOUNDED": 2.0, "OOD_WEAK_CONFOUNDER": 0.2, "OOD_SIGN_FLIP": -1.5}
S01_METHODS = ("EXACT_CF_SHAPLEY", "OBS_ASSOC", "RECENCY", "EQUAL")
S01_PREDICATES = {
    "ood_shapley_unique_A_all", "ood_shapley_false_mass_le_1e12", "max_efficiency_error_le_1e12",
}
S01_COLUMNS = ("seed", "context", "gamma", "method", "top1_A", "false_credit_mass",
               "score_A", "score_C", "score_D", "score_B", "max_efficiency_error",
               "counterfactual_structural_evaluations")
S01_TOLERANCE = 1e-12


def _verify_s01_predicates(verdict: dict, raw: bytes) -> None:
    predicates = verdict.get("primary_predicates")
    if type(predicates) is not dict or set(predicates) != S01_PREDICATES:
        raise ValueError("S01 OOD primary predicate roster mismatch")
    if any(value is not True for value in predicates.values()):
        raise ValueError("S01 OOD qualifier has failed or non-boolean primary predicate")
    expected = set(product(range(1000, 1128), S01_CONTEXTS, S01_METHODS))
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != S01_COLUMNS:
        raise ValueError("S01 OOD seed CSV header mismatch")
    seen = set()
    efficiency_by_seed: dict[tuple[int, str], float] = {}
    for row in reader:
        location = f"{row.get('seed')}/{row.get('context')}/{row.get('method')}"
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"S01 OOD malformed row at {location}")
        try:
            key = (int(row["seed"]), row["context"], row["method"])
            gamma = float(row["gamma"])
            scores = tuple(float(row[field]) for field in ("score_A", "score_C", "score_D", "score_B"))
            false_mass = float(row["false_credit_mass"])
            efficiency = float(row["max_efficiency_error"])
        except ValueError as exc:
            raise ValueError(f"S01 OOD malformed number at {location}") from exc
        seed, context, method = key
        if key not in expected or key in seen or gamma != S01_CONTEXTS[context]:
            raise ValueError(f"S01 OOD unexpected or duplicate seed row at {location}")
        seen.add(key)
        if not all(math.isfinite(value) and value >= 0 for value in (*scores, false_mass, efficiency)):
            raise ValueError(f"S01 OOD invalid metric at {location}")
        # Compute the two reported outcomes from the scores before checking limits.
        top1 = scores[0] > max(scores[1:]) + S01_TOLERANCE
        total = sum(scores)
        if not math.isfinite(total):
            raise ValueError(f"S01 OOD score total overflow at {location}")
        computed_mass = sum(scores[1:]) / total if total > 1e-15 else 0.0
        # The historical writer can sum scores in a different order. This
        # comparison tolerance does not replace the preregistered cutoff.
        if row["top1_A"] != str(int(top1)) or not math.isclose(
            false_mass, computed_mass, rel_tol=0.0, abs_tol=1e-15
        ):
            raise ValueError(f"S01 OOD score projection mismatch at {location}")
        if context.startswith("OOD_") and method == "EXACT_CF_SHAPLEY":
            if not top1 or computed_mass > S01_TOLERANCE:
                raise ValueError(f"S01 OOD primary predicate contradicted at {location}")
        if efficiency > S01_TOLERANCE or efficiency != efficiency_by_seed.setdefault((seed, context), efficiency):
            raise ValueError(f"S01 OOD efficiency predicate contradicted at {location}")
    if seen != expected:
        missing = min(expected - seen)
        raise ValueError(f"S01 OOD seed roster incomplete at {missing[0]}/{missing[1]}/{missing[2]}")
    stored_max = verdict.get("max_shapley_efficiency_error")
    if type(stored_max) not in (int, float) or stored_max != max(efficiency_by_seed.values()):
        raise ValueError("S01 OOD efficiency summary differs from checked seed rows")


def validate(root: Path) -> None:
    s01a_dir = root / "artifacts/research-s01-skill-luck"
    s01b_dir = root / "artifacts/research-s01-ood-credit"
    s03_dir = root / "artifacts/research-s03-latent-dynamics"
    s01a_files = _verify_sha_dir(s01a_dir, {"verdict.json"})
    s01b_files = _verify_sha_dir(s01b_dir, {"verdict.json", "seed_results.csv"})
    s03_files = _verify_sha_dir(s03_dir, {"verdict.json", "seed_results.csv"})
    s01a, s01b, s03 = (json.loads(files["verdict.json"])
                       for files in (s01a_files, s01b_files, s03_files))
    if s01a.get("verdict") != "S01_SKILLLUCK_CONCEPT_REPRODUCED":
        raise ValueError("S01 conceptual verdict drift")
    if s01a.get("architecture_promotion_authority") is not False:
        raise ValueError("S01 conceptual result illegally authorizes architecture")
    if s01b.get("verdict") != "S01_OOD_CAUSAL_CREDIT_QUALIFIED":
        raise ValueError("S01 OOD qualifier verdict drift")
    _verify_s01_predicates(s01b, s01b_files["seed_results.csv"])
    if s01b.get("architecture_promotion_authority") is not False or s01b.get("paper_reproduction_authority") is not False:
        raise ValueError("S01 OOD qualifier illegally escalated authority")
    if s03.get("verdict") != "S03_CONTROLLED_LATENT_DYNAMICS_NOT_QUALIFIED":
        raise ValueError("S03 negative verdict was erased or changed")
    predicates = s03.get("primary_predicates", {})
    if predicates.get("ood_h8_dynamic_wins_ge_56_of_64") is not False:
        raise ValueError("S03 frozen failed h8 predicate not preserved")
    if s03.get("architecture_promotion_authority") is not False or s03.get("neuroscience_authority") is not False or s03.get("paper_reproduction_authority") is not False:
        raise ValueError("S03 controlled result illegally escalated authority")

    ruins = _json(root / "research/09_KILLED_HYPOTHESES.yaml")
    if not any(r.get("ruin_id") == "RUIN-S03-CONTROLLED-LONG-HORIZON-ROBUSTNESS" and r.get("status") == "KILLED_AS_PREREGISTERED" for r in ruins):
        raise ValueError("S03 negative result missing from failure memory")

    queue = _json(root / "research/08_REPRODUCTION_QUEUE.yaml")
    r01 = next((x for x in queue if x.get("item_id") == "R01"), None)
    r03 = next((x for x in queue if x.get("item_id") == "R03"), None)
    # R01 is an advancing reproduction queue item, not a frozen verdict.  The
    # historical gate must preserve the original S01 authority boundary while
    # allowing later independently sealed estimator/shadow qualifications to
    # advance the queue.  Do not require a stale *_PENDING token forever.
    r01_status = r01.get("status", "") if r01 else ""
    if not r01 or not any(token in r01_status for token in (
        "MATCHED_BUDGET_ESTIMATOR_PENDING",
        "MATCHED_BUDGET_ESTIMATOR_QUALIFIED_CONTROLLED",
    )):
        raise ValueError("S01 queue estimator boundary drift")
    if "PRIMARY_SOURCE_BYTES_QUARANTINED" not in r01_status:
        raise ValueError("S01 primary-source quarantine boundary drift")
    if "PAPER_REPRODUCTION_PENDING" not in r01_status:
        raise ValueError("S01 paper-reproduction boundary drift")
    if not r03 or "FAILED_PREREGISTERED_H8_ROBUSTNESS_GATE" not in r03.get("status", ""):
        raise ValueError("S03 queue failure boundary drift")


def main() -> int:
    try:
        validate(ROOT)
    except (ValueError, OSError, csv.Error) as exc:
        print(f"RESEARCH-EXECUTION-GATE: FAIL — {exc}")
        return 1
    print("RESEARCH-EXECUTION-GATE: PASS — S01 narrow positives and S03 preregistered negative are checksum-bound; no promotion")
    return 0


if __name__ == "__main__":
    sys.exit(main())
