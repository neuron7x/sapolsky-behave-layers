from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/cog-epistemic-01"
VERDICT = ROOT / "research/results/COG-EPISTEMIC-01R/verdict.json"
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


def _validate(v: dict) -> list[str]:
    errors: list[str] = []
    if v.get("verdict") != "TYPED_EPISTEMIC_LATTICE_R1_QUALIFIED_SYNTHETIC_NARROWED":
        errors.append("verdict drift")
    if v.get("scientific_pass") is not True:
        errors.append("scientific_pass drift")
    if v.get("authority") != "EPISTEMIC_RUNTIME_SAFETY_PRIMITIVE_ONLY":
        errors.append("authority drift")
    if v.get("preconfirmatory_preregistration_commit") != "72e7f59da6e8cf6dce8984e2360fc4e9cbd6db1f":
        errors.append("preregistration commit drift")
    if v.get("positive_chain") != ["OBSERVED", "PREDICTIVE", "ASSUMPTION_CONDITIONAL", "INTERVENTION_SUPPORTED"]:
        errors.append("positive chain drift")
    if set(v.get("terminal_states", [])) != {"UNIDENTIFIED", "FALSIFIED", "OOD", "ABSTAIN"}:
        errors.append("terminal state set drift")
    if v.get("errors") != []:
        errors.append("recorded execution errors")

    boundary = v.get("epistemic_boundary", {})
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

    for cohort in ("PRIMARY_R1", "REPLICATION_R1"):
        c = v.get("cohorts", {}).get(cohort, {})
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
    for p in (ART / "verdict.json", ART / "transition_matrix.csv", ART / "SHA256SUMS", VERDICT):
        if not p.is_file():
            errors.append(f"missing {p.relative_to(ROOT)}")
    if errors:
        print("COG-EPISTEMIC01-GATE FAIL", *errors, sep="\n - ")
        return 1
    for line in (ART / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = ART / name
        if not path.is_file() or _sha(path) != expected:
            errors.append(f"checksum {name}")
    if _sha(ART / "verdict.json") != _sha(VERDICT):
        errors.append("artifact/research verdict mismatch")
    v = json.loads(VERDICT.read_text())
    errors.extend(_validate(v))

    if "--self-test" in sys.argv:
        mutants: list[dict] = []
        m = json.loads(json.dumps(v)); m["epistemic_boundary"]["terminal_record_resurrection_allowed"] = True; mutants.append(m)
        m = json.loads(json.dumps(v)); m["cohorts"]["PRIMARY_R1"]["families"]["F5_SURROGATE_AS_DIRECT_INTERVENTION"]["forbidden_accept_count"] = 1; mutants.append(m)
        m = json.loads(json.dumps(v)); m["cohorts"]["REPLICATION_R1"]["families"]["F6_CROSS_CLAIM_TOKEN_REUSE"]["forbidden_acceptance_rate"] = 1/128; mutants.append(m)
        m = json.loads(json.dumps(v)); m["epistemic_boundary"]["unconditional_causal_truth_state_exists"] = True; mutants.append(m)
        m = json.loads(json.dumps(v)); m["positive_chain"][-1] = "TRUE_CAUSAL_MODEL"; mutants.append(m)
        m = json.loads(json.dumps(v)); m["cohorts"]["PRIMARY_R1"]["digest_checks"]["payload_change_changes_digest"] = False; mutants.append(m)
        killed = sum(bool(_validate(m)) for m in mutants)
        if killed != len(mutants):
            errors.append(f"self-test killed {killed}/{len(mutants)}")
        else:
            print(f"COG-EPISTEMIC01-GATE SELF-TEST: {killed}/{len(mutants)} authority/type mutations killed")

    if errors:
        print("COG-EPISTEMIC01-GATE FAIL", *errors, sep="\n - ")
        return 1
    print("COG-EPISTEMIC01-GATE PASS: typed capability-bound epistemic lattice blocks all frozen illegal promotions in PRIMARY and REPLICATION.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
