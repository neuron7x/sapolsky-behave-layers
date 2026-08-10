from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import time

from cwc.inference.abstention import AbstentionPolicy
from experiments.csca_02_ua.common import (
    CALIBRATION_FAMILIES,
    evaluate_raw_case,
    generate_case,
    policy_to_dict,
    score_cases,
    serialize_raw,
)

ROOT = Path(__file__).resolve().parents[2]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def policy_candidates(raw_cases):
    adequacy = sorted(r.intervention_nrmse for r in raw_cases)
    disagreement = sorted(r.model_disagreement for r in raw_cases)
    ood = sorted(r.ood_score for r in raw_cases)

    def q(values, p):
        idx = min(len(values) - 1, max(0, round((len(values) - 1) * p)))
        return values[idx]

    adequacy_grid = sorted(set([0.15, 0.25, 0.40, 0.60, 0.85, 1.20, 2.0, q(adequacy, 0.50), q(adequacy, 0.75), q(adequacy, 0.90), q(adequacy, 0.95)]))
    disagreement_grid = sorted(set([0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.0, q(disagreement, 0.50), q(disagreement, 0.75), q(disagreement, 0.90), q(disagreement, 0.95)]))
    ood_grid = sorted(set([q(ood, 0.75), q(ood, 0.90), q(ood, 0.95), max(ood) + 1e-9]))
    for delta, max_nrmse, max_dis, min_rank, max_ood in itertools.product(
        (0.0, 0.01, 0.02, 0.05, 0.10),
        adequacy_grid,
        disagreement_grid,
        (0.50, 0.67, 0.75, 0.90),
        ood_grid,
    ):
        yield AbstentionPolicy(
            version="CSCA-02-UA-calibration-candidate",
            delta=float(delta),
            max_intervention_nrmse=float(max_nrmse),
            max_model_disagreement=float(max_dis),
            min_rank_stability=float(min_rank),
            max_ood_score=float(max_ood),
            min_intervention_support=32,
            leverage_floor=0.10,
        )


def qualifies_calibration(score) -> bool:
    zero = score["by_family"].get("N0_ZERO_CAUSE", {})
    return (
        score["selective_false_causal_authority"] <= 0.025
        and score["causal_rank_accuracy_given_accept"] >= 0.95
        and score["coverage"] >= 0.20
        and zero.get("accepted", 1) == 0
    )


def select_policy(raw_cases):
    admissible = []
    for policy in policy_candidates(raw_cases):
        score = score_cases(raw_cases, policy)
        if qualifies_calibration(score):
            complexity = (
                policy.delta + policy.max_intervention_nrmse + policy.max_model_disagreement
                + (1.0 - policy.min_rank_stability) + policy.max_ood_score
            )
            key = (
                -score["coverage"],
                score["selective_false_causal_authority"],
                score["mean_false_credit_mass_given_accept"],
                complexity,
                tuple(policy_to_dict(policy).values()),
            )
            admissible.append((key, policy, score))
    if not admissible:
        return None, None
    admissible.sort(key=lambda item: item[0])
    _, policy, score = admissible[0]
    return policy, score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed-start", type=int, default=31000)
    parser.add_argument("--seed-count", type=int, default=32)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    raw = []
    for seed in range(args.seed_start, args.seed_start + args.seed_count):
        for family in CALIBRATION_FAMILIES:
            raw.append(evaluate_raw_case(generate_case(seed, family)))
    policy, score = select_policy(raw)
    elapsed = time.perf_counter() - started
    raw_payload = [serialize_raw(r) for r in raw]
    (args.out / "calibration_cases.json").write_text(json.dumps(raw_payload, indent=2, sort_keys=True) + "\n")
    if policy is None:
        verdict = {
            "status": "CALIBRATION_FAILED_NO_ADMISSIBLE_POLICY",
            "n_cases": len(raw),
            "wall_seconds": elapsed,
            "confirmatory_authority": False,
        }
        (args.out / "12_UNCERTAINTY_CALIBRATION.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
        print(json.dumps(verdict, indent=2, sort_keys=True))
        return 2

    policy_dict = policy_to_dict(policy)
    policy_dict["version"] = "CSCA-02-UA-POLICY-V1"
    canonical = json.dumps(policy_dict, sort_keys=True, separators=(",", ":")).encode()
    policy_sha = sha256_bytes(canonical)
    calibration = {
        "status": "CALIBRATION_PASS_POLICY_FROZEN",
        "seed_start": args.seed_start,
        "seed_count": args.seed_count,
        "families": list(CALIBRATION_FAMILIES),
        "n_cases": len(raw),
        "selected_policy": policy_dict,
        "selected_policy_sha256": policy_sha,
        "calibration_score": {k: v for k, v in score.items() if k != "decisions"},
        "wall_seconds": elapsed,
        "confirmatory_authority": True,
    }
    (args.out / "12_UNCERTAINTY_CALIBRATION.json").write_text(json.dumps(calibration, indent=2, sort_keys=True) + "\n")
    # YAML-compatible JSON is intentionally used: JSON is a strict YAML 1.2 subset and
    # avoids introducing a new parser dependency into the evidence spine.
    (args.out / "13_ABSTENTION_POLICY.yaml").write_text(json.dumps({"policy": policy_dict, "sha256": policy_sha}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(calibration, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
