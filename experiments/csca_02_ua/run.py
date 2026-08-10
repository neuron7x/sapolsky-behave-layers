from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import time

from cwc.inference.abstention import AbstentionPolicy
from experiments.csca_02_ua.common import (
    CONFIRMATORY_FAMILIES,
    evaluate_raw_case,
    generate_case,
    score_cases,
    serialize_raw,
)

ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy(path: Path) -> tuple[AbstentionPolicy, str]:
    payload = json.loads(path.read_text())
    policy_data = payload["policy"]
    expected = payload["sha256"]
    canonical = json.dumps(policy_data, sort_keys=True, separators=(",", ":")).encode()
    actual = hashlib.sha256(canonical).hexdigest()
    if actual != expected:
        raise RuntimeError("frozen abstention policy hash mismatch")
    return AbstentionPolicy(**policy_data), actual


def qualification(score) -> tuple[bool, list[str]]:
    reasons = []
    if not score["selective_false_causal_authority"] < score["no_abstention_false_causal_authority"]:
        reasons.append("FALSE_AUTHORITY_NOT_REDUCED")
    if score["selective_false_causal_authority"] > 0.05:
        reasons.append("FALSE_AUTHORITY_GT_0_05")
    if score["causal_rank_accuracy_given_accept"] < 0.90:
        reasons.append("ACCEPT_ACCURACY_LT_0_90")
    if score["coverage"] < 0.20:
        reasons.append("COVERAGE_LT_0_20")
    if score["by_family"]["N0_ZERO_CAUSE"]["accepted"] != 0:
        reasons.append("ZERO_CAUSE_ACCEPTED")
    if score["by_family"]["M11_SHARED_MODEL_CLASS_MISSPECIFICATION"]["accepted"] != 0:
        reasons.append("SHARED_WRONG_STRUCTURE_ACCEPTED")
    for family, stats in score["by_family"].items():
        if stats["false_authority_rate"] > 0.10:
            reasons.append(f"FAMILY_FALSE_AUTHORITY_GT_0_10:{family}")
    return not reasons, reasons


def write_matrix(path: Path, raw, decisions) -> None:
    lookup = {(d["seed"], d["family"]): d for d in decisions}
    fields = [
        "seed", "family", "true_causal_set", "provisional_candidate", "state", "accepted_candidate",
        "false_authority", "no_abstention_false_authority", "intervention_nrmse", "model_disagreement",
        "rank_stability", "ood_score", "factual_rmse", "mean_false_credit_mass",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in raw:
            d = lookup[(r.seed, r.family)]
            writer.writerow({
                "seed": r.seed,
                "family": r.family,
                "true_causal_set": "|".join(r.true_causal_set),
                "provisional_candidate": r.provisional_candidate,
                "state": d["state"],
                "accepted_candidate": d["candidate"] or "",
                "false_authority": d["false_authority"],
                "no_abstention_false_authority": r.no_abstention_false_authority,
                "intervention_nrmse": r.intervention_nrmse,
                "model_disagreement": r.model_disagreement,
                "rank_stability": r.rank_stability,
                "ood_score": r.ood_score,
                "factual_rmse": r.factual_rmse,
                "mean_false_credit_mass": r.mean_false_credit_mass,
            })


def run_cohort(seed_start: int, seed_count: int, policy: AbstentionPolicy):
    raw = []
    for seed in range(seed_start, seed_start + seed_count):
        for family in CONFIRMATORY_FAMILIES:
            raw.append(evaluate_raw_case(generate_case(seed, family)))
    score = score_cases(raw, policy)
    passed, reasons = qualification(score)
    return raw, score, passed, reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--primary-start", type=int, default=41000)
    parser.add_argument("--replication-start", type=int, default=51000)
    parser.add_argument("--seed-count", type=int, default=32)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    policy, policy_sha = load_policy(args.policy)
    started = time.perf_counter()
    primary_raw, primary_score, primary_pass, primary_reasons = run_cohort(args.primary_start, args.seed_count, policy)
    replication_raw, replication_score, replication_pass, replication_reasons = run_cohort(args.replication_start, args.seed_count, policy)
    elapsed = time.perf_counter() - started

    write_matrix(args.out / "16_STRUCTURAL_MISSPECIFICATION_MATRIX.csv", primary_raw + replication_raw, primary_score["decisions"] + replication_score["decisions"])
    (args.out / "primary_cases.json").write_text(json.dumps([serialize_raw(r) for r in primary_raw], indent=2, sort_keys=True) + "\n")
    (args.out / "replication_cases.json").write_text(json.dumps([serialize_raw(r) for r in replication_raw], indent=2, sort_keys=True) + "\n")
    pass_all = primary_pass and replication_pass
    result = {
        "experiment": "CSCA-02-UA Counterfactual Uncertainty & Abstention Qualification",
        "policy_sha256": policy_sha,
        "preregistration_sha256": sha256_file(ROOT / "experiments/csca_02_ua/PREREGISTRATION.md"),
        "implementation_sha256": sha256_file(ROOT / "experiments/csca_02_ua/common.py"),
        "primary": {"pass": primary_pass, "failure_reasons": primary_reasons, **{k: v for k, v in primary_score.items() if k != "decisions"}},
        "replication": {"pass": replication_pass, "failure_reasons": replication_reasons, **{k: v for k, v in replication_score.items() if k != "decisions"}},
        "wall_seconds": elapsed,
        "scientific_pass": pass_all,
        "verdict": "UNCERTAINTY_AWARE_CREDIT_QUALIFIED" if pass_all else "UNCERTAINTY_MODEL_NOT_CAUSALLY_ADEQUATE",
        "authority": "UNCERTAINTY_QUALIFIED" if pass_all else "RESEARCH_ONLY",
        "shadow_inference_authorized": bool(pass_all),
        "active_causal_control_authorized": False,
        "paper_reproduction_authority": False,
        "biological_mechanism_authority": False,
        "architecture_promotion_authority": False,
    }
    (args.out / "15_CSCA_02_RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if pass_all else 3


if __name__ == "__main__":
    raise SystemExit(main())
