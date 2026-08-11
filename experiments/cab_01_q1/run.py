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
ART = ROOT / "artifacts/cab-01-q1"
RES = ROOT / "research/results/CAB-01-Q1"
COHORTS = {"PRIMARY": 310811, "REPLICATION": 410811}
N = 128
PREREG_COMMIT = "f55fde0f7eee54f88f6f0443d3de48dbbb582afe"
PARENT_DESIGN_COMMIT = "a849b63"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def _implementation_commit() -> str:
    paths = [
        "cwc/benchmarks/causal_authority.py",
        "experiments/cab_01_q1/run.py",
        "tests/test_cab01_q1.py",
    ]
    return subprocess.check_output(["git", "log", "-1", "--format=%H", "--", *paths], cwd=ROOT, text=True).strip()


def run() -> dict[str, object]:
    ART.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    all_cases = []
    cohort_summary: dict[str, object] = {}
    errors: list[str] = []
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

        family_counts = collections.Counter(c.family for c in cases)
        expected_counts = {**{f"F{i}": N for i in range(11)}, "F11": 3 * N}
        if dict(sorted(family_counts.items())) != expected_counts:
            errors.append(f"{cohort}: family count mismatch {dict(family_counts)}")

        label_disagreements = []
        for c in cases:
            a_state, a_decision = analytic_oracle(c.task)
            r_state, r_decision = runtime_oracle(c.task)
            if a_state != c.expected_state or r_state != c.expected_state or not decisions_equal(a_decision, c.construction_label) or not decisions_equal(r_decision, c.construction_label):
                label_disagreements.append({
                    "family": c.family,
                    "seed": c.seed,
                    "construction_state": c.expected_state,
                    "analytic_state": a_state,
                    "runtime_state": r_state,
                    "construction": serialize_case(c)["construction_label"],
                    "analytic": vars(a_decision) if hasattr(a_decision, "__dict__") else {k: getattr(a_decision, k) for k in a_decision.__slots__},
                    "runtime": vars(r_decision) if hasattr(r_decision, "__dict__") else {k: getattr(r_decision, k) for k in r_decision.__slots__},
                })
        if label_disagreements:
            errors.append(f"{cohort}: {len(label_disagreements)} label-path disagreements")

        f11_pass, f11_errors = validate_f11_triads(cases)
        if not f11_pass:
            errors.extend(f11_errors[:20])

        # Surface-only classifier sees shape signatures only. Deterministic 4/5 train, 1/5 test.
        labels = [c.expected_state for c in cases]
        majority_rate = max(collections.Counter(labels).values()) / len(labels)
        by_signature: dict[tuple[object, ...], collections.Counter[str]] = {}
        train = [c for i, c in enumerate(cases) if i % 5 != 0]
        test = [c for i, c in enumerate(cases) if i % 5 == 0]
        for c in train:
            by_signature.setdefault(surface_signature(c.task), collections.Counter())[c.expected_state] += 1
        global_majority = collections.Counter(c.expected_state for c in train).most_common(1)[0][0]
        correct = 0
        for c in test:
            counts = by_signature.get(surface_signature(c.task))
            pred = counts.most_common(1)[0][0] if counts else global_majority
            correct += int(pred == c.expected_state)
        surface_accuracy = correct / len(test)
        leakage_pass = surface_accuracy <= majority_rate + 1e-12
        if not leakage_pass:
            errors.append(f"{cohort}: surface leakage {surface_accuracy:.6f}>{majority_rate:.6f}")

        policy_metrics: dict[str, dict[str, float | int]] = {}
        for name, policy in POLICIES.items():
            outputs = [policy(c.task, c.seed) for c in cases]
            policy_metrics[name] = score_policy(cases, outputs)
        oracle_outputs = [policy_oracle(c, c.seed) for c in cases]
        policy_metrics["hidden_state_oracle"] = score_policy(cases, oracle_outputs)

        non_oracle = [k for k in policy_metrics if k != "hidden_state_oracle"]
        dominators = {
            target: [name for name in non_oracle if name != target and pareto_dominates(policy_metrics[name], policy_metrics[target])]
            for target in ("always_act", "always_abstain")
        }
        if not dominators["always_act"]:
            errors.append(f"{cohort}: always_act remains Pareto-optimal")
        if not dominators["always_abstain"]:
            errors.append(f"{cohort}: always_abstain remains Pareto-optimal")

        cohort_summary[cohort] = {
            "seed_base": seed_base,
            "case_count": len(cases),
            "family_counts": dict(sorted(family_counts.items())),
            "label_path_disagreements": len(label_disagreements),
            "f11_triads_pass": f11_pass,
            "surface_only_accuracy": surface_accuracy,
            "majority_class_rate": majority_rate,
            "surface_leakage_pass": leakage_pass,
            "pareto_dominators": dominators,
            "policy_metrics": policy_metrics,
        }
        all_cases.extend(cases)

    verdict: dict[str, object] = {
        "experiment_id": "CAB-01-Q1",
        "verdict": "CAB01_Q1_BENCHMARK_QUALIFIED_SYNTHETIC" if not errors else "CAB01_Q1_NOT_QUALIFIED",
        "benchmark_qualified": not errors,
        "authority": "SYNTHETIC_BENCHMARK_QUALIFICATION_ONLY",
        "parent_design_commit": PARENT_DESIGN_COMMIT,
        "preconfirmatory_execution_preregistration_commit": PREREG_COMMIT,
        "implementation_commit": _implementation_commit(),
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

    instance_path = ART / "instances.jsonl"
    with instance_path.open("wb") as f:
        for c in all_cases:
            f.write(_json_bytes(serialize_case(c)))
    (ART / "baseline_metrics.json").write_text(json.dumps(cohort_summary, indent=2, sort_keys=True) + "\n")
    (ART / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    (RES / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return verdict


if __name__ == "__main__":
    v = run()
    raise SystemExit(0 if v["benchmark_qualified"] else 1)
