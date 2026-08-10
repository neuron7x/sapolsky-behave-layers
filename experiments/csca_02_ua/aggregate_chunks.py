from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_matrix(path: Path, chunks: list[dict[str, object]]) -> None:
    fields = [
        "cohort", "seed", "family", "true_causal_set", "provisional_candidate", "state", "accepted_candidate",
        "false_authority", "no_abstention_false_authority", "intervention_nrmse", "model_disagreement",
        "rank_stability", "ood_score", "factual_rmse", "mean_false_credit_mass",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for chunk in chunks:
            decisions = {(d["seed"], d["family"]): d for d in chunk["decisions"]}
            for raw in chunk["raw_cases"]:
                decision = decisions[(raw["seed"], raw["family"])]
                writer.writerow({
                    "cohort": chunk["label"],
                    "seed": raw["seed"],
                    "family": raw["family"],
                    "true_causal_set": "|".join(raw["true_causal_set"]),
                    "provisional_candidate": raw["provisional_candidate"],
                    "state": decision["state"],
                    "accepted_candidate": decision["candidate"] or "",
                    "false_authority": decision["false_authority"],
                    "no_abstention_false_authority": raw["no_abstention_false_authority"],
                    "intervention_nrmse": raw["intervention_nrmse"],
                    "model_disagreement": raw["model_disagreement"],
                    "rank_stability": raw["rank_stability"],
                    "ood_score": raw["ood_score"],
                    "factual_rmse": raw["factual_rmse"],
                    "mean_false_credit_mass": raw["mean_false_credit_mass"],
                })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--replication", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    primary = load(args.primary)
    replication = load(args.replication)
    if primary["label"] != "PRIMARY" or replication["label"] != "INDEPENDENT_REPLICATION":
        raise RuntimeError("cohort labels mismatch")
    if primary["seed_start"] != 41000 or replication["seed_start"] != 51000:
        raise RuntimeError("frozen seed cohort mismatch")
    if primary["seed_count"] != 32 or replication["seed_count"] != 32:
        raise RuntimeError("frozen seed count mismatch")
    if primary["policy_sha256"] != replication["policy_sha256"]:
        raise RuntimeError("policy differs across confirmatory cohorts")
    policy_payload = load(args.policy)
    if policy_payload["sha256"] != primary["policy_sha256"]:
        raise RuntimeError("confirmatory policy differs from frozen registry policy")

    pass_all = bool(primary["pass"] and replication["pass"])
    result = {
        "experiment": "CSCA-02-UA Counterfactual Uncertainty & Abstention Qualification",
        "execution_mode": "fresh-process cohort isolation; mathematically identical run_cohort implementation",
        "policy_sha256": primary["policy_sha256"],
        "preregistration_sha256": sha256_file(ROOT / "experiments/csca_02_ua/PREREGISTRATION.md"),
        "common_implementation_sha256": sha256_file(ROOT / "experiments/csca_02_ua/common.py"),
        "primary_chunk_sha256": sha256_file(args.primary),
        "replication_chunk_sha256": sha256_file(args.replication),
        "primary": {"pass": primary["pass"], "failure_reasons": primary["failure_reasons"], **primary["score"]},
        "replication": {"pass": replication["pass"], "failure_reasons": replication["failure_reasons"], **replication["score"]},
        "scientific_pass": pass_all,
        "verdict": "UNCERTAINTY_AWARE_CREDIT_QUALIFIED" if pass_all else "UNCERTAINTY_MODEL_NOT_CAUSALLY_ADEQUATE",
        "authority": "UNCERTAINTY_QUALIFIED" if pass_all else "RESEARCH_ONLY",
        "shadow_inference_authorized": pass_all,
        "active_causal_control_authorized": False,
        "paper_reproduction_authority": False,
        "biological_mechanism_authority": False,
        "architecture_promotion_authority": False,
    }
    (args.out / "15_CSCA_02_RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_matrix(args.out / "16_STRUCTURAL_MISSPECIFICATION_MATRIX.csv", [primary, replication])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if pass_all else 3


if __name__ == "__main__":
    raise SystemExit(main())
