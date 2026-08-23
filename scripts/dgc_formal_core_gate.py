from __future__ import annotations


def _prove(name, assumptions, conclusion, *, z3):
    solver = z3.Solver()
    solver.add(*assumptions)
    solver.add(z3.Not(conclusion))
    result = solver.check()
    if result != z3.unsat:
        model = solver.model() if result == z3.sat else None
        raise AssertionError(f"formal obligation {name} not proved: result={result} model={model}")
    print(f"FORMAL-PASS {name}")


def main() -> int:
    try:
        import z3
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "z3-solver is required; install dgc-formal-requirements.txt. "
            "Absence of the solver is FORMAL_EXECUTION_UNAVAILABLE, not PASS."
        ) from exc

    Real = z3.Real

    # F1 — reservation preserves the global budget invariant.
    spent, reserved, new_reservation, global_budget = map(
        Real, ["spent", "reserved", "new_reservation", "global_budget"]
    )
    _prove(
        "F1_RESERVATION_BUDGET_SAFETY",
        [
            spent >= 0,
            reserved >= 0,
            new_reservation >= 0,
            global_budget >= 0,
            spent + reserved <= global_budget,
            new_reservation <= global_budget - spent - reserved,
        ],
        spent + reserved + new_reservation <= global_budget,
        z3=z3,
    )

    # F2 — committing actual cost <= released reservation preserves budget safety.
    actual, released = map(Real, ["actual", "released"])
    _prove(
        "F2_COMMIT_BUDGET_SAFETY",
        [
            spent >= 0,
            reserved >= 0,
            global_budget >= 0,
            spent + reserved <= global_budget,
            actual >= 0,
            released >= 0,
            actual <= released,
            released <= reserved,
        ],
        (spent + actual) + (reserved - released) <= global_budget,
        z3=z3,
    )

    # F3 — lease expiry can only reduce reserved budget.
    _prove(
        "F3_EXPIRY_BUDGET_SAFETY",
        [
            spent >= 0,
            reserved >= 0,
            global_budget >= 0,
            spent + reserved <= global_budget,
            released >= 0,
            released <= reserved,
        ],
        spent + (reserved - released) <= global_budget,
        z3=z3,
    )

    # F4 — positive robust VOC lower bound implies nominal gain exceeds all declared penalties.
    gain_lower, cost, ambiguity_penalty, eta, kappa = map(
        Real, ["gain_lower", "cost", "ambiguity_penalty", "eta", "kappa"]
    )
    robust_lower = gain_lower - cost - ambiguity_penalty - 2 * eta - kappa
    _prove(
        "F4_ROBUST_VOC_ADMISSION_IMPLICATION",
        [
            cost >= 0,
            ambiguity_penalty >= 0,
            eta >= 0,
            kappa >= 0,
            robust_lower > 0,
        ],
        gain_lower > cost + ambiguity_penalty + 2 * eta + kappa,
        z3=z3,
    )

    # F5 — a Pareto gate can only authorize when every declared lower-bound condition holds.
    cost_gain_lcb, quality_gain_lcb, regret_gain_lcb, dq, dr = map(
        Real,
        ["cost_gain_lcb", "quality_gain_lcb", "regret_gain_lcb", "dq", "dr"],
    )
    authorized = z3.And(
        cost_gain_lcb > 0,
        quality_gain_lcb >= -dq,
        regret_gain_lcb >= -dr,
        dq >= 0,
        dr >= 0,
    )
    _prove(
        "F5_PARETO_AUTHORITY_CONJUNCTION",
        [authorized],
        z3.And(
            cost_gain_lcb > 0,
            quality_gain_lcb >= -dq,
            regret_gain_lcb >= -dr,
        ),
        z3=z3,
    )

    print(f"DGC-FORMAL-CORE: PASS solver=Z3-{z3.get_version_string()} obligations=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
