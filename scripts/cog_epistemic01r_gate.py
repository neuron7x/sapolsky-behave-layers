from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "research/results/COG-EPISTEMIC-01/verdict.json"
R1 = ROOT / "research/results/COG-EPISTEMIC-01R/verdict.json"
ART = ROOT / "artifacts/cog-epistemic-01r"
FAMILIES = {
    "F0_DIRECT_CONSTRUCTION_BYPASS",
    "F1_WRONG_CAPABILITY_CLASS",
    "F2_UNIDENTIFIED_RESURRECTION",
    "F3_FALSIFIED_RESURRECTION",
    "F4_NO_DIRECT_INTERVENTION_EVIDENCE",
    "F5_SURROGATE_AS_DIRECT_INTERVENTION",
    "F6_CROSS_CLAIM_TOKEN_REUSE",
    "F7_STALE_PARENT_TOKEN_REUSE",
    "F8_SCOPE_ESCALATION",
    "F9_EVIDENCE_HASH_OR_CLASS_MUTATION",
    "F10_LEGACY_ASSUMPTION_VIOLATION_PROMOTION",
    "F11_LEGACY_COUNTERMODEL_COLLAPSE",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(parent: dict, r1: dict) -> list[str]:
    errors: list[str] = []
    if parent.get("verdict") != "TYPED_EPISTEMIC_LATTICE_NOT_QUALIFIED" or parent.get("scientific_pass") is not False:
        errors.append("parent raw non-pass drift")
    if not any("F11_LEGACY_COUNTERMODEL_COLLAPSE" in e for e in parent.get("errors", [])):
        errors.append("parent F11 failure no longer preserved")

    if r1.get("verdict") != "TYPED_EPISTEMIC_LATTICE_QUALIFIED_SYNTHETIC_NARROWED":
        errors.append("R1 verdict drift")
    if r1.get("scientific_pass") is not True:
        errors.append("R1 scientific_pass drift")
    if r1.get("authority") != "EPISTEMIC_RUNTIME_SAFETY_PRIMITIVE_ONLY":
        errors.append("R1 authority drift")
    if r1.get("preconfirmatory_preregistration_commit") != "608e629a01490d58645d9c3f7fc73293b83ea3e4":
        errors.append("R1 preregistration commit drift")
    repair = r1.get("repair", {})
    if repair.get("thresholds_weakened") is not False:
        errors.append("repair weakened thresholds")
    if repair.get("frozen_family_semantics_changed") is not False:
        errors.append("repair changed family semantics")
    if repair.get("F10_F11_preconditions_changed_to_immutable_api_state_fixtures") is not True:
        errors.append("repair precondition fixture missing")
    if repair.get("fresh_namespaces") is not True:
        errors.append("fresh namespace requirement drift")
    if r1.get("positive_chain") != ["OBSERVED", "PREDICTIVE", "ASSUMPTION_CONDITIONAL", "INTERVENTION_SUPPORTED"]:
        errors.append("positive chain drift")
    if set(r1.get("terminal_states", [])) != {"UNIDENTIFIED", "FALSIFIED", "OOD", "ABSTAIN"}:
        errors.append("terminal states drift")
    if r1.get("errors") != []:
        errors.append("R1 recorded errors")

    boundary = r1.get("epistemic_boundary", {})
    for key in (
        "intervention_supported_equals_true_causal_model",
        "unconditional_causal_truth_state_exists",
        "terminal_record_resurrection_allowed",
        "surrogate_or_replay_can_mint_direct_intervention_authority",
        "semantic_causality",
        "real_trace_identification",
        "replay_control",
        "active_control",
        "architecture_promotion",
    ):
        if boundary.get(key) is not False:
            errors.append(f"unsafe boundary {key}")

    expected_ns = {"PRIMARY": ("R1_PRIMARY", 81001), "REPLICATION": ("R1_REPLICATION", 91001)}
    for cohort, (namespace, seed_base) in expected_ns.items():
        c = r1.get("cohorts", {}).get(cohort, {})
        if c.get("namespace") != namespace or c.get("seed_base") != seed_base:
            errors.append(f"{cohort} namespace/seed drift")
        if c.get("legal_transition_acceptance_rate") != 1.0:
            errors.append(f"{cohort} legal chain")
        if set(c.get("families", {})) != FAMILIES:
            errors.append(f"{cohort} family set drift")
        for family, fs in c.get("families", {}).items():
            if fs.get("n") != 128:
                errors.append(f"{cohort} {family} n")
            if fs.get("forbidden_accept_count") != 0 or fs.get("forbidden_acceptance_rate") != 0.0:
                errors.append(f"{cohort} {family} forbidden acceptance")
            if fs.get("unexpected_or_harness_error_count") != 0:
                errors.append(f"{cohort} {family} runtime/harness error")
        d = c.get("digest_checks", {})
        if d.get("deterministic_identical_content") is not True or d.get("payload_change_changes_digest") is not True:
            errors.append(f"{cohort} digest checks")
    return errors


def main() -> int:
    errors: list[str] = []
    for p in (PARENT, R1, ART / "verdict.json", ART / "transition_matrix.csv", ART / "SHA256SUMS"):
        if not p.is_file():
            errors.append(f"missing {p.relative_to(ROOT)}")
    if errors:
        print("COG-EPISTEMIC01R-GATE FAIL", *errors, sep="\n - ")
        return 1
    for line in (ART / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        p = ART / name
        if not p.is_file() or _sha(p) != expected:
            errors.append(f"checksum {name}")
    if _sha(ART / "verdict.json") != _sha(R1):
        errors.append("artifact/research R1 verdict mismatch")
    parent = json.loads(PARENT.read_text())
    r1 = json.loads(R1.read_text())
    errors.extend(_validate(parent, r1))

    if "--self-test" in sys.argv:
        mutants: list[tuple[dict, dict]] = []
        p=json.loads(json.dumps(parent)); q=json.loads(json.dumps(r1)); q["epistemic_boundary"]["terminal_record_resurrection_allowed"]=True; mutants.append((p,q))
        p=json.loads(json.dumps(parent)); q=json.loads(json.dumps(r1)); q["cohorts"]["PRIMARY"]["families"]["F5_SURROGATE_AS_DIRECT_INTERVENTION"]["forbidden_accept_count"]=1; mutants.append((p,q))
        p=json.loads(json.dumps(parent)); q=json.loads(json.dumps(r1)); q["cohorts"]["REPLICATION"]["families"]["F11_LEGACY_COUNTERMODEL_COLLAPSE"]["forbidden_acceptance_rate"]=1/128; mutants.append((p,q))
        p=json.loads(json.dumps(parent)); q=json.loads(json.dumps(r1)); q["repair"]["thresholds_weakened"]=True; mutants.append((p,q))
        p=json.loads(json.dumps(parent)); q=json.loads(json.dumps(r1)); q["positive_chain"][-1]="TRUE_CAUSAL_MODEL"; mutants.append((p,q))
        p=json.loads(json.dumps(parent)); q=json.loads(json.dumps(r1)); p["scientific_pass"]=True; mutants.append((p,q))
        killed=sum(bool(_validate(p,q)) for p,q in mutants)
        if killed != len(mutants):
            errors.append(f"self-test killed {killed}/{len(mutants)}")
        else:
            print(f"COG-EPISTEMIC01R-GATE SELF-TEST: {killed}/{len(mutants)} authority/repair mutations killed")

    if errors:
        print("COG-EPISTEMIC01R-GATE FAIL", *errors, sep="\n - ")
        return 1
    print("COG-EPISTEMIC01R-GATE PASS: parent harness failure preserved; fresh R1 typed epistemic lattice blocks all forbidden promotions with immutable F10/F11 state fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
