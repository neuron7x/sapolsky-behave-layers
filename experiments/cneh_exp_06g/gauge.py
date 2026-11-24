"""Joint synthetic gauge theorem certificates, not physical inference."""
from __future__ import annotations

from decimal import Decimal as D, localcontext
from fractions import Fraction as F
import itertools

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f import panel as f

TIMES = (0, 3, 7, 18, 30, 60, 120)
GAINS = (F(7, 8), F(9, 8))
GAMMAS = (F(1), F(2))
DELAYS = (F(0), F(1))
TAUS = (F(100), F(110), F(120))
ANCHORS = ((F(-1, 4), F(1, 8), F(1, 8), F(1, 8)),
           (F(-1, 4), F(1, 8), F(0), F(1, 8)))
CENTER = F(5, 6)
TOL = F(1, 10**100)
NEGATIVE = {
    "historical_count_observability": "FAIL_PRESERVED",
    "historical_nominal_ood": "FAIL_PRESERVED",
    "historical_noise_width": "FAIL_PRESERVED",
    "historical_structural_aliases": "PRESERVED",
    "historical_sensor_width": "FAIL_PRESERVED",
    "historical_2ms_reachability": "FAIL_PRESERVED",
    "calibration": "NOT_TESTED",
    "biophysical_validity": "NOT_TESTED",
    "joint_finite_noise_feasibility": "NOT_TESTED",
    "multiscale_scientific_coherence": "NOT_TESTED",
    "statistical_generalization": "NOT_TESTED",
    "blind_causal_cohort": "BLOCKED",
    "closed_loop_efficacy": "BLOCKED",
    "real_calibration_verified": False,
    "scientific_promotion": "BLOCKED",
    "scientific_promotion_authorized": False,
    "source_action_authorized": False,
    "closed_loop_authorized": False,
}


def constant_interval():
    return a.sub(a.point(120), a.mul(a.point(20), a.exponential(F(-5, 2))))


def validate_nuisance(g, gamma, delta, tau):
    a.need(all(type(x) is F for x in (g, gamma, delta, tau)),
           "exact nuisance coordinates required")
    a.need(GAINS[0] <= g <= GAINS[-1] and 1 <= gamma <= 2 and
           0 <= delta <= 1 and 100 <= tau <= 120, "nuisance domain")


def key(v, offset_from_c0, drift, u, tau):
    """Key in exact effective coordinates only, not an observation inverse."""
    a.need(type(u) is tuple and len(u) == 4 and all(type(x) is F for x in u),
           "effective coordinate encoding")
    a.need(type(v) is F and -74 <= v <= -68, "voltage domain")
    a.need(type(offset_from_c0) is F and type(drift) is F and -1 <= drift <= 1,
           "effective offset/drift encoding")
    validate_nuisance(F(1), F(1), F(0), tau)
    a.need(u[1] >= 0 and u[2] >= 0 and u[3] >= 0, "effective conductance domain")
    return (v, offset_from_c0, drift, *u, tau if u[2] else None)


def encode_key(value):
    return [None if x is None else a.q(x) for x in value]


def dec(x):
    value = F(x)
    return D(value.numerator)/D(value.denominator)


def c0():
    return D(120)-20*D("-2.5").exp()


def block():
    return D("3.57")/(D("3.57")+D("3.72").exp())


def lift(u, g, gamma, delta, tau):
    validate_nuisance(g, gamma, delta, tau)
    key(F(-71), F(0), F(0), u, tau)
    with localcontext() as context:
        context.prec = 120
        w, aa, nn, hh = map(dec, u)
        g, gamma, delta, tau = map(dec, (g, gamma, delta, tau))
        x = (D(5)/6+w*(delta/200).exp()/g,
             aa*(delta*2/5).exp()/g,
             nn*(delta/tau).exp()/(g*gamma),
             hh*(delta/6).exp()/g)
        b = (1-g)*c0()
        a.need(all(0 <= v <= 1 for v in x) and -16 <= b <= 16,
               "lift outside declared domain")
        return tuple(map(F, x)), F(b)


def direct_current(t, x, g, gamma, delta, tau, b, d):
    """Independent direct KCL in physical units, evaluated at 120 digits."""
    with localcontext() as context:
        context.prec = 120
        w, aa, nn, hh = map(dec, x)
        g, gamma, delta, tau, b, d = map(dec, (g, gamma, delta, tau, b, d))
        time = dec(t)+delta
        adapt = 20+(24*w-20)*(-time/200).exp()
        ampa = D("0.1")*aa*(-time*2/5).exp()
        nmda = D("0.1")*nn*(-time/tau).exp()
        gaba = D("0.5")*hh*(-time/6).exp()
        current = 100-20*D("-2.5").exp()+adapt-60*ampa-60*block()*gamma*nmda+10*gaba
        return F(g*current+b+d*dec(t)/120)


def trace_basis(t, tau):
    """Decimal evaluation basis for (A0,d,u_w,u_A,u_N,u_G)."""
    time, rate = dec(t), dec(tau)
    return (D(1), time/120, 24*(-time/200).exp(),
            -6*(-time*2/5).exp(), -6*block()*(-time/rate).exp(),
            5*(-time/6).exp())


def effective_current(t, u, tau, offset_from_c0=F(0), drift=F(0)):
    with localcontext() as context:
        context.prec = 120
        coefficients = (c0()+dec(offset_from_c0), dec(drift), *map(dec, u))
        return F(sum((v*w for v, w in zip(trace_basis(t, tau), coefficients, strict=True)), D(0)))


def sharp_certificate():
    rates = (
        ("w", F(7, 9), F(1, 200), CENTER),
        ("AMPA", F(7, 9), F(2, 5), F(1)),
        ("NMDA", F(7, 18), F(1, 100), F(1)),
        ("GABA", F(7, 9), F(1, 6), F(1)),
    )
    bounds = {}
    ratios = {}
    for name, factor, decay, amplitude in rates:
        ratio = a.mul(a.point(factor), a.exponential(-decay))
        upper = a.mul(a.point(amplitude), a.sub(a.point(1), ratio))
        bounds[name] = a.outward(upper, 2**40)
        ratios[name] = a.encode(a.outward(ratio, 2**40))
    optimum = bounds["NMDA"]
    a.need(all(optimum[0] > x[1] for name, x in bounds.items() if name != "NMDA"),
           "NMDA coordinate does not dominate")
    a.need(optimum[1]-optimum[0] <= F(1, 2**32), "optimum certificate width")
    offset = a.mul(a.point(F(1, 8)), constant_interval())
    a.need(0 < offset[0] <= offset[1] < 16, "attainment offset not admissible")
    return {
        "scope": "SHARP_GLOBAL_DIAMETER_EXACT_NOISELESS_TRACE_ONLY",
        "formula": "1-(7/18)*exp(-1/100)",
        "diameter_outer": a.encode(optimum),
        "coordinate_upper_bounds": {name: a.encode(x) for name, x in bounds.items()},
        "ratio_outer": ratios, "attainment_offset_magnitude_pA": a.encode(offset),
        "noisy_upper_bound": "NOT_ESTABLISHED",
        "minimax_point_error_lower_bound": a.encode(a.mul(a.point(F(1, 2)), optimum)),
    }


def interval_current(t, x, g, gamma, delta, tau, offset):
    validate_nuisance(g, gamma, delta, tau)
    a.need(len(x) == 4 and all(type(v) is F and 0 <= v <= 1 for v in x),
           "normalized truth domain")
    a.need(type(t) is int and t in a.TIMES and type(offset) is F and -16 <= offset <= 16,
           "channel time/offset domain")
    w, aa, nn, hh = x
    time = F(t)+delta
    nmda_block = a.reciprocal(a.add(a.point(1), a.div(
        a.exponential(F(93, 25)), a.point(F(357, 100)))))
    terms = (
        a.mul(a.point(24*w-20), a.exponential(-time/200)),
        a.mul(a.point(-6*aa), a.exponential(-time/F(5, 2))),
        a.mul(a.mul(a.point(-6*gamma*nn), nmda_block), a.exponential(-time/tau)),
        a.mul(a.point(5*hh), a.exponential(-time/6)),
    )
    return a.outward(a.add(a.mul(a.point(g), a.add(constant_interval(), a.isum(terms))),
                            a.point(offset)), 2**120)


def finite_witness(name):
    a.need(name in ("ZERO_DELAY", "SHARP_DELAY"), "witness roster")
    delay = F(1) if name == "SHARP_DELAY" else F(0)
    tau = F(100)
    step = F(1, 2**30)
    offset = a.mul(a.point(F(1, 8)), constant_interval())
    b = f.quantize(a.midpoint(offset), step)
    n_outer = a.mul(a.point(F(7, 18)), a.exponential(-delay/tau))
    n = f.quantize(a.midpoint(n_outer), step) if delay else F(7, 18)
    left = (CENTER, F(0), F(1), F(0))
    right = (CENTER, F(0), n, F(0))
    separation = 1-n
    if delay:
        lower = F(sharp_certificate()["diameter_outer"][0])
        a.need(separation >= lower-F(1, 2**29), "sharp finite witness separation")
    else:
        a.need(separation == F(11, 18), "zero-delay witness separation")
    samples = []
    for t in a.TIMES:
        il = interval_current(t, left, GAINS[0], F(1), delay, tau, b)
        ir = interval_current(t, right, GAINS[-1], F(2), F(0), tau, -b)
        hull = (min(il[0], ir[0]), max(il[1], ir[1]))
        code = f.quantize(a.midpoint(hull), step)
        dl = max(abs(code-v) for v in il)
        dr = max(abs(code-v) for v in ir)
        a.need(max(dl, dr) <= f.EPS and code/step == int(code/step),
               "shared quantized record infeasible")
        samples.append({"time_ms": t, "code_pA": a.q(code),
                        "left_outer_pA": a.encode(il), "right_outer_pA": a.encode(ir),
                        "left_worst_error_pA": a.q(dl), "right_worst_error_pA": a.q(dr)})
    return {
        "name": name, "scope": "FINITE_RECORD_DIAMETER_LOWER_BOUND_ONLY",
        "separation": a.q(separation), "voltage_mV": "-71/1", "tau_ms": a.q(tau),
        "epsilon_pA": a.q(f.EPS), "step_pA": a.q(step),
        "left": {"x": [a.q(v) for v in left], "gain": "7/8", "gamma": "1/1",
                 "delay_ms": a.q(delay), "offset_pA": a.q(b), "drift_pA": "0/1"},
        "right": {"x": [a.q(v) for v in right], "gain": "9/8", "gamma": "2/1",
                  "delay_ms": "0/1", "offset_pA": a.q(-b), "drift_pA": "0/1"},
        "samples": samples,
    }


def panel():
    rows = []
    for index, g, gamma, delta, tau in itertools.product(
            range(2), GAINS, GAMMAS, DELAYS, TAUS):
        u = ANCHORS[index]
        x, b = lift(u, g, gamma, delta, tau)
        errors = [abs(direct_current(t, x, g, gamma, delta, tau, b, F(0)) -
                      effective_current(t, u, tau)) for t in TIMES]
        a.need(max(errors) <= TOL, "independent direct KCL discrepancy")
        rows.append({"anchor": index, "gain": a.q(g), "gamma": a.q(gamma),
                     "delay_ms": a.q(delta), "tau_ms": a.q(tau),
                     "key": encode_key(key(F(-71), F(0), F(0), u, tau)),
                     "x": [a.q(v) for v in x], "offset_pA": a.q(b),
                     "times_ms": list(TIMES), "absolute_errors_pA": [a.q(v) for v in errors]})
    a.need(len(rows) == 48, "complete lift roster")
    return rows
