from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path
import subprocess

from cwc.benchmarks.causal_authority import (
    POLICIES,
    analytic_oracle,
    decisions_equal,
    generate_cohort,
    pareto_dominates,
    policy_oracle,
    runtime_oracle,
    score_policy,
    serialize_case,
    surface_signature,
    validate_f11_triads,
)

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/cab-01-q1-r1"
RES = ROOT / "research/results/CAB-01-Q1-R1"
COHORTS = {"PRIMARY_R1": 510811, "REPLICATION_R1": 610811}
N = 128
PREREG_COMMIT = "fdd89e4c6ef578647e8522035a6bbbb62185c33f"
PARENT_Q1_EVIDENCE_COMMIT = "2d3bec65972a213dcdb0f24ef53a4edf4b3f0ec2"
GENERATOR_IMPLEMENTATION_COMMIT = "a8ed935f1140eb5dba2e971dcf20229831fd1e12"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def _implementation_commit() -> str:
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", "experiments/cab_01_q1_r1/run.py", "tests/test_cab01_q1_r1.py"],
        cwd=ROOT,
        text=True,
    ).strip()


def evaluate_surface_null(cases) -> dict[str, float | int | bool]:
    signatures = {surface_signature(c.task) for c in cases}
    train = [c for i, c in enumerate(cases) if i % 5 != 0]
    test = [c for i, c in enumerate(cases) if i % 5 == 0]
    by_signature: dict[tuple[object, ...], collections.Counter[str]] = {}
    for c in train:
        by_signature.setdefault(surface_signature(c.task), collections.Counter())[c.expected_state] += 1
    train_majority = collections.Counter(c.expected_state for c in train).most_common(1)[0][0]
    correct = 0
    for c in test:
        counts = by_signature.get(surface_signature(c.task))
        pred = counts.most_common(1)[0][0] if counts else train_majority
        correct += int(pred == c.expected_state)
    surface_accuracy = correct / len(test)
    heldout_majority = max(collections.Counter(c.expected_state for c in test).values()) / len(test)
    full_majority = max(collections.Counter(c.expected_state for c in cases).values()) / len(cases)
    structural_pass = len(signatures) == 1
    predictive_pass = surface_accuracy <= heldout_majority + 1e-12
    return {
        "unique_surface_signatures": len(signatures),
        "surface_only_accuracy": surface_accuracy,
        "heldout_majority_class_rate": heldout_majority,
        "full_cohort_majority_class_rate": full_majority,
        "structural_surface_null_pass": structural_pass,
        "heldout_predictive_null_pass": predictive_pass,
        "surface_leakage_pass": structural_pass and predictive_pass,
        "heldout_n": len(test),
    }


def run() -> dict[str, object]:
    ART.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    all_cases = []
    errors: list[str] = []
    cohort_summary: dict[str, object] = {}
    regeneration_hashes: dict[str, dict[str, str]] = {}

    for cohort, seed_base in COHORTS.items():
        cases = generate_cohort(cohort, seed_base, N)
        replay = generate_cohort(cohort, seed_base, N)
        rows = [serialize_case(c) for c in cases]
        replay_rows = [serialize_case(c) for c in replay]
        h1 = hashlib.sha256(b"".join(_json_bytes(r) for r in rows)).hexdigest()
        h2 = hashlib.sha256(b"".join(_json_bytes(r) for r in replay_rows)).hexdigest()
        regeneration_hashes[cohort] = {"generation": h1, "replay": h2}
        if h1 != h2:
            errors.append(f"{cohort}: deterministic replay mismatch")

        counts = collections.Counter(c.family for c in cases)
        expected_counts = {**{f"F{i}": N for i in range(11)}, "F11": 3 * N}
        if dict(sorted(counts.items())) != expected_counts:
            errors.append(f"{cohort}: family count mismatch")

        disagreements = 0
        for c in cases:
            a_state, a_decision = analytic_oracle(c.task)
            r_state, r_decision = runtime_oracle(c.task)
            if (
                a_state != c.expected_state
                or r_state != c.expected_state
                or not decisions_equal(a_decision, c.construction_label)
                or not decisions_equal(r_decision, c.construction_label)
            ):
                disagreements += 1
        if disagreements:
            errors.append(f"{cohort}: {disagreements} label-path disagreements")

        f11_pass, f11_errors = validate_f11_triads(cases)
        if not f11_pass:
            errors.extend(f11_errors[:20])

        surface = evaluate_surface_null(cases)
        if not surface["surface_leakage_pass"]:
            errors.append(f"{cohort}: R1 surface null failed")

        policy_metrics: dict[str, dict[str, float | int]] = {}
        for name, policy in POLICIES.items():
            policy_metrics[name] = score_policy(cases, [policy(c.task, c.seed) for c in cases])
        policy_metrics["hidden_state_oracle"] = score_policy(cases, [policy_oracle(c, c.seed) for c in cases])
        non_oracle = [k for k in policy_metrics if k != "hidden_state_oracle"]
        dominators = {
            target: [
                name
                for name in non_oracle
                if name != target and pareto_dominates(policy_metrics[name], policy_metrics[target])
            ]
            for target in ("always_act", "always_abstain")
        }
        if not dominators["always_act"]:
            errors.append(f"{cohort}: always_act remains Pareto-optimal")
        if not dominators["always_abstain"]:
            errors.append(f"{cohort}: always_abstain remains Pareto-optimal")

        cohort_summary[cohort] = {
            "seed_base": seed_base,
            "case_count": len(cases),
            "family_counts": dict(sorted(counts.items())),
            "label_path_disagreements": disagreements,
            "f11_triads_pass": f11_pass,
            **surface,
            "pareto_dominators": dominators,
            "policy_metrics": policy_metrics,
        }
        all_cases.extend(cases)

    verdict: dict[str, object] = {
        "experiment_id": "CAB-01-Q1-R1",
        "verdict": "CAB01_Q1_R1_BENCHMARK_QUALIFIED_SYNTHETIC" if not errors else "CAB01_Q1_R1_NOT_QUALIFIED",
        "benchmark_qualified": not errors,
        "authority": "SYNTHETIC_BENCHMARK_QUALIFICATION_ONLY",
        "parent_q1_evidence_commit": PARENT_Q1_EVIDENCE_COMMIT,
        "preconfirmatory_r1_preregistration_commit": PREREG_COMMIT,
        "generator_implementation_commit": GENERATOR_IMPLEMENTATION_COMMIT,
        "r1_evaluation_implementation_commit": _implementation_commit(),
        "n_ordinary_per_family_per_cohort": N,
        "n_f11_groups_per_cohort": N,
        "cohorts": cohort_summary,
        "regeneration_hashes": regeneration_hashes,
        "errors": errors,
        "novelty_status": "UNKNOWN_OVERLAP_CONCEDED",
        "non_promotion_boundary": {
            "cwc_superiority": False,
            "real_model_transfer": False,
            "natural_language_contamination_resistance": False,
            "semantic_causal_truth": False,
            "large_model_compute_pareto": False,
            "external_independent_replication": False,
            "flagship_result_qualified": False,
        },
    }

    with (ART / "instances.jsonl").open("wb") as f:
        for c in all_cases:
            f.write(_json_bytes(serialize_case(c)))
    (ART / "baseline_metrics.json").write_text(json.dumps(cohort_summary, indent=2, sort_keys=True) + "\n")
    (ART / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    (RES / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return verdict


if __name__ == "__main__":
    verdict = run()
    raise SystemExit(0 if verdict["benchmark_qualified"] else 1)
