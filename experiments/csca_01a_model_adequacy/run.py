from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/csca-01a-model-adequacy"
BETA_HATS = (1.0, 0.5)
ALPHAS = (0.0, 0.1, 0.25, 0.5, 1.0, 1.25)


def model_y(*, A: int, C: int, beta_hat: float, alpha: float) -> float:
    return beta_hat * A + alpha * C


def exact_value(*, A: int, C: int, beta_hat: float, alpha: float, coalition: frozenset[str]) -> float:
    observed = model_y(A=A, C=C, beta_hat=beta_hat, alpha=alpha)
    names = tuple(sorted(coalition))
    total = 0.0
    count = 0
    for vals in itertools.product((-1, 1), repeat=len(names)):
        assignment = {"A": A, "C": C}
        assignment.update(dict(zip(names, vals, strict=True)))
        total += model_y(A=assignment["A"], C=assignment["C"], beta_hat=beta_hat, alpha=alpha)
        count += 1
    return observed - total / count


def shapley(*, A: int, C: int, beta_hat: float, alpha: float) -> dict[str, float]:
    empty = exact_value(A=A, C=C, beta_hat=beta_hat, alpha=alpha, coalition=frozenset())
    va = exact_value(A=A, C=C, beta_hat=beta_hat, alpha=alpha, coalition=frozenset({"A"}))
    vc = exact_value(A=A, C=C, beta_hat=beta_hat, alpha=alpha, coalition=frozenset({"C"}))
    vac = exact_value(A=A, C=C, beta_hat=beta_hat, alpha=alpha, coalition=frozenset({"A", "C"}))
    return {
        "A": 0.5 * ((va - empty) + (vac - vc)),
        "C": 0.5 * ((vc - empty) + (vac - va)),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    max_error = 0.0
    for beta_hat in BETA_HATS:
        for alpha in ALPHAS:
            abs_a = []
            abs_c = []
            for A, C in itertools.product((-1, 1), repeat=2):
                phi = shapley(A=A, C=C, beta_hat=beta_hat, alpha=alpha)
                abs_a.append(abs(phi["A"]))
                abs_c.append(abs(phi["C"]))
                max_error = max(max_error, abs(abs(phi["A"]) - abs(beta_hat)), abs(abs(phi["C"]) - abs(alpha)))
            mean_a = sum(abs_a) / len(abs_a)
            mean_c = sum(abs_c) / len(abs_c)
            denom = mean_a + mean_c
            false_mass = 0.0 if denom <= 1e-15 else mean_c / denom
            expected_false = 0.0 if abs(beta_hat) + abs(alpha) <= 1e-15 else abs(alpha) / (abs(beta_hat) + abs(alpha))
            max_error = max(max_error, abs(false_mass - expected_false))
            actual_relation = "C>A" if mean_c > mean_a + 1e-12 else "A>C" if mean_a > mean_c + 1e-12 else "TIE"
            expected_relation = "C>A" if abs(alpha) > abs(beta_hat) else "A>C" if abs(beta_hat) > abs(alpha) else "TIE"
            if actual_relation != expected_relation:
                max_error = float("inf")
            rows.append({
                "beta_hat": beta_hat,
                "alpha": alpha,
                "mean_abs_phi_A": mean_a,
                "mean_abs_phi_C": mean_c,
                "false_credit_mass": false_mass,
                "ranking": actual_relation,
                "expected_ranking": expected_relation,
            })
    passed = math.isfinite(max_error) and max_error <= 1e-12
    payload = {
        "experiment": "CSCA-01A counterfactual model adequacy attack",
        "rows": rows,
        "max_analytic_error": max_error,
        "primary_pass": passed,
        "verdict": "COUNTERFACTUAL_MODEL_ERROR_PROPAGATES_TO_CAUSAL_CREDIT" if passed else "CSCA_01A_ANALYTIC_IDENTITY_FAILED",
        "architecture_promotion_authority": False,
        "interpretation": "A correct Shapley operator cannot repair structural errors in the counterfactual model it receives.",
    }
    (OUT / "verdict.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
