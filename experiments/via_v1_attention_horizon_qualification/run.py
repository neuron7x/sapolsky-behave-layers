"""Execute the preregistered exact attention-horizon mechanism qualification."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

from cwc.causal.opportunity import (
    QualityComputeOutcome,
    opportunity_at_lambda,
    summarize_opportunity,
    validate_quality_compute_replay,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "via-v1-attention-horizon-qualification"

ACTIONS = {"short": 2, "full": 8}
SEQUENCE_LENGTH = 8


def _predict(prefix: tuple[int, ...], *, regime: str, horizon: int) -> tuple[int, int]:
    if regime == "local":
        target_index = len(prefix) - 1
    elif regime == "long":
        target_index = 0
    else:
        raise ValueError(regime)
    target = prefix[target_index]
    visible_start = len(prefix) - horizon
    prediction = target if target_index >= visible_start else 0
    return prediction, target


def build_rows() -> list[QualityComputeOutcome]:
    rows: list[QualityComputeOutcome] = []
    for regime in ("local", "long"):
        for bits in itertools.product((0, 1), repeat=SEQUENCE_LENGTH):
            unit_id = f"{regime}:" + "".join(map(str, bits))
            for action, horizon in ACTIONS.items():
                prediction, target = _predict(bits, regime=regime, horizon=horizon)
                rows.append(
                    QualityComputeOutcome(
                        unit_id=unit_id,
                        regime=regime,
                        action=action,
                        quality=float(prediction == target),
                        compute=float(horizon),
                    )
                )
    validate_quality_compute_replay(rows, actions=("short", "full"))
    return rows


def _regime_action_means(rows: list[QualityComputeOutcome]) -> dict[str, dict[str, dict[str, float]]]:
    out: dict[str, dict[str, dict[str, float]]] = {}
    for regime in ("local", "long"):
        out[regime] = {}
        for action in ("short", "full"):
            cell = [r for r in rows if r.regime == regime and r.action == action]
            out[regime][action] = {
                "quality": sum(r.quality for r in cell) / len(cell),
                "compute_proxy": sum(r.compute for r in cell) / len(cell),
                "n_units": len(cell),
            }
    return out


def _action_reversal(summary) -> bool:
    # Search only positive-lambda points with positive gross regime opportunity.
    rows = build_rows()
    for point in summary.points:
        lam = point.lambda_compute
        if lam <= 0.0 or point.regime_gap <= 1e-12:
            continue
        winners: dict[str, str] = {}
        for regime in ("local", "long"):
            scores = {}
            for action in ("short", "full"):
                cell = [r for r in rows if r.regime == regime and r.action == action]
                scores[action] = sum(r.quality - lam * r.compute for r in cell) / len(cell)
            winners[regime] = max(scores, key=lambda a: (scores[a], a))
        if len(set(winners.values())) > 1:
            return True
    return False


def main() -> int:
    rows = build_rows()
    summary = summarize_opportunity(rows, controller_compute=0.0, actions=("short", "full"))
    ordering_valid = all(
        p.fixed_value <= p.regime_oracle_value + 1e-12
        and p.regime_oracle_value <= p.instance_oracle_value + 1e-12
        for p in summary.points
    )
    reversal = _action_reversal(summary)
    checks = {
        "exhaustive_replay_valid": True,
        "information_ordering_valid": ordering_valid,
        "positive_regime_opportunity_interval": summary.positive_regime_interval_found,
        "positive_controller_compute_allowance": summary.max_controller_compute_allowance > 0.0,
        "action_ranking_reversal_across_regimes": reversal,
        "no_ascension_authority": True,
    }
    qualified = all(checks.values())
    verdict_name = (
        "ATTENTION_HORIZON_MECHANISM_QUALIFIED_CONTROL_ONLY"
        if qualified
        else "ATTENTION_HORIZON_MECHANISM_REJECTED"
    )

    payload = {
        "schema": "cwc-via-v1q/verdict-1",
        "verdict": verdict_name,
        "candidate_mechanism": "adaptive_attention_horizon",
        "scientific_pass": False,
        "ascension_authorized": False,
        "via_v2_authorized": False,
        "prospective_real_pilot_candidate": qualified,
        "resource_unit": "visible_symbol_count_controlled_proxy",
        "unit_count": len({r.unit_id for r in rows}),
        "action_count": len(summary.actions),
        "regime_action_means": _regime_action_means(rows),
        "critical_lambdas": list(summary.critical_lambdas),
        "sampled_lambdas": list(summary.sampled_lambdas),
        "max_regime_gap": summary.max_regime_gap,
        "max_instance_gap": summary.max_instance_gap,
        "max_controller_compute_allowance": summary.max_controller_compute_allowance,
        "checks": checks,
        "points": [
            {
                "lambda_compute": p.lambda_compute,
                "fixed_value": p.fixed_value,
                "regime_oracle_value": p.regime_oracle_value,
                "instance_oracle_value": p.instance_oracle_value,
                "regime_gap": p.regime_gap,
                "instance_gap": p.instance_gap,
                "regime_net_gap": p.regime_net_gap,
                "best_fixed_action": p.best_fixed_action,
            }
            for p in summary.points
        ],
        "scope_limit": (
            "controlled exact-enumeration mechanism qualification only; no trained-model, "
            "real-workload, GPU, latency, energy, or VIA ascension claim"
        ),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    verdict_path = OUT / "verdict.json"
    verdict_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(verdict_path.read_bytes()).hexdigest()
    (OUT / "SHA256SUMS").write_text(f"{digest}  verdict.json\n")

    print(json.dumps({
        "verdict": verdict_name,
        "max_regime_gap": summary.max_regime_gap,
        "max_controller_compute_allowance": summary.max_controller_compute_allowance,
        "critical_lambdas": list(summary.critical_lambdas),
    }, indent=2))
    return 0 if qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
