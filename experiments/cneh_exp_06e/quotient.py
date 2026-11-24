"""Exact observation quotient for the frozen hypothetical C/D clamp.

The analytic theorem is in PROTOCOL.md. Numerical fixtures are diagnostics,
not a substitute for the proof or an authorization to act.
"""
from __future__ import annotations

from decimal import Decimal as D, localcontext
from fractions import Fraction as F
import itertools

from experiments.cneh_exp_06c import algebra as a, fixtures

ANCHORS = (
    (F(-1, 3), F(1, 4), F(1, 4), F(1, 4)),
    (F(-1, 3), F(1, 4), F(0), F(1, 4)),
)
VOLTAGE = F(-71)
TOLERANCE = F(1, 10**75)
GAIN = (F(1), F(3, 2), F(2))
DELAY = (F(0), F(1, 2), F(1))
TAU = (F(100), F(110), F(120))
CENTER = F(5, 6)


def validate_anchor(z):
    a.need(type(z) is tuple and len(z) == 4 and all(type(v) is F for v in z),
           "effective state must be four exact rationals")
    a.need(-CENTER <= z[0] <= 1-CENTER and 0 <= z[1] <= 1
           and 0 <= z[2] <= 2 and 0 <= z[3] <= 1, "effective state domain")


def validate_nuisance(gamma, delay, tau):
    a.need(all(type(v) is F for v in (gamma, delay, tau)),
           "nuisance must be exact rationals")
    a.need(1 <= gamma <= 2 and 0 <= delay <= 1 and 100 <= tau <= 120,
           "nuisance domain")


def quotient_key(voltage, z, tau):
    """Canonical key in effective coordinates, not an inverse from observations."""
    validate_anchor(z)
    validate_nuisance(F(1), F(0), tau)
    a.need(type(voltage) is F and -74 <= voltage <= -68, "voltage domain")
    return (voltage, *z, tau if z[2] != 0 else None)


def exp_box(lo, hi):
    a.need(type(lo) is F and type(hi) is F and lo <= hi, "exponential domain")
    return a.exponential(lo)[0], a.exponential(hi)[1]


def lift_box(z, gain, delay, tau):
    """Outward enclosure of the lifted state for a rectangular nuisance box."""
    validate_anchor(z)
    for g, d, t in itertools.product(gain, delay, tau):
        validate_nuisance(g, d, t)
    a.need(all(lo <= hi for lo, hi in (gain, delay, tau)), "reversed box")
    ew = exp_box(delay[0]/200, delay[1]/200)
    ea = exp_box(delay[0]/F(5, 2), delay[1]/F(5, 2))
    en = exp_box(delay[0]/tau[1], delay[1]/tau[0])
    eg = exp_box(delay[0]/6, delay[1]/6)
    return (
        a.add(a.point(CENTER), a.mul(a.point(z[0]), ew)),
        a.mul(a.point(z[1]), ea),
        a.div(a.mul(a.point(z[2]), en), gain),
        a.mul(a.point(z[3]), eg),
    )


def family_certificate(z):
    bounds = lift_box(z, (GAIN[0], GAIN[-1]), (DELAY[0], DELAY[-1]),
                      (TAU[0], TAU[-1]))
    a.need(all(0 <= lo <= hi <= 1 for lo, hi in bounds),
           "lift family not certified inside physical prior")
    return bounds


def decimal_lift(z, gamma, delay, tau):
    """Numerical diagnostic, independently evaluated at 90 decimal digits."""
    validate_anchor(z)
    validate_nuisance(gamma, delay, tau)
    with localcontext() as ctx:
        ctx.prec = 90
        zw, za, zn, zg = map(fixtures.decimal, z)
        g, d, tn = map(fixtures.decimal, (gamma, delay, tau))
        return tuple(map(F, (
            D(5)/6+zw*(d/200).exp(),
            za*(d/D("2.5")).exp(),
            zn*(d/tn).exp()/g,
            zg*(d/6).exp(),
        )))


def quotient_current(t, z, tau):
    """Independent direct expression of the quotient trace."""
    with localcontext() as ctx:
        ctx.prec = 90
        zw, za, zn, zg = map(fixtures.decimal, z)
        tn = fixtures.decimal(tau)
        dt = D(t)
        block = 1/(1+D("3.72").exp()/D("3.57"))
        value = (120-20*D("-2.5").exp()+24*zw*(-dt/200).exp()
                 -6*za*(-dt/D("2.5")).exp()-6*block*zn*(-dt/tn).exp()
                 +5*zg*(-dt/6).exp())
        return F(value)


def encode_key(key):
    return [None if v is None else a.q(v) for v in key]


def graph_support():
    rows = [{"past_mode": old, "future_mode": new}
            for old, new in itertools.product(range(4), repeat=2)]
    support = {str(old): [r["future_mode"] for r in rows if r["past_mode"] == old]
               for old in range(4)}
    a.need(len(rows) == 16 and all(v == [0, 1, 2, 3] for v in support.values()),
           "unrestricted transition roster")
    return {"pairs": rows, "future_support_by_past_mode": support,
            "assumption": "UNRESTRICTED_ACTION_TIME_SWITCHING"}


def negative_controls():
    base = ANCHORS[0]
    key = quotient_key(VOLTAGE, base, F(100))
    checks = {}

    def reject(label, call):
        try:
            call()
        except ValueError:
            checks[label] = "REJECTED"
        else:
            raise ValueError("negative control escaped: "+label)

    reject("NONRATIONAL_NUISANCE", lambda: decimal_lift(base, 1, F(0), F(100)))
    reject("GAIN_OUTSIDE", lambda: decimal_lift(base, F(3), F(0), F(100)))
    reject("DELAY_OUTSIDE", lambda: decimal_lift(base, F(1), F(2), F(100)))
    reject("TAU_OUTSIDE", lambda: quotient_key(VOLTAGE, base, F(200)))
    reject("MALFORMED_ANCHOR", lambda: quotient_key(VOLTAGE, (F(0),), F(100)))
    reject("INFEASIBLE_FAMILY", lambda: family_certificate((F(0), F(1), F(0), F(0))))
    reject("VOLTAGE_OUTSIDE", lambda: quotient_key(F(-60), base, F(100)))
    for i in range(4):
        changed = tuple(v+(F(1, 16) if i == j else 0) for j, v in enumerate(base))
        a.need(quotient_key(VOLTAGE, changed, F(100)) != key, "amplitude collision")
        checks["AMPLITUDE_"+str(i)] = "DISTINCT"
    a.need(quotient_key(VOLTAGE+1, base, F(100)) != key, "voltage collision")
    checks["VOLTAGE_CHANGED"] = "DISTINCT"
    a.need(quotient_key(VOLTAGE, base, F(120)) != key, "active tau collision")
    checks["ACTIVE_TAU_CHANGED"] = "DISTINCT"
    a.need(quotient_key(VOLTAGE, ANCHORS[1], F(100)) ==
           quotient_key(VOLTAGE, ANCHORS[1], F(120)), "silent tau must alias")
    checks["SILENT_TAU_CHANGED"] = "EQUIVALENT"
    return checks


def report():
    cases = []
    counts = {}
    bounds = []
    for index, z in enumerate(ANCHORS):
        bounds.append([a.encode(q) for q in family_certificate(z)])
        for gamma, delay, tau in itertools.product(GAIN, DELAY, TAU):
            key = quotient_key(VOLTAGE, z, tau)
            state = decimal_lift(z, gamma, delay, tau)
            point_bounds = lift_box(z, a.point(gamma), a.point(delay), a.point(tau))
            a.need(all(lo-TOLERANCE <= v <= hi+TOLERANCE
                       for v, (lo, hi) in zip(state, point_bounds, strict=True)),
                   "independent Decimal state disagrees with exact lift enclosure")
            a.need(all(0 <= v <= 1 for v in state), "point outside physical prior")
            # Direct KCL from C, not the quotient expression.
            for t in a.TIMES:
                actual = fixtures.current(F(t)+delay, state, tau_n=tau, nmda_gain=gamma)
                expected = quotient_current(t, z, tau)
                a.need(abs(actual-expected) <= TOLERANCE, "quotient trace mismatch")
            counts[key] = counts.get(key, 0)+1
            cases.append({"anchor": index, "gain": a.q(gamma), "delay_ms": a.q(delay),
                          "tau_ms": a.q(tau), "quotient": encode_key(key),
                          "state_outer_bounds": [a.encode(q) for q in point_bounds],
                          "decimal_samples_checked": len(a.TIMES)})
    a.need(len(cases) == 54 and sorted(counts.values()) == [9, 9, 9, 27],
           "complete equivalence-class roster")
    # At zero delay, the exact physical N-coordinate differs by the gain ratio.
    left = (F(1, 2), F(1, 4), F(1, 4), F(1, 4))
    right = (F(1, 2), F(1, 4), F(1, 8), F(1, 4))
    a.need(left[2] != right[2] and left[2] == 2*right[2], "gain alias witness")
    a.need(decimal_lift(ANCHORS[0], F(1), F(0), F(100)) == left
           and decimal_lift(ANCHORS[0], F(2), F(0), F(100)) == right,
           "zero-delay exact witness")
    return {
        "experiment": "CNEH-EXP-06E",
        "scope": "EXACT_NOISELESS_HYPOTHETICAL_CLAMP_QUOTIENT_ONLY",
        "theorem": "FIVE_SAMPLES_EQUAL_IFF_EFFECTIVE_QUOTIENT_EQUAL",
        "proof": "DISTINCT_EXPONENTIALS_ROLLE_ZERO_BOUND_IN_PROTOCOL",
        "anchor_family_bounds": bounds,
        "cases": cases,
        "fibers": [{"key": encode_key(k), "cases": n} for k, n in counts.items()],
        "gain_alias": {"left": [a.q(v) for v in left], "right": [a.q(v) for v in right]},
        "negative_controls": negative_controls(),
        "graph": graph_support(),
        "historical_count_observability": "FAIL_PRESERVED",
        "historical_nominal_ood": "FAIL_PRESERVED",
        "historical_noise_width": "FAIL_PRESERVED",
        "historical_2ms_reachability": "FAIL_PRESERVED",
        "calibration": "NOT_TESTED",
        "biophysical_validity": "NOT_TESTED",
        "statistical_generalization": "NOT_TESTED",
        "multiscale_scientific_coherence": "NOT_TESTED",
        "blind_causal_cohort": "BLOCKED",
        "closed_loop_efficacy": "BLOCKED",
        "source_action_authorized": False,
        "closed_loop_authorized": False,
        "scientific_promotion": "BLOCKED",
        "scientific_promotion_authorized": False,
    }
