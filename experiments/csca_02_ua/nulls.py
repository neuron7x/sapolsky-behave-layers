from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cwc.counterfactual.adequacy import InterventionProbe, InterventionSupport
from cwc.counterfactual.model import CANDIDATES, fit_counterfactual_ensemble
from cwc.credit.estimator import estimate_credit_envelope
from cwc.inference.abstention import decide_causal_authority
from experiments.csca_02_ua.common import (
    EVAL_N,
    SUPPORT_N_PER_CANDIDATE,
    TRAIN_N,
    decide_raw,
    evaluate_raw_case,
    generate_case,
)
from experiments.csca_02_ua.run import load_policy


def _collinear_factual_wrong_counterfactual(seed: int, policy):
    """Factual C=A makes the forced wrong edge observationally invisible.

    The learned/faulted model can fit factual outcomes nearly as well as the noise floor,
    while do(C) remains structurally false. This directly attacks the invalid inference
    factual_fit_good => causal_model_good.
    """
    rng = random.Random(seed)
    train_rows = []
    train_y = []
    for _ in range(TRAIN_N):
        A = 1.0 if rng.random() < 0.5 else -1.0
        row = {
            "A": A,
            "C": A,  # exact observational collinearity
            "D": 1.0 if rng.random() < 0.5 else -1.0,
            "B": 1.0 if rng.random() < 0.5 else -1.0,
            "context": 1.0 if rng.random() < 0.5 else -1.0,
        }
        train_rows.append(row)
        train_y.append(A + rng.gauss(0.0, 0.15))
    eval_rows = []
    eval_y = []
    for _ in range(EVAL_N):
        A = 1.0 if rng.random() < 0.5 else -1.0
        row = {
            "A": A,
            "C": A,
            "D": 1.0 if rng.random() < 0.5 else -1.0,
            "B": 1.0 if rng.random() < 0.5 else -1.0,
            "context": 1.0 if rng.random() < 0.5 else -1.0,
        }
        eval_rows.append(row)
        eval_y.append(A + rng.gauss(0.0, 0.15))

    probes = []
    for candidate in CANDIDATES:
        for _ in range(SUPPORT_N_PER_CANDIDATE):
            A = 1.0 if rng.random() < 0.5 else -1.0
            base = {
                "A": A,
                "C": 1.0 if rng.random() < 0.5 else -1.0,
                "D": 1.0 if rng.random() < 0.5 else -1.0,
                "B": 1.0 if rng.random() < 0.5 else -1.0,
                "context": 1.0 if rng.random() < 0.5 else -1.0,
            }
            observed = 1.0 if candidate == "A" else 0.0
            probes.append(InterventionProbe(candidate, base, observed))
    support = InterventionSupport(tuple(probes))
    models = fit_counterfactual_ensemble(train_rows, train_y, seed=seed, fault="SHARED_SPURIOUS_EDGE", bootstraps_per_family=4)
    pred = np.mean(np.asarray([m.predict(eval_rows) for m in models]), axis=0)
    factual_rmse = float(np.sqrt(np.mean((pred - np.asarray(eval_y)) ** 2)))
    envelope = estimate_credit_envelope(
        models,
        eval_rows,
        support,
        data_version=hashlib.sha256(f"null7:{seed}".encode()).hexdigest(),
        factual_residual_sd=factual_rmse,
    )
    decision = decide_causal_authority(envelope, policy)
    return {
        "factual_rmse": factual_rmse,
        "provisional_candidate": envelope.provisional_candidate,
        "intervention_nrmse": envelope.intervention_nrmse,
        "model_disagreement": envelope.model_disagreement,
        "decision_state": decision.state,
        "decision_candidate": decision.candidate,
        "pass": decision.state != "ACCEPT_CAUSAL_CREDIT",
    }


def main() -> int:
    policy, policy_sha = load_policy(ROOT / "research/registry/13_ABSTENTION_POLICY.yaml")
    seeds = range(61000, 61016)

    zero = [evaluate_raw_case(generate_case(seed, "N0_ZERO_CAUSE")) for seed in seeds]
    zero_decisions = [decide_raw(raw, policy) for raw in zero]

    shared = [evaluate_raw_case(generate_case(seed, "M11_SHARED_MODEL_CLASS_MISSPECIFICATION")) for seed in seeds]
    shared_decisions = [decide_raw(raw, policy) for raw in shared]

    unseen = [evaluate_raw_case(generate_case(seed, "M7_SYNERGISTIC_CAUSES")) for seed in seeds]
    unseen_decisions = [decide_raw(raw, policy) for raw in unseen]

    confound = [evaluate_raw_case(generate_case(seed, "M9_LATENT_CONFOUNDER_SHIFT")) for seed in seeds]
    confound_decisions = [decide_raw(raw, policy) for raw in confound]

    # Mandatory support null: the same otherwise-valid case with support metadata reduced
    # below the frozen minimum must never be accepted.
    insufficient_raw = replace(evaluate_raw_case(generate_case(61000, "M0_CORRECT_STRUCTURE")), min_intervention_support=8)
    insufficient = decide_raw(insufficient_raw, policy)

    factual_wrong = _collinear_factual_wrong_counterfactual(61000, policy)

    # Post-confirmatory context-invariance attack. These are frozen held-out records;
    # no threshold is changed. A global ACCEPT when context_stability<1 means the current
    # authority object is too coarse for context-dependent causality.
    context_records = []
    for filename in ("primary_chunk.json", "independent_replication_chunk.json"):
        payload = json.loads((ROOT / "research/results/CSCA-02-UA-CHUNKS" / filename).read_text())
        raw_lookup = {(r["seed"], r["family"]): r for r in payload["raw_cases"]}
        for decision in payload["decisions"]:
            if decision["family"] != "M10_CONTEXT_DEPENDENT_CAUSALITY":
                continue
            raw = raw_lookup[(decision["seed"], decision["family"])]
            if decision["state"] == "ACCEPT_CAUSAL_CREDIT" and raw["context_stability"] < 1.0:
                context_records.append({
                    "cohort": payload["label"],
                    "seed": decision["seed"],
                    "candidate": decision["candidate"],
                    "context_stability": raw["context_stability"],
                })

    checks = {
        "NULL_01_ZERO_CAUSAL_EFFECT": {
            "accepted": sum(d.state == "ACCEPT_CAUSAL_CREDIT" for d in zero_decisions),
            "pass": all(d.state != "ACCEPT_CAUSAL_CREDIT" for d in zero_decisions),
        },
        "NULL_02_CORRELATION_ONLY_HIGH_ASSOC_ZERO_INTERVENTION": {
            "accepted": sum(d.state == "ACCEPT_CAUSAL_CREDIT" for d in zero_decisions),
            "pass": all(d.state != "ACCEPT_CAUSAL_CREDIT" for d in zero_decisions),
        },
        "NULL_03_DESTROYED_TRUE_LINK": {
            "proxy": "N0_ZERO_CAUSE",
            "pass": all(d.state == "FALSIFIED_NO_LEVERAGE" for d in zero_decisions),
        },
        "NULL_04_SPURIOUS_STRUCTURAL_EDGE": {
            "accepted": sum(d.state == "ACCEPT_CAUSAL_CREDIT" for d in shared_decisions),
            "pass": all(d.state != "ACCEPT_CAUSAL_CREDIT" for d in shared_decisions),
        },
        "NULL_05_COMMON_WRONG_STRUCTURE_ENTIRE_ENSEMBLE": {
            "accepted": sum(d.state == "ACCEPT_CAUSAL_CREDIT" for d in shared_decisions),
            "pass": all(d.state != "ACCEPT_CAUSAL_CREDIT" for d in shared_decisions),
        },
        "NULL_06_UNSEEN_CAUSAL_TOPOLOGY": {
            "accepted": sum(d.state == "ACCEPT_CAUSAL_CREDIT" for d in unseen_decisions),
            "false_authority": sum(d.state == "ACCEPT_CAUSAL_CREDIT" and d.candidate not in {"A", "B"} for d in unseen_decisions),
            "pass": all(not (d.state == "ACCEPT_CAUSAL_CREDIT" and d.candidate not in {"A", "B"}) for d in unseen_decisions),
        },
        "NULL_07_FACTUAL_FIT_GOOD_COUNTERFACTUAL_WRONG": factual_wrong,
        "NULL_08_LATENT_CONFOUNDER_SHIFT": {
            "accepted": sum(d.state == "ACCEPT_CAUSAL_CREDIT" for d in confound_decisions),
            "pass": all(d.state != "ACCEPT_CAUSAL_CREDIT" for d in confound_decisions),
        },
        "NULL_09_INSUFFICIENT_INTERVENTION_SUPPORT": {
            "state": insufficient.state,
            "pass": insufficient.state == "ABSTAIN_INSUFFICIENT_INTERVENTION_SUPPORT",
        },
        "NULL_10_CONTEXT_DEPENDENT_AUTHORITY": {
            "accepted_context_unstable_cases": context_records,
            "count": len(context_records),
            "pass": len(context_records) == 0,
            "interpretation": "A global causal candidate was accepted in cases where the top candidate changes across context strata; current policy does not gate context_stability.",
        },
    }
    all_pass = all(bool(item["pass"]) for item in checks.values())
    payload = {
        "experiment": "CSCA-02-UA mandatory post-confirmatory null attack suite",
        "policy_sha256": policy_sha,
        "seed_range": [61000, 61015],
        "checks": checks,
        "all_nulls_pass": all_pass,
        "verdict": "NULL_ATTACK_SUITE_PASS" if all_pass else "NULL_ATTACK_EXPOSED_UNRESOLVED_FAILURE",
        "promotion_authority": False,
        "note": "Post-confirmatory diagnostic; it cannot rescue or alter the frozen CSCA-02 verdict.",
    }
    out = ROOT / "research/results/CSCA-02-UA/NULL_ATTACKS.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if all_pass else 4


if __name__ == "__main__":
    raise SystemExit(main())
