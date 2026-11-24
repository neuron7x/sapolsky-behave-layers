"""Prospective minimal-sample diagnostic and complete G evidence report."""
from __future__ import annotations

from decimal import Decimal as D, localcontext
from fractions import Fraction as F

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06g import gauge as g

TAU = F(110)
TAU_SHIFT = F(1, 1024)
FIXED_NMDA_SHIFT = F(1, 1024)
FIVE = (0, 3, 18, 60, 120)
SIX = (0, 3, 18, 30, 60, 120)
EXTRA = 7
SCOPE = "UNCLIPPED_NOISELESS_TRACE_NO_SAMPLE_SPECIFIC_JITTER_ONLY"
QUALIFIED = "PASS_CONDITIONAL_JOINT_GAUGE_THEOREM_ONLY"


def solve(matrix, rhs):
    """Independent pivoted Decimal diagnostic, never an exact rank proof."""
    n = len(matrix)
    a.need(n > 0 and len(rhs) == n and all(len(row) == n for row in matrix),
           "interpolation dimension")
    rows = [list(row)+[value] for row, value in zip(matrix, rhs, strict=True)]
    for i in range(n):
        j = max(range(i, n), key=lambda k: abs(rows[k][i]))
        a.need(rows[j][i] != 0, "singular diagnostic matrix")
        rows[i], rows[j] = rows[j], rows[i]
        pivot = rows[i][i]
        rows[i] = [x/pivot for x in rows[i]]
        for j in range(n):
            if j != i:
                factor = rows[j][i]
                rows[j] = [x-factor*y for x, y in zip(rows[j], rows[i], strict=True)]
    return tuple(row[-1] for row in rows)


def value(coeff, tau, t):
    return sum((x*y for x, y in zip(coeff, g.trace_basis(t, tau), strict=True)), D(0))


def baseline():
    # Known g=1, gamma=3/2, delta=1/2, b=d=0 and all x=1/2.
    delay = D("0.5")
    return (g.c0(), D(0), -D(1)/3*(-delay/200).exp(),
            D("0.5")*(-delay*2/5).exp(),
            D("0.75")*(-delay/g.dec(TAU)).exp(),
            D("0.5")*(-delay/6).exp())


def physical(coeff, tau):
    delay = D("0.5")
    c, drift, w, aa, nn, hh = coeff
    x = (D(5)/6+w*(delay/200).exp(), aa*(delay*2/5).exp(),
         nn*(delay/g.dec(tau)).exp()/D("1.5"), hh*(delay/6).exp())
    b = c-g.c0()
    a.need(all(0 < z < 1 for z in x) and -16 < b < 16 and -1 < drift < 1,
           "diagnostic lift not strictly interior")
    return {"x": [a.q(F(z)) for z in x], "offset_pA": a.q(F(b)),
            "drift_pA": a.q(F(drift)), "gain": "1/1",
            "gamma": "3/2", "delay_ms": "1/2", "tau_ms": a.q(tau)}


def sample_witness(unknown_tau):
    with localcontext() as context:
        context.prec = 120
        original = baseline()
        times = SIX if unknown_tau else FIVE
        tau = TAU+TAU_SHIFT if unknown_tau else TAU
        target = [value(original, TAU, t) for t in times]
        matrix = [g.trace_basis(t, tau) for t in times]
        if unknown_tau:
            alternate = solve(matrix, target)
        else:
            fixed = original[4]+g.dec(FIXED_NMDA_SHIFT)
            columns = (0, 1, 2, 3, 5)
            fitted = solve([[row[j] for j in columns] for row in matrix],
                           [y-row[4]*fixed for row, y in zip(matrix, target, strict=True)])
            by_column = dict(zip(columns, fitted, strict=True))
            alternate = tuple(fixed if j == 4 else by_column[j] for j in range(6))
        first, second = physical(original, TAU), physical(alternate, tau)
        residuals = [abs(value(alternate, tau, t)-y)
                     for t, y in zip(times, target, strict=True)]
        extra_residual = abs(value(alternate, tau, EXTRA)-value(original, TAU, EXTRA))
        a.need(max(residuals) <= D("1e-90"), "interpolation residual threshold")
        a.need(extra_residual > D("1e-12"), "extra sample fails discrimination threshold")
        return {"scope": "NUMERICAL_CORROBORATION_NOT_EXACT_PROOF",
                "kind": "UNKNOWN_TAU_SIX_ALIAS" if unknown_tau else "FIXED_TAU_FIVE_ALIAS",
                "matched_times_ms": list(times), "extra_time_ms": EXTRA,
                "left": first, "right": second,
                "left_coefficients": [a.q(F(x)) for x in original],
                "right_coefficients": [a.q(F(x)) for x in alternate],
                "matched_absolute_residuals_pA": [a.q(F(x)) for x in residuals],
                "extra_absolute_residual_pA": a.q(F(extra_residual))}


def theorem():
    return {"scope": SCOPE,
            "exact_effective_quotient": ["V", "A0", "A1", "u_w", "u_A", "u_N", "u_G", "active_tau"],
            "fixed_tau_minimal_distinct_samples": 6,
            "unknown_active_tau_minimal_distinct_samples": 7,
            "silent_tau_identified": False,
            "proof": "EXPONENTIAL_POLYNOMIAL_ZERO_BOUND_AND_INTERIOR_LINEAR_FIBER",
            "noisy_or_jittered_minimal_count": "NOT_ESTABLISHED"}


def negative_controls():
    active, silent = g.ANCHORS
    v, zero = F(-71), F(0)
    controls = {}

    def reject(name, operation):
        try:
            operation()
        except ValueError:
            controls[name] = "REJECTED"
        else:
            raise ValueError("negative control escaped: "+name)

    reject("FLOAT_GAIN", lambda: g.lift(active, 1.0, F(1), zero, TAU))
    reject("GAIN_OUTSIDE", lambda: g.lift(active, F(2), F(1), zero, TAU))
    reject("GAMMA_OUTSIDE", lambda: g.lift(active, F(1), F(3), zero, TAU))
    reject("DELAY_OUTSIDE", lambda: g.lift(active, F(1), F(1), F(-1), TAU))
    reject("TAU_OUTSIDE", lambda: g.lift(active, F(1), F(1), zero, F(200)))
    reject("VOLTAGE_OUTSIDE", lambda: g.key(F(-60), zero, zero, active, TAU))
    reject("DRIFT_OUTSIDE", lambda: g.key(v, zero, F(2), active, TAU))
    reject("NEGATIVE_CONDUCTANCE", lambda: g.key(v, zero, zero, (zero, F(-1), zero, zero), TAU))
    reject("MALFORMED_KEY", lambda: g.key(v, zero, zero, (zero,), TAU))
    reject("UNKNOWN_WITNESS", lambda: g.finite_witness("UNREGISTERED"))
    reject("INVALID_SAMPLE_TIME", lambda: g.interval_current(4, (zero,)*4, F(1), F(1), zero, TAU, zero))
    reject("INFEASIBLE_LIFT", lambda: g.lift((zero, F(2), zero, zero), F(1), F(1), zero, TAU))
    k = g.key(v, zero, zero, active, TAU)
    for name, candidate in (
            ("OFFSET_DISTINCT", g.key(v, F(1), zero, active, TAU)),
            ("DRIFT_DISTINCT", g.key(v, zero, F(1), active, TAU)),
            ("ACTIVE_TAU_DISTINCT", g.key(v, zero, zero, active, TAU+1)),
            ("VOLTAGE_DISTINCT", g.key(v+1, zero, zero, active, TAU))):
        a.need(candidate != k, "key collision: "+name)
        controls[name] = "DISTINCT"
    a.need(g.key(v, zero, zero, silent, TAU) == g.key(v, zero, zero, silent, TAU+1),
           "silent tau alias lost")
    controls["SILENT_TAU_EQUIVALENT"] = "EQUIVALENT"
    a.need(len(controls) == 17, "negative control roster")
    return controls


def report():
    stages = {
        "sharp_certificate": g.sharp_certificate,
        "finite_witnesses": lambda: [g.finite_witness(name) for name in ("ZERO_DELAY", "SHARP_DELAY")],
        "minimal_samples": theorem,
        "sample_witnesses": lambda: [sample_witness(False), sample_witness(True)],
        "panel": g.panel,
        "negative_controls": negative_controls,
    }
    results, failures = {}, []
    for name, fn in stages.items():
        try:
            results[name] = fn()
        except Exception as exc:
            failures.append({"stage": name, "error_type": type(exc).__name__, "error": str(exc)})
    return {"experiment": "CNEH-EXP-06G", "scope": SCOPE,
            "qualification": "FAIL_ENGINEERING_GATE" if failures else QUALIFIED,
            "noiseless_latent_identifiability": "FAIL_COUNTEREXAMPLE" if
                "finite_witnesses" in results else "NOT_QUALIFIED",
            "failures": failures, **results, **g.NEGATIVE}
