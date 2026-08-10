#!/usr/bin/env python3
"""Bind ACT-R&D-01 pass-1 execution results to their declared scientific boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_sha_dir(path: Path) -> None:
    sums = path / "SHA256SUMS"
    if not sums.is_file():
        raise ValueError(f"missing checksum ledger: {sums}")
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        target = path / name
        if not target.is_file():
            raise ValueError(f"checksum target missing: {target}")
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f"checksum mismatch: {target}")


def validate(root: Path) -> None:
    s01a_dir = root / "artifacts/research-s01-skill-luck"
    s01b_dir = root / "artifacts/research-s01-ood-credit"
    s03_dir = root / "artifacts/research-s03-latent-dynamics"
    for d in (s01a_dir, s01b_dir, s03_dir):
        _verify_sha_dir(d)

    s01a = _json(s01a_dir / "verdict.json")
    s01b = _json(s01b_dir / "verdict.json")
    s03 = _json(s03_dir / "verdict.json")
    if s01a.get("verdict") != "S01_SKILLLUCK_CONCEPT_REPRODUCED":
        raise ValueError("S01 conceptual verdict drift")
    if s01a.get("architecture_promotion_authority") is not False:
        raise ValueError("S01 conceptual result illegally authorizes architecture")
    if s01b.get("verdict") != "S01_OOD_CAUSAL_CREDIT_QUALIFIED":
        raise ValueError("S01 OOD qualifier verdict drift")
    if not all(s01b.get("primary_predicates", {}).values()):
        raise ValueError("S01 OOD qualifier has failed primary predicate")
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
    if not r01 or "MATCHED_BUDGET_ESTIMATOR_PENDING" not in r01.get("status", ""):
        raise ValueError("S01 queue boundary drift")
    if not r03 or "FAILED_PREREGISTERED_H8_ROBUSTNESS_GATE" not in r03.get("status", ""):
        raise ValueError("S03 queue failure boundary drift")


def main() -> int:
    try:
        validate(ROOT)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"RESEARCH-EXECUTION-GATE: FAIL — {exc}")
        return 1
    print("RESEARCH-EXECUTION-GATE: PASS — S01 narrow positives and S03 preregistered negative are checksum-bound; no promotion")
    return 0


if __name__ == "__main__":
    sys.exit(main())
