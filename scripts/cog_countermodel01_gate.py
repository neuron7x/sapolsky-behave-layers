from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "research/results/COG-COUNTERMODEL-01/verdict.json"
R1 = ROOT / "research/results/COG-COUNTERMODEL-01R/verdict.json"
ART = ROOT / "artifacts/cog-countermodel-01r"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(parent: dict, r1: dict) -> list[str]:
    errors: list[str] = []
    if parent.get("verdict") != "AUTONOMOUS_COUNTERMODEL_GENERATOR_NOT_QUALIFIED":
        errors.append("parent negative verdict drift")
    if parent.get("scientific_pass") is not False:
        errors.append("parent negative scientific_pass drift")
    if parent.get("authority") != "NO_PROMOTION":
        errors.append("parent negative authority drift")

    if r1.get("verdict") != "SET_VALUED_COUNTERMODEL_GUARD_QUALIFIED_SYNTHETIC_NARROWED":
        errors.append("R1 verdict drift")
    if r1.get("scientific_pass") is not True:
        errors.append("R1 scientific_pass drift")
    if r1.get("authority") != "COUNTERMODEL_SET_GUARD_ONLY":
        errors.append("R1 authority drift")
    if r1.get("parent_verdict") != "AUTONOMOUS_COUNTERMODEL_GENERATOR_NOT_QUALIFIED":
        errors.append("R1 no longer binds parent failure")

    boundary = r1.get("epistemic_boundary", {})
    for key in (
        "assumption_conditional_interval_is_causal_truth",
        "hidden_true_beta_recovery_used_for_qualification",
        "pareto_membership_used_as_truth_criterion",
        "unconditional_causal_authority",
        "semantic_causality",
        "real_trace_identification",
        "replay_control",
        "active_control",
        "architecture_promotion",
    ):
        if boundary.get(key) is not False:
            errors.append(f"unsafe epistemic boundary {key}")
    if boundary.get("unrestricted_equivalence_set_is_all_real_beta_in_declared_reparameterization_class") is not True:
        errors.append("set-valued unrestricted equivalence boundary drift")

    for cohort in ("PRIMARY", "REPLICATION"):
        if r1.get("cohort_errors", {}).get(cohort) != []:
            errors.append(f"{cohort} recorded cohort errors")
        summary = r1.get("cohorts", {}).get(cohort, {})
        for fam in ("R0_VALID", "R1_COORDINATED_EXCLUSION", "R2_ALEATORIC_HIGH"):
            s = summary.get(fam, {})
            if s.get("all_real_unrestricted_set_rate") != 1.0:
                errors.append(f"{cohort} {fam} unrestricted set")
            if float(s.get("material_exact_countermodel_survival_rate", 0.0)) < 0.99:
                errors.append(f"{cohort} {fam} countermodel survival")
            if float(s.get("finite_grid_diameter_ge_1_rate", 0.0)) < 0.99:
                errors.append(f"{cohort} {fam} ambiguity diameter")
            if s.get("nonempty_frontier_rate") != 1.0:
                errors.append(f"{cohort} {fam} frontier")
            if float(s.get("max_frontier_path_error", 1.0)) > 1e-10:
                errors.append(f"{cohort} {fam} path reconstruction")
            if int(s.get("causal_authority_count", -1)) != 0:
                errors.append(f"{cohort} {fam} authority")
        for fam in ("R0_VALID", "R1_COORDINATED_EXCLUSION"):
            s = summary.get(fam, {})
            if float(s.get("direct_interval_exists_rate", 0.0)) < 0.95:
                errors.append(f"{cohort} {fam} interval existence")
            if float(s.get("direct_interval_width_lt_material_shift_rate", 0.0)) < 0.95:
                errors.append(f"{cohort} {fam} interval width")
            if float(s.get("no_material_countermodel_within_bound_rate", 0.0)) < 0.95:
                errors.append(f"{cohort} {fam} material bound")
            if float(s.get("assumption_conditional_state_rate", 0.0)) < 0.95:
                errors.append(f"{cohort} {fam} assumption conditional state")
        r3 = summary.get("R3_UPSTREAM_INVALID", {})
        if float(r3.get("upstream_ineligible_rate", 0.0)) < 0.95:
            errors.append(f"{cohort} R3 upstream veto")
        if int(r3.get("causal_authority_count", -1)) != 0:
            errors.append(f"{cohort} R3 authority")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in (PARENT, R1, ART / "seed_results.csv", ART / "verdict.json", ART / "SHA256SUMS"):
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
    if errors:
        print("COG-COUNTERMODEL01-GATE FAIL", *errors, sep="\n - ")
        return 1

    for line in (ART / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = ART / name
        if not path.is_file() or _sha(path) != expected:
            errors.append(f"checksum {name}")
    if _sha(ART / "verdict.json") != _sha(R1):
        errors.append("artifact/research R1 verdict mismatch")

    parent = json.loads(PARENT.read_text())
    r1 = json.loads(R1.read_text())
    errors.extend(_validate(parent, r1))

    if "--self-test" in sys.argv:
        mutants: list[tuple[dict, dict]] = []
        p = json.loads(json.dumps(parent)); q = json.loads(json.dumps(r1)); p["scientific_pass"] = True; mutants.append((p, q))
        p = json.loads(json.dumps(parent)); q = json.loads(json.dumps(r1)); q["epistemic_boundary"]["unconditional_causal_authority"] = True; mutants.append((p, q))
        p = json.loads(json.dumps(parent)); q = json.loads(json.dumps(r1)); q["cohorts"]["PRIMARY"]["R1_COORDINATED_EXCLUSION"]["material_exact_countermodel_survival_rate"] = 0.0; mutants.append((p, q))
        p = json.loads(json.dumps(parent)); q = json.loads(json.dumps(r1)); q["epistemic_boundary"]["hidden_true_beta_recovery_used_for_qualification"] = True; mutants.append((p, q))
        p = json.loads(json.dumps(parent)); q = json.loads(json.dumps(r1)); q["cohorts"]["REPLICATION"]["R3_UPSTREAM_INVALID"]["upstream_ineligible_rate"] = 0.0; mutants.append((p, q))
        killed = sum(bool(_validate(p, q)) for p, q in mutants)
        if killed != len(mutants):
            errors.append(f"self-test killed {killed}/{len(mutants)}")
        else:
            print(f"COG-COUNTERMODEL01-GATE SELF-TEST: {killed}/{len(mutants)} authority/truth-selection mutations killed")

    if errors:
        print("COG-COUNTERMODEL01-GATE FAIL", *errors, sep="\n - ")
        return 1
    print("COG-COUNTERMODEL01-GATE PASS: parent failure preserved; R1 set-valued countermodel guard qualified narrowly with zero causal authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
