from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/cab-01-q1-r1"
RES = ROOT / "research/results/CAB-01-Q1-R1/verdict.json"
EXPECTED_COUNTS = {**{f"F{i}": 128 for i in range(11)}, "F11": 384}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(v: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if v.get("verdict") != "CAB01_Q1_R1_BENCHMARK_QUALIFIED_SYNTHETIC": errors.append("verdict")
    if v.get("benchmark_qualified") is not True: errors.append("benchmark_qualified")
    if v.get("authority") != "SYNTHETIC_BENCHMARK_QUALIFICATION_ONLY": errors.append("authority")
    if v.get("parent_q1_evidence_commit") != "2d3bec65972a213dcdb0f24ef53a4edf4b3f0ec2": errors.append("parent Q1")
    if v.get("preconfirmatory_r1_preregistration_commit") != "fdd89e4c6ef578647e8522035a6bbbb62185c33f": errors.append("R1 prereg")
    if v.get("generator_implementation_commit") != "a8ed935f1140eb5dba2e971dcf20229831fd1e12": errors.append("generator commit")
    if v.get("errors") != []: errors.append("errors")
    if v.get("novelty_status") != "UNKNOWN_OVERLAP_CONCEDED": errors.append("novelty")
    for key, value in dict(v.get("non_promotion_boundary", {})).items():
        if value is not False: errors.append(f"unsafe promotion {key}")
    for cohort, seed in {"PRIMARY_R1": 510811, "REPLICATION_R1": 610811}.items():
        c = dict(dict(v.get("cohorts", {})).get(cohort, {}))
        if c.get("seed_base") != seed: errors.append(f"{cohort} seed")
        if c.get("case_count") != 1792: errors.append(f"{cohort} count")
        if c.get("family_counts") != EXPECTED_COUNTS: errors.append(f"{cohort} counts")
        if c.get("label_path_disagreements") != 0: errors.append(f"{cohort} oracle")
        if c.get("f11_triads_pass") is not True: errors.append(f"{cohort} F11")
        if c.get("unique_surface_signatures") != 1: errors.append(f"{cohort} structural leakage")
        if c.get("structural_surface_null_pass") is not True: errors.append(f"{cohort} structural null")
        if c.get("heldout_predictive_null_pass") is not True: errors.append(f"{cohort} predictive null")
        if c.get("surface_leakage_pass") is not True: errors.append(f"{cohort} leakage")
        if float(c.get("surface_only_accuracy", 2.0)) > float(c.get("heldout_majority_class_rate", -1.0)) + 1e-12:
            errors.append(f"{cohort} heldout null envelope")
        dom = dict(c.get("pareto_dominators", {}))
        if not dom.get("always_act"): errors.append(f"{cohort} always_act Pareto")
        if not dom.get("always_abstain"): errors.append(f"{cohort} always_abstain Pareto")
    for pair in dict(v.get("regeneration_hashes", {})).values():
        pair = dict(pair)
        if pair.get("generation") != pair.get("replay"): errors.append("deterministic replay")
    return errors


def main() -> int:
    errors: list[str] = []
    for p in [ART / "instances.jsonl", ART / "baseline_metrics.json", ART / "verdict.json", ART / "SHA256SUMS", RES]:
        if not p.is_file(): errors.append(f"missing {p.relative_to(ROOT)}")
    if errors:
        print("CAB01-Q1-R1-GATE FAIL", *errors, sep="\n - ")
        return 1
    for line in (ART / "SHA256SUMS").read_text().splitlines():
        want, name = line.split("  ", 1)
        p = ART / name
        if not p.is_file() or sha256(p) != want: errors.append(f"checksum {name}")
    if sha256(ART / "verdict.json") != sha256(RES): errors.append("verdict mirror")
    v = json.loads(RES.read_text())
    errors.extend(validate(v))

    if "--self-test" in sys.argv:
        mutations = []
        m = copy.deepcopy(v); m["benchmark_qualified"] = False; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY_R1"]["unique_surface_signatures"] = 2; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY_R1"]["surface_only_accuracy"] = 0.9; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["REPLICATION_R1"]["label_path_disagreements"] = 1; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["REPLICATION_R1"]["f11_triads_pass"] = False; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY_R1"]["pareto_dominators"]["always_abstain"] = []; mutations.append(m)
        m = copy.deepcopy(v); m["non_promotion_boundary"]["cwc_superiority"] = True; mutations.append(m)
        m = copy.deepcopy(v); m["novelty_status"] = "NOVEL"; mutations.append(m)
        killed = sum(bool(validate(m)) for m in mutations)
        if killed != len(mutations): errors.append(f"self-test killed {killed}/{len(mutations)}")
        else: print(f"CAB01-Q1-R1-GATE SELF-TEST: {killed}/{len(mutations)} mutations killed")

    if errors:
        print("CAB01-Q1-R1-GATE FAIL", *errors, sep="\n - ")
        return 1
    print("CAB01-Q1-R1-GATE PASS: synthetic benchmark qualification bound; flagship/model promotion remains forbidden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
