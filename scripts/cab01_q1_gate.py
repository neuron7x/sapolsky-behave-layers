from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/cab-01-q1"
RES = ROOT / "research/results/CAB-01-Q1/verdict.json"
EXPECTED_COUNTS = {**{f"F{i}": 128 for i in range(11)}, "F11": 384}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(v: dict[str, object]) -> list[str]:
    e: list[str] = []
    if v.get("verdict") != "CAB01_Q1_BENCHMARK_QUALIFIED_SYNTHETIC": e.append("verdict")
    if v.get("benchmark_qualified") is not True: e.append("benchmark_qualified")
    if v.get("authority") != "SYNTHETIC_BENCHMARK_QUALIFICATION_ONLY": e.append("authority")
    if v.get("parent_design_commit") != "a849b63": e.append("parent design")
    if v.get("preconfirmatory_execution_preregistration_commit") != "f55fde0f7eee54f88f6f0443d3de48dbbb582afe": e.append("prereg commit")
    if v.get("errors") != []: e.append("errors")
    if v.get("novelty_status") != "UNKNOWN_OVERLAP_CONCEDED": e.append("novelty overclaim")
    for key, value in dict(v.get("non_promotion_boundary", {})).items():
        if value is not False: e.append(f"unsafe promotion {key}")
    for cohort, base in {"PRIMARY": 310811, "REPLICATION": 410811}.items():
        c = dict(dict(v.get("cohorts", {})).get(cohort, {}))
        if c.get("seed_base") != base: e.append(f"{cohort} seed")
        if c.get("case_count") != 1792: e.append(f"{cohort} count")
        if c.get("family_counts") != EXPECTED_COUNTS: e.append(f"{cohort} family counts")
        if c.get("label_path_disagreements") != 0: e.append(f"{cohort} oracle disagreement")
        if c.get("f11_triads_pass") is not True: e.append(f"{cohort} F11")
        if c.get("surface_leakage_pass") is not True: e.append(f"{cohort} leakage")
        if float(c.get("surface_only_accuracy", 2.0)) > float(c.get("majority_class_rate", -1.0)) + 1e-12: e.append(f"{cohort} leakage envelope")
        dom = dict(c.get("pareto_dominators", {}))
        if not dom.get("always_act"): e.append(f"{cohort} always_act Pareto")
        if not dom.get("always_abstain"): e.append(f"{cohort} always_abstain Pareto")
    for pair in dict(v.get("regeneration_hashes", {})).values():
        pair = dict(pair)
        if pair.get("generation") != pair.get("replay"): e.append("deterministic regeneration")
    return e


def main() -> int:
    errors: list[str] = []
    required = [ART / "instances.jsonl", ART / "baseline_metrics.json", ART / "verdict.json", ART / "SHA256SUMS", RES]
    for p in required:
        if not p.is_file(): errors.append(f"missing {p.relative_to(ROOT)}")
    if errors:
        print("CAB01-Q1-GATE FAIL", *errors, sep="\n - ")
        return 1
    for line in (ART / "SHA256SUMS").read_text().splitlines():
        want, name = line.split("  ", 1)
        path = ART / name
        if not path.is_file() or sha256(path) != want: errors.append(f"checksum {name}")
    if sha256(ART / "verdict.json") != sha256(RES): errors.append("verdict mirror mismatch")
    v = json.loads(RES.read_text())
    errors.extend(validate(v))

    if "--self-test" in sys.argv:
        mutations = []
        m = copy.deepcopy(v); m["benchmark_qualified"] = False; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY"]["label_path_disagreements"] = 1; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY"]["surface_leakage_pass"] = False; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["REPLICATION"]["f11_triads_pass"] = False; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY"]["pareto_dominators"]["always_act"] = []; mutations.append(m)
        m = copy.deepcopy(v); m["non_promotion_boundary"]["cwc_superiority"] = True; mutations.append(m)
        m = copy.deepcopy(v); m["novelty_status"] = "NOVEL"; mutations.append(m)
        killed = sum(bool(validate(x)) for x in mutations)
        if killed != len(mutations): errors.append(f"self-test killed {killed}/{len(mutations)}")
        else: print(f"CAB01-Q1-GATE SELF-TEST: {killed}/{len(mutations)} semantic/authority mutations killed")

    if errors:
        print("CAB01-Q1-GATE FAIL", *errors, sep="\n - ")
        return 1
    print("CAB01-Q1-GATE PASS: benchmark generator qualified synthetically; no CWC superiority or real-model promotion licensed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
