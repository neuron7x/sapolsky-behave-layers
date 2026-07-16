"""Mathematical theory of adaptive-mechanism identifiability, verified against
the CWC experiments. Reproduces the note in docs/IDENTIFIABILITY_THEORY.md.

Object: a utility matrix U[context c, choice a], optional cost K[a], budget κ
(max fraction of the population that may take an expensive choice). We study the
oracle gap G = V_oracle − V_fixed and prove it is governed by the context×choice
INTERACTION under the operating budget.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def decompose(U: list[list[float]], p: list[float] | None = None) -> dict:
    """2-way (weighted-over-contexts, uniform-over-choices) ANOVA of U and the
    unconstrained oracle gap. Returns the exact gap formula terms."""
    m, n = len(U), len(U[0])
    if p is None:
        p = [1.0 / m] * m
    mu = sum(p[c] * U[c][a] for c in range(m) for a in range(n)) / n
    beta = [sum(p[c] * U[c][a] for c in range(m)) - mu for a in range(n)]
    alpha = [sum(U[c][a] for a in range(n)) / n - mu for c in range(m)]
    gamma = [[U[c][a] - mu - alpha[c] - beta[a] for a in range(n)] for c in range(m)]
    v_oracle = sum(p[c] * max(U[c]) for c in range(m))
    v_fixed = max(sum(p[c] * U[c][a] for c in range(m)) for a in range(n))
    gap = v_oracle - v_fixed
    gap_formula = sum(p[c] * max(beta[a] + gamma[c][a] for a in range(n)) for c in range(m)) - max(beta)
    gamma_rms = math.sqrt(sum(p[c] * gamma[c][a] ** 2 for c in range(m) for a in range(n)) / n)
    beta_spread = max(beta) - min(beta)
    ctx_argmax = [max(range(n), key=lambda a: U[c][a]) for c in range(m)]
    return {"gap": gap, "gap_formula": gap_formula, "beta": beta, "gamma_rms": gamma_rms,
            "beta_spread": beta_spread, "quality_dominant_choice": len(set(ctx_argmax)) == 1,
            "per_context_argmax": ctx_argmax}


def constrained_gap(Q: list[list[float]], cheap: int, expensive: int,
                    p_context: list[float], kappa: float) -> dict:
    """Budget-constrained oracle gap. Two choices: `cheap` (cost 0) and
    `expensive` (cost 1). At most fraction κ of the population may take the
    expensive choice. Oracle sees context; fixed policy is context-blind.

    Oracle: spend the κ budget on the contexts with the largest quality gain
    Δ_c = Q[c,expensive] − Q[c,cheap], largest first.
    Best context-blind policy: either all-cheap, or expensive to a random κ.
    """
    m = len(Q)
    gains = sorted(range(m), key=lambda c: Q[c][expensive] - Q[c][cheap], reverse=True)
    # oracle: fill budget with highest-gain contexts (fractional knapsack)
    budget = kappa
    v_oracle = sum(p_context[c] * Q[c][cheap] for c in range(m))
    for c in gains:
        take = min(p_context[c], budget)
        v_oracle += take * max(0.0, Q[c][expensive] - Q[c][cheap])
        budget -= take
        if budget <= 1e-12:
            break
    # context-blind best: all-cheap vs κ-random-expensive
    v_all_cheap = sum(p_context[c] * Q[c][cheap] for c in range(m))
    # random κ expensive: each context gets expensive with prob κ
    v_rand = sum(p_context[c] * ((1 - kappa) * Q[c][cheap] + kappa * Q[c][expensive]) for c in range(m))
    v_fixed = max(v_all_cheap, v_rand)
    return {"v_oracle": v_oracle, "v_fixed": v_fixed, "constrained_gap": v_oracle - v_fixed,
            "v_all_cheap": v_all_cheap, "v_random_kappa": v_rand}


def main() -> None:
    out: dict = {}

    # 1) PLASTICITY — real data, unconstrained (utility already = quality−retention)
    runs = [json.loads((ROOT / f"artifacts/wp3-plasticity-v1/oracle-gap/raw_runs/seed{s}.json").read_text())
            for s in range(5)]
    allocs = ["attn", "mlp", "head", "embed"]
    tasks = ["lexical", "relational"]
    U_plast = [[sum(r["tasks"][t][a]["utility"] for r in runs) / len(runs) for a in allocs] for t in tasks]
    out["plasticity"] = decompose(U_plast)
    out["plasticity"]["explanation"] = ("gap~0: attention has the largest choice main-effect (beta) and its "
                                        "interaction is never overtaken -> weak-interaction collapse regime.")

    # 2) ROUTING v2 — quality only (unconstrained) vs budget-constrained
    Q_route = [[1.00, 1.00],    # EASY: direct, semantic
               [0.004, 1.00]]   # HARD: direct, semantic
    out["routing_unconstrained"] = decompose(Q_route)
    out["routing_unconstrained"]["explanation"] = ("gap=0 on quality alone: the semantic path dominates "
                                                   "(solves EASY and HARD) -> quality-dominance collapse.")
    out["routing_budget_kappa_0.5"] = constrained_gap(Q_route, cheap=0, expensive=1,
                                                      p_context=[0.5, 0.5], kappa=0.5)
    out["routing_budget_kappa_0.5"]["explanation"] = ("gap>0: the 50% budget forbids the dominant semantic "
                                                      "path everywhere; the oracle spends it on HARD. This is "
                                                      "why routing v2 was identifiable — cost, not quality.")

    # 2b) PLASTICITY REVISITED under a parameter-COST budget (the AMG premise).
    # utility_λ(task, group) = new_acc − λ·(params/params_max). Post-hoc λ sweep.
    Kg = {a: runs[0]["tasks"]["lexical"][a]["cost_params"] for a in allocs}
    kmax = max(Kg.values())
    acc = {t: {a: sum(r["tasks"][t][a]["new_acc"] for r in runs) / len(runs) for a in allocs} for t in tasks}
    sweep = {}
    for lam in (0.0, 0.5, 1.0, 2.0):
        Ul = [[acc[t][a] - lam * Kg[a] / kmax for a in allocs] for t in tasks]
        d = decompose(Ul)
        oc = {t: allocs[max(range(len(allocs)), key=lambda a: Ul[ti][a])] for ti, t in enumerate(tasks)}
        # per-seed gaps for robustness
        per_seed = []
        for r in runs:
            Us = [[r["tasks"][t][a]["new_acc"] - lam * Kg[a] / kmax for a in allocs] for t in tasks]
            vo = sum(max(row) for row in Us) / len(tasks)
            vf = max(sum(Us[ti][a] for ti in range(len(tasks))) / len(tasks) for a in range(len(allocs)))
            per_seed.append(vo - vf)
        sweep[f"lambda_{lam}"] = {"gap": d["gap"], "oracle_choice": oc,
                                  "per_seed_gaps": per_seed, "min_seed_gap": min(per_seed)}
    out["plasticity_cost_budget_sweep"] = sweep
    out["plasticity_cost_budget_note"] = (
        "REVIVAL: the original λ=0 gap is ~0, but for λ∈[0.5,1.0] the cost-weighted oracle allocates the CHEAP "
        "'head' group to lexical (which it can solve) and reserves the expensive 'attn' only for relational "
        "(structurally necessary) — beating any fixed group. gap≈0.19 at λ=1, identical across all 5 seeds. "
        "EPISTEMIC STATUS: EXPLORATORY (λ chosen post-hoc). Generates a preregisterable hypothesis; requires a "
        "fresh confirmatory run with a cost-aware oracle objective and λ frozen before execution.")

    # 3) POSITIVE CONTROL — anti-dominant specialization
    out["ideal_specialized"] = decompose([[1.0, 0.0], [0.0, 1.0]])

    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "artifacts/identifiability_theory.json").write_text(json.dumps(out, indent=2))
    pl = out["plasticity"]
    ratio = pl["gamma_rms"] / (pl["beta_spread"] + 1e-9)
    print("PLASTICITY unconstrained gap      =", round(pl["gap"], 4),
          "| quality-dominant?", pl["quality_dominant_choice"],
          "| gamma_rms/beta_spread =", round(ratio, 3))
    print("ROUTING quality-only gap          =", round(out["routing_unconstrained"]["gap"], 4),
          "| quality-dominant?", out["routing_unconstrained"]["quality_dominant_choice"])
    print("ROUTING budget-constrained gap    =", round(out["routing_budget_kappa_0.5"]["constrained_gap"], 4),
          "  (oracle", round(out["routing_budget_kappa_0.5"]["v_oracle"], 3),
          "vs fixed", round(out["routing_budget_kappa_0.5"]["v_fixed"], 3), ")")
    print("IDEAL specialized gap             =", round(out["ideal_specialized"]["gap"], 4))


if __name__ == "__main__":
    main()
