from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from cwc.governance.sequential import (
    SamplingMode,
    SequentialSamplingContract,
    stitched_hoeffding_confidence_sequence,
)


def mean(values: Iterable[float]) -> float:
    vv = tuple(values)
    return sum(vv) / len(vv) if vv else float("nan")


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    by_policy: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_policy[str(row["policy"])].append(row)

    policies: dict[str, object] = {}
    for policy, rr in sorted(by_policy.items()):
        payload = {
            "n": len(rr),
            "mean_net_decision_value": mean(float(r["score"]) for r in rr),
            "compute_rate": mean(1.0 if r["buy_diagnostic"] else 0.0 for r in rr),
            "decision_error_rate": mean(1.0 if float(r["decision_loss"]) > 0 else 0.0 for r in rr),
            "mean_compute_cost": mean(float(r["compute_cost"]) for r in rr),
        }
        if policy == "B3_DGC":
            payload["oracle_routing_agreement"] = mean(
                1.0 if bool(r["buy_diagnostic"]) == bool(r["oracle_should_compute"]) else 0.0 for r in rr
            )
            payload["false_stop_rate"] = mean(
                1.0 if (not bool(r["buy_diagnostic"]) and bool(r["oracle_should_compute"])) else 0.0 for r in rr
            )
            payload["false_escalation_rate"] = mean(
                1.0 if (bool(r["buy_diagnostic"]) and not bool(r["oracle_should_compute"])) else 0.0 for r in rr
            )
        policies[policy] = payload

    dgc = {str(r["task_id"]): float(r["score"]) for r in by_policy["B3_DGC"]}
    comparisons: dict[str, object] = {}
    # Frozen support bounds derived from workloads.py, not observed outcomes.
    # B0 always computes; DGC differs only by stopping in same-action A/D, so
    # DGC-B0 is in [0, max(A/D diagnostic cost)=0.12]. B1/B2 can disagree in E,
    # where the worst paired bounds are [-max_cost, max_loss_b-min_cost].
    support_bounds = {
        "B0_FIXED": (0.0, 0.12),
        "B1_UNCERTAINTY": (-0.06, 1.545),
        "B2_COST_QUALITY_ROUTER": (-0.06, 1.545),
    }
    for baseline in ("B0_FIXED", "B1_UNCERTAINTY", "B2_COST_QUALITY_ROUTER"):
        base = {str(r["task_id"]): float(r["score"]) for r in by_policy[baseline]}
        diffs = [dgc[k] - base[k] for k in sorted(dgc)]
        lo, hi = support_bounds[baseline]
        contract = SequentialSamplingContract(
            SamplingMode.IID_BOUNDED, lo, hi, 0.05, f"DGC-DEV-PAIRED-CS-{baseline}-V1"
        )
        cs = stitched_hoeffding_confidence_sequence(diffs, contract=contract)
        comparisons[baseline] = {
            "paired_mean_delta_dgc_minus_baseline": cs.mean,
            "anytime_cs_lower": cs.lower,
            "anytime_cs_upper": cs.upper,
            "n": cs.n,
            "method": cs.method,
            "development_only": True,
        }
    return {"policies": policies, "comparisons": comparisons}
