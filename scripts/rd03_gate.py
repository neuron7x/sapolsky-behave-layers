from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(root: Path, *, result_override=None, null_override=None) -> list[str]:
    errors: list[str] = []
    reg = root / "research/registry"
    result_path = root / "research/results/CSCA-02-UA/15_CSCA_02_RESULTS.json"
    null_path = root / "research/results/CSCA-02-UA/NULL_ATTACKS.json"
    required = [
        reg / "11_COUNTERFACTUAL_MODEL_REGISTRY.yaml",
        reg / "12_UNCERTAINTY_CALIBRATION.json",
        reg / "13_ABSTENTION_POLICY.yaml",
        reg / "14_CSCA_02_PREREGISTRATION.md",
        reg / "15_CSCA_02_RESULTS.json",
        root / "research/reports/16_STRUCTURAL_MISSPECIFICATION_MATRIX.csv",
        reg / "17_INFERENCE_TRACE_SCHEMA.json",
        root / "research/preregistration/18_REAL_MODEL_REPLAY_PREREGISTRATION.md",
        root / "research/reports/19_PHYSICAL_COMPUTE_REPORT.json",
        root / "research/reports/20_INFERENCE_PROMOTION_DECISION.md",
        result_path,
        null_path,
        reg / "rd03_pipeline_state.json",
        root / "experiments/csca_02_ua/PREREGISTRATION.md",
        root / "research/results/ACT-RD-03/verdict.json",
        root / "research/results/ACT-RD-03/SHA256SUMS",
        root / "research/reports/ACT_RD_03_EXECUTION_REPORT.md",
        root / "research/results/CSCA-02-UA/SHA256SUMS",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing RD03 artifact: {path.relative_to(root)}")
    if errors:
        return errors

    policy_wrapper = load_json(reg / "13_ABSTENTION_POLICY.yaml")
    actual_policy_sha = canonical_sha(policy_wrapper["policy"])
    if actual_policy_sha != policy_wrapper.get("sha256"):
        errors.append("frozen policy canonical SHA mismatch")

    result = result_override if result_override is not None else load_json(result_path)
    nulls = null_override if null_override is not None else load_json(null_path)
    prereg = root / "experiments/csca_02_ua/PREREGISTRATION.md"
    if result.get("policy_sha256") != policy_wrapper.get("sha256"):
        errors.append("result policy SHA does not bind frozen policy")
    if result.get("preregistration_sha256") != sha256_file(prereg):
        errors.append("result preregistration SHA drift")

    # Frozen negative scientific result is itself binding evidence. A gate PASS means
    # preservation of that result, never promotion of the mechanism.
    if result.get("verdict") != "UNCERTAINTY_MODEL_NOT_CAUSALLY_ADEQUATE":
        errors.append("CSCA-02 negative verdict drift/promoted")
    if result.get("scientific_pass") is not False:
        errors.append("CSCA-02 scientific_pass must remain false")
    if result.get("authority") != "RESEARCH_ONLY":
        errors.append("RD03 causal authority silently promoted")
    for key in ("shadow_inference_authorized", "active_causal_control_authorized", "architecture_promotion_authority"):
        if result.get(key) is not False:
            errors.append(f"unauthorized promotion: {key}")

    primary = result.get("primary", {})
    replication = result.get("replication", {})
    if primary.get("pass") is not False or "COVERAGE_LT_0_20" not in primary.get("failure_reasons", []):
        errors.append("primary preregistered coverage failure not preserved")
    if primary.get("accepted") != 43 or primary.get("n") != 224:
        errors.append("primary frozen sample/accept count drift")
    if replication.get("pass") is not True or replication.get("accepted") != 45 or replication.get("n") != 224:
        errors.append("independent replication frozen result drift")
    for cohort_name, cohort in (("primary", primary), ("replication", replication)):
        if cohort.get("selective_false_causal_authority") != 0.0:
            errors.append(f"{cohort_name} false authority changed")
        if cohort.get("causal_rank_accuracy_given_accept") != 1.0:
            errors.append(f"{cohort_name} accepted accuracy changed")
        for family in ("N0_ZERO_CAUSE", "M11_SHARED_MODEL_CLASS_MISSPECIFICATION"):
            if cohort.get("by_family", {}).get(family, {}).get("accepted") != 0:
                errors.append(f"{cohort_name} {family} gained causal authority")

    if nulls.get("verdict") != "NULL_ATTACK_EXPOSED_UNRESOLVED_FAILURE":
        errors.append("null-suite verdict drift")
    if nulls.get("all_nulls_pass") is not False or nulls.get("promotion_authority") is not False:
        errors.append("mandatory null failure was erased or promoted")
    context = nulls.get("checks", {}).get("NULL_10_CONTEXT_DEPENDENT_AUTHORITY", {})
    if context.get("pass") is not False or context.get("count") != 12:
        errors.append("context-conditional authority failure not preserved")

    replay_text = (root / "research/preregistration/18_REAL_MODEL_REPLAY_PREREGISTRATION.md").read_text(encoding="utf-8")
    if "BLOCKED_BY_CSCA_02_UA_FAIL" not in replay_text or "Execution authority:** NONE" not in replay_text:
        errors.append("blocked real-model replay boundary drift")
    physical = load_json(root / "research/reports/19_PHYSICAL_COMPUTE_REPORT.json")
    if physical.get("status") != "NOT_EXECUTED_ANCESTOR_GATE_FAILED" or physical.get("measured_hardware_claims") is not False:
        errors.append("physical compute was silently claimed after failed ancestor gate")
    promotion = (root / "research/reports/20_INFERENCE_PROMOTION_DECISION.md").read_text(encoding="utf-8")
    if "NO_PROMOTION" not in promotion or "RESEARCH_ONLY" not in promotion:
        errors.append("inference promotion report lost fail-closed decision")
    pipeline = load_json(reg / "rd03_pipeline_state.json")
    if pipeline.get("target_reached") is not False or pipeline.get("current_authority") != "RESEARCH_ONLY":
        errors.append("pipeline state silently promoted")
    for key in ("shadow_inference_authorized", "real_model_replay_authorized", "physical_compute_authorized", "active_causal_control_authorized"):
        if pipeline.get(key) is not False:
            errors.append(f"pipeline unauthorized state: {key}")

    act_verdict = load_json(root / "research/results/ACT-RD-03/verdict.json")
    if act_verdict.get("scientific_eval") != "FAIL" or act_verdict.get("current_authority") != "RESEARCH_ONLY":
        errors.append("ACT-RD-03 overall verdict lost fail-closed scientific decision")
    if act_verdict.get("target_reached") is not False:
        errors.append("ACT-RD-03 target silently marked reached")

    # Verify every act-level evidence binding. Paths are repository-relative.
    for line in (root / "research/results/ACT-RD-03/SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(None, 1)
        path = root / rel.strip()
        if not path.is_file():
            errors.append(f"act evidence binding missing: {rel.strip()}")
        elif sha256_file(path) != expected:
            errors.append(f"act evidence SHA mismatch: {rel.strip()}")

    return errors


def self_test() -> list[str]:
    base = load_json(ROOT / "research/results/CSCA-02-UA/15_CSCA_02_RESULTS.json")
    nulls = load_json(ROOT / "research/results/CSCA-02-UA/NULL_ATTACKS.json")
    mutations = []

    m = json.loads(json.dumps(base)); m["verdict"] = "UNCERTAINTY_AWARE_CREDIT_QUALIFIED"; m["scientific_pass"] = True
    mutations.append((m, nulls, "verdict promotion"))
    m = json.loads(json.dumps(base)); m["shadow_inference_authorized"] = True
    mutations.append((m, nulls, "shadow authority bypass"))
    m = json.loads(json.dumps(base)); m["authority"] = "SHADOW_INFERENCE_QUALIFIED"
    mutations.append((m, nulls, "authority bypass"))
    n = json.loads(json.dumps(nulls)); n["all_nulls_pass"] = True; n["checks"]["NULL_10_CONTEXT_DEPENDENT_AUTHORITY"]["pass"] = True
    mutations.append((base, n, "context-null erasure"))

    failures = []
    for result, null_payload, label in mutations:
        if not validate(ROOT, result_override=result, null_override=null_payload):
            failures.append(f"self-test failed to kill mutation: {label}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    errors = self_test() if args.self_test else validate(ROOT)
    if errors:
        print("RD03-GATE: FAIL")
        for error in errors:
            print(" -", error)
        return 1
    if args.self_test:
        print("RD03-GATE SELF-TEST: PASS 4/4 semantic corruptions detected")
    else:
        result = load_json(ROOT / "research/results/CSCA-02-UA/15_CSCA_02_RESULTS.json")
        print(
            "RD03-GATE: PASS "
            f"scientific_verdict={result['verdict']} authority={result['authority']} "
            f"primary={result['primary']['accepted']}/{result['primary']['n']} "
            f"replication={result['replication']['accepted']}/{result['replication']['n']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
