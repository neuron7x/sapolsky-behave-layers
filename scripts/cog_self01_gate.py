from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/cog-self-01"
RES = ROOT / "research/results/COG-SELF-01/verdict.json"
FAMILIES = tuple(f"S{i}" for i in range(12))
N = 128
PREREG = "ee99a9e732e3b4fc408f80a9a3ce71d3178717d6"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(v: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if v.get("experiment_id") != "COG-SELF-01": errors.append("experiment id")
    if v.get("verdict") != "AUTONOMOUS_DECISION_RELEVANT_FALSIFICATION_GOVERNOR_QUALIFIED_SYNTHETIC_NARROWED": errors.append("verdict")
    if v.get("scientific_pass") is not True: errors.append("scientific_pass")
    if v.get("authority") != "SYNTHETIC_SELF_FALSIFICATION_SAFETY_SELECTION_PRIMITIVE_ONLY": errors.append("authority")
    if v.get("preconfirmatory_preregistration_commit") != PREREG: errors.append("prereg binding")
    if v.get("n_per_family_per_cohort") != N: errors.append("n")
    if v.get("cohort_seed_bases") != {"PRIMARY": 710811, "REPLICATION": 810811}: errors.append("seed bases")
    if v.get("errors") != []: errors.append("errors")
    if v.get("novelty_status") != "UNKNOWN_OVERLAP_CONCEDED": errors.append("novelty")
    policy = dict(v.get("runtime_policy", {}))
    if policy.get("survival_can_promote_authority") is not False: errors.append("survival promotion")
    if policy.get("negative_outcome_can_only_retract_or_invalidate_bound_target") is not True: errors.append("negative target boundary")
    if policy.get("frozen_evidence_rewrite_api_exposed") is not False: errors.append("evidence rewrite")
    if policy.get("decision_relevant_spend_only") is not True: errors.append("decision relevance")
    for key, value in dict(v.get("non_promotion_boundary", {})).items():
        if value is not False: errors.append(f"unsafe promotion {key}")
    cohorts = dict(v.get("cohorts", {}))
    for cohort in ("PRIMARY", "REPLICATION"):
        c = dict(cohorts.get(cohort, {}))
        if c.get("n") != 12 * N: errors.append(f"{cohort} n")
        fams = dict(c.get("families", {}))
        for family in FAMILIES:
            f = dict(fams.get(family, {}))
            if f.get("n") != N or f.get("pass_count") != N or f.get("runtime_errors") != 0:
                errors.append(f"{cohort}:{family}")
        for field in (
            "false_spend_count", "irrelevant_attack_selection_count",
            "uncertified_attack_selection_count", "stale_plan_acceptance_count",
            "permutation_disagreement_count", "survival_promotion_count",
            "negative_target_violation_count", "stale_or_unbound_outcome_acceptance_count",
            "runtime_error_count",
        ):
            if c.get(field) != 0: errors.append(f"{cohort}:{field}")
        if c.get("negative_propagation_pass_count") != c.get("negative_propagation_evaluated_count"):
            errors.append(f"{cohort}:negative propagation")
    regen = dict(v.get("regeneration_hashes", {}))
    if regen.get("generation") != regen.get("replay"): errors.append("deterministic replay")
    return errors


def main() -> int:
    errors: list[str] = []
    required = [ART / "results.jsonl", ART / "verdict.json", ART / "SHA256SUMS", RES]
    for p in required:
        if not p.is_file(): errors.append(f"missing {p.relative_to(ROOT)}")
    if errors:
        print("COG-SELF-01-GATE FAIL", *errors, sep="\n - ")
        return 1
    for line in (ART / "SHA256SUMS").read_text().splitlines():
        want, name = line.split("  ", 1)
        p = ART / name
        if not p.is_file() or _sha(p) != want: errors.append(f"checksum {name}")
    if _sha(ART / "verdict.json") != _sha(RES): errors.append("verdict mirror")
    v = json.loads(RES.read_text())
    errors.extend(_validate(v))

    if "--self-test" in sys.argv:
        mutations = []
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY"]["false_spend_count"] = 1; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY"]["stale_plan_acceptance_count"] = 1; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["REPLICATION"]["irrelevant_attack_selection_count"] = 1; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["REPLICATION"]["uncertified_attack_selection_count"] = 1; mutations.append(m)
        m = copy.deepcopy(v); m["runtime_policy"]["survival_can_promote_authority"] = True; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY"]["negative_target_violation_count"] = 1; mutations.append(m)
        m = copy.deepcopy(v); m["cohorts"]["PRIMARY"]["stale_or_unbound_outcome_acceptance_count"] = 1; mutations.append(m)
        m = copy.deepcopy(v); m["non_promotion_boundary"]["semantic_causal_truth"] = True; mutations.append(m)
        killed = sum(bool(_validate(x)) for x in mutations)
        if killed != len(mutations): errors.append(f"self-test killed {killed}/{len(mutations)}")
        else: print(f"COG-SELF-01-GATE SELF-TEST: {killed}/{len(mutations)} mutations killed")

    if errors:
        print("COG-SELF-01-GATE FAIL", *errors, sep="\n - ")
        return 1
    print("COG-SELF-01-GATE PASS: synthetic decision-relevant falsification primitive bound; promotion remains forbidden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
