from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def expected_policy_value(*, true_p_b: float, believed_p_b: float, loss_b: float, cost: float) -> dict[str, float | bool]:
    """Two-world misspecification attack with action A as the believed baseline.

    B0 buys a perfect diagnostic. DGC buys iff believed expected regret exceeds cost.
    Evaluation uses the true world probability, which is unavailable to the governor.
    """
    dgc_buy = believed_p_b * loss_b > cost
    dgc_value = -cost if dgc_buy else -(true_p_b * loss_b)
    b0_value = -cost
    return {
        "dgc_buy": dgc_buy,
        "dgc_expected_value": dgc_value,
        "b0_expected_value": b0_value,
        "dgc_minus_b0": dgc_value - b0_value,
    }


def find_counterexample() -> dict[str, float | bool] | None:
    for true_p in (0.05, 0.10, 0.20, 0.30):
        for believed_p in (0.005, 0.01, 0.02, 0.05):
            for loss_b in (0.5, 1.0, 1.5):
                for cost in (0.02, 0.05, 0.10):
                    out = expected_policy_value(
                        true_p_b=true_p,
                        believed_p_b=believed_p,
                        loss_b=loss_b,
                        cost=cost,
                    )
                    if float(out["dgc_minus_b0"]) < 0:
                        return {
                            "true_p_b": true_p,
                            "believed_p_b": believed_p,
                            "loss_b": loss_b,
                            "cost": cost,
                            **out,
                        }
    return None


def main() -> int:
    result = find_counterexample()
    outdir = ROOT / "artifacts/dgc-01-falsification"
    outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "COUNTEREXAMPLE_FOUND" if result else "NO_COUNTEREXAMPLE_IN_GRID",
        "claim_scope_effect": "DGC optimality requires a valid decision model; misspecified belief can make DGC worse than fixed compute.",
        "counterexample": result,
        "promotion_effect": "NONE_NEGATIVE_BOUNDARY_ONLY",
    }
    path = outdir / "verdict.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (outdir / "SHA256SUMS").write_text(f"{digest}  verdict.json\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())
