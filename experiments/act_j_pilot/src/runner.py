"""Run the Act-J pilot and write an evidence bundle.

Trains the neural controller across a beta sweep and multiple seeds for a regular and
a critical problem, checks each converged (I, V) against the analytic V*(I), and
records the worst gap plus the phase-transition signature (critical routes even at a
high information price; regular does not).

Usage:
  PYTHONPATH=. python experiments/act_j_pilot/src/runner.py --out artifacts/act-j-pilot
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import random

from experiments.act_j_pilot.src.act_j_pilot import compare_to_theory, train_controller
from experiments.common.value_of_information_rate import optimal_value_at_rate_ri

REGULAR = [[1.0, 0.0], [0.0, 0.5]]    # unique prior optimum (margin 0.25)
CRITICAL = [[1.0, 0.0], [0.0, 1.0]]   # two actions tie -> indifference
PRIOR = [0.5, 0.5]
BETAS = [3.0, 1.0, 0.3, 0.1]
SEEDS = [0, 1, 2]


def run() -> dict[str, object]:
    results: dict[str, object] = {"betas": BETAS, "seeds": SEEDS}
    worst_gap = 0.0
    for name, u in (("regular", REGULAR), ("critical", CRITICAL)):
        rows_all = []
        for s in SEEDS:
            rows = compare_to_theory(u, PRIOR, BETAS, steps=4000, seed=s)
            rows_all.append(rows)
            worst_gap = max(worst_gap, max(abs(float(r["gap_to_theory"])) for r in rows))
        results[name] = rows_all

    # phase-transition signature at the highest information price (beta = max BETAS)
    reg_hi = train_controller(REGULAR, PRIOR, max(BETAS), steps=4000, seed=0)
    crit_hi = train_controller(CRITICAL, PRIOR, max(BETAS), steps=4000, seed=0)
    phase = {
        "beta": max(BETAS),
        "regular_value_at_high_price": reg_hi.value,
        "regular_information": reg_hi.information_nats,
        "critical_value_at_high_price": crit_hi.value,
        "critical_information": crit_hi.information_nats,
        "critical_routes_regular_does_not": crit_hi.value > 10.0 * reg_hi.value + 1e-3,
    }
    results["phase_transition"] = phase

    # scaling: random larger problems (|C|,|A| > 2) must also land on V*(I)
    scaling = []
    for k, a, sd in ((4, 3, 11), (6, 4, 7), (8, 5, 3)):
        rng = random.Random(sd)
        u = [[rng.uniform(-1.0, 1.0) for _ in range(a)] for _ in range(k)]
        p = [1.0 / k] * k
        res = train_controller(u, p, beta=0.3, steps=5000, seed=0)
        v_star = optimal_value_at_rate_ri(u, res.information_nats, p)
        gap = abs(res.value - v_star)
        worst_gap = max(worst_gap, gap)
        scaling.append({"n_contexts": k, "n_actions": a, "information": res.information_nats,
                        "trained_value": res.value, "theory_v_star": v_star, "gap": gap})
    results["scaling"] = scaling
    results["worst_gap_to_theory"] = worst_gap
    results["verdict"] = (
        "TRAINED_CONTROLLER_REALISES_V_STAR"
        if worst_gap < 0.02 and bool(phase["critical_routes_regular_does_not"])
        else "MISMATCH"
    )
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="artifacts/act-j-pilot")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results = run()
    (out / "RESULTS.json").write_text(json.dumps(results, indent=2))
    print(f"verdict: {results['verdict']}  worst_gap={results['worst_gap_to_theory']:.4f}")
    ph = results["phase_transition"]
    assert isinstance(ph, dict)
    print(f"phase transition @ beta={ph['beta']}: "
          f"regular V={ph['regular_value_at_high_price']:.4f} (I={ph['regular_information']:.4f})  "
          f"critical V={ph['critical_value_at_high_price']:.4f} (I={ph['critical_information']:.4f})")


if __name__ == "__main__":
    main()
