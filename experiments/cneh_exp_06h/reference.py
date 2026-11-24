"""Reference-assisted gauge breaking; synthetic conditional guarantees only."""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache

from experiments.cneh_exp_06c import algebra as a, estimator as c

TIMES = (0, 3, 18, 24, 60, 120, 240)
PRIMARY = (0, 3, 24, 240)
STEP = F(1, 2**30)
EPS = F(1, 1024)
R = F(1, 2**20)
J = F(1, 2**20)
E = EPS+STEP/2
GAIN = (F(7, 8), F(9, 8))
GAMMA = (F(1), F(2))
DELAY = (F(0), F(1))
TAU = (F(100), F(120))
VOLTAGE = (F(-74), F(-68))
PRIOR = (F(0), F(1))
Z_PRIOR = ((F(-5, 6), F(1, 6)), PRIOR, (F(0), F(2)), PRIOR)
Z_MAG = tuple(map(a.maxabs, Z_PRIOR))
CENTER = F(5, 6)
WIDTH = F(1, 16)
COEFF_GRID = 2**80
FIELDS = {"schema", "voltage_mV", "samples", "references"}
REFS = ("zero_pA", "span_pA", "late_zero_pA", "gamma", "delay_ms", "tau_ms")
SCHEMA = "CNEH-SYNTHETIC-REFERENCE-V1"
BOUNDED = "BOUNDED_SYNTHETIC_REFERENCES"
SCOPE = "CONDITIONAL_ON_TRACE_INDEPENDENT_SYNTHETIC_REFERENCES"
NEGATIVE = {
    "historical_count_observability": "FAIL_PRESERVED",
    "historical_nominal_ood": "FAIL_PRESERVED",
    "historical_noise_width": "FAIL_PRESERVED",
    "historical_structural_aliases": "PRESERVED",
    "historical_sensor_width": "FAIL_PRESERVED",
    "historical_joint_gauge": "FAIL_PRESERVED",
    "historical_2ms_reachability": "FAIL_PRESERVED",
    "calibration": "NOT_TESTED",
    "biophysical_validity": "NOT_TESTED",
    "multiscale_scientific_coherence": "NOT_TESTED",
    "statistical_generalization": "NOT_TESTED",
    "joint_feasibility_proven": False,
    "real_calibration_verified": False,
    "scientific_promotion": "BLOCKED",
    "scientific_promotion_authorized": False,
    "source_action_authorized": False,
    "closed_loop_authorized": False,
    "closed_loop_efficacy": "BLOCKED",
    "blind_causal_cohort": "BLOCKED",
}


def constant():
    return a.sub(a.point(120), a.mul(a.point(20), a.exponential(F(-5, 2))))


def nmda_block():
    return a.reciprocal(a.add(a.point(1), a.div(
        a.exponential(F(93, 25)), a.point(F(357, 100)))))


def exp_interval(interval):
    return a.exponential(interval[0])[0], a.exponential(interval[1])[1]


@lru_cache(maxsize=128)
def row(t, tau):
    a.need(t in TIMES and TAU[0] <= tau[0] <= tau[1] <= TAU[1],
           "reference matrix domain")
    return tuple(a.outward(x, COEFF_GRID) for x in (
        a.mul(a.point(24), a.exponential(-F(t, 200))),
        a.mul(a.point(-6), a.exponential(-F(t)/F(5, 2))),
        a.mul(a.mul(a.point(-6), nmda_block()),
              exp_interval((-F(t)/tau[0], -F(t)/tau[1]))),
        a.mul(a.point(5), a.exponential(-F(t, 6))),
    ))


@lru_cache(maxsize=128)
def preconditioner(tau):
    rows = tuple(row(t, tau) for t in PRIMARY)
    mid = [[a.midpoint(value) for value in r] for r in rows]
    return rows, tuple(tuple(r) for r in a.inverse(mid))


def inverse_norm_certificate(tau):
    rows, inverse = preconditioner(tau)
    b = tuple(sum(map(abs, r), F(0)) for r in inverse)
    m = []
    for i in range(4):
        entries = [
            a.sub(a.point(int(i == j)), a.isum(
                a.mul(a.point(inverse[i][k]), rows[k][j]) for k in range(4)))
            for j in range(4)
        ]
        m.append(sum(map(a.maxabs, entries), F(0)))
    eta = max(m)
    a.need(eta < 1, "interval inverse contraction not certified")
    upper = tuple(a.outward((v+error*max(b)/(1-eta),)*2, 2**40)[1]
                  for v, error in zip(b, m, strict=True))
    return {"tau_ms": a.encode(tau), "eta_upper": a.q(a.outward((eta, eta), 2**40)[1]),
            "row_norm_uppers": [a.q(v) for v in upper]}


@lru_cache(maxsize=1)
def diameter_certificate():
    # Every tau in the full continuous physiological prior belongs to a cell.
    cells = [inverse_norm_certificate((F(k), F(k+2))) for k in range(100, 119)]
    norms = tuple(max(F(cell["row_norm_uppers"][i]) for cell in cells) for i in range(4))
    gain_width = 4*R/128
    current_diff = 2*(E+R)/GAIN[0]+200*gain_width/GAIN[0]**2+8*J
    tau_mismatch = 6*F(240, 100**2)*2*R*2
    effective = tuple(norm*(current_diff+tau_mismatch) for norm in norms)
    rates = (F(1, 200), F(2, 5), F(1, 100), F(1, 6))
    factors = tuple(a.exponential(rate)[1] for rate in rates)
    slopes = (rates[0], rates[1], F(1, 100)+F(1, 10000)+1, rates[3])
    raw_bounds = tuple(factor*(width+mag*2*R*slope)
                       for factor, width, mag, slope in
                       zip(factors, effective, Z_MAG, slopes, strict=True))
    bounds = tuple(a.outward((v, v), 2**40)[1] for v in raw_bounds)
    a.need(max(bounds) <= WIDTH, "global conditional width target not certified")
    return {
        "scope": "ALL_COMPATIBLE_PAIRS_REFERENCE_ASSISTED_SYNTHETIC_MODEL",
        "primary_times_ms": list(PRIMARY), "full_tau_cover": cells,
        "row_norm_uppers": [a.q(v) for v in norms],
        "reference_total_error": a.q(R), "residual_jitter_ms": a.q(J),
        "current_pair_difference_upper_pA": a.q(current_diff),
        "tau_mismatch_upper_pA": a.q(tau_mismatch),
        "coordinate_diameter_uppers": [a.q(v) for v in bounds],
        "max_diameter_upper": a.q(max(bounds)), "target": a.q(WIDTH),
        "margin_lower": a.q(WIDTH-max(bounds)),
        "status": "PASS_CONDITIONAL_FINITE_NOISE_DIAMETER",
        "real_calibration_verified": False,
        "scientific_promotion_authorized": False,
    }


def code(value):
    v = a.decode(value)
    a.need(abs(v) <= 1000 and (v/STEP).denominator == 1, "sensor code domain")
    return v


def parse(record):
    a.need(type(record) is dict and set(record) == FIELDS and record["schema"] == SCHEMA,
           "reference record schema")
    voltage = a.decode(record["voltage_mV"])
    a.need(VOLTAGE[0] <= voltage <= VOLTAGE[1], "voltage domain")
    samples = record["samples"]
    a.need(type(samples) is list and len(samples) == len(TIMES), "sample roster")
    observed = []
    for t, item in zip(TIMES, samples, strict=True):
        a.need(type(item) is dict and set(item) == {"t_ms", "current_pA"} and
               type(item["t_ms"]) is int and item["t_ms"] == t, "sample chronology")
        observed.append(code(item["current_pA"]))
    refs = record["references"]
    if refs is not None:
        a.need(type(refs) is dict and set(refs) == set(REFS), "reference roster")
        refs = {name: code(refs[name]) for name in REFS}
    return voltage, observed, refs


def reference_intervals(refs):
    a.need(refs is not None, "missing independent references")
    r0, r1, r240, gamma, delay, tau = (refs[name] for name in REFS)
    values = {
        "gain": c.intersect(GAIN, ((r1-r0-2*R)/128, (r1-r0+2*R)/128)),
        "offset": c.intersect((F(-16), F(16)), (r0-R, r0+R)),
        "drift": c.intersect((F(-1), F(1)), ((r240-r0-2*R)/2, (r240-r0+2*R)/2)),
        "gamma": c.intersect(GAMMA, (gamma-R, gamma+R)),
        "delay": c.intersect(DELAY, (delay-R, delay+R)),
        "tau": c.intersect(TAU, (tau-R, tau+R)),
    }
    return None if any(x is None for x in values.values()) else values


def result(status, voltage, bounds=None, refs=None):
    return {"status": status, "scope": SCOPE, "voltage_mV": a.q(voltage),
            "normalized_bounds": None if bounds is None else [a.encode(x) for x in bounds],
            "max_width": None if bounds is None else a.q(max(hi-lo for lo, hi in bounds)),
            "reference_intervals": None if refs is None else
                {name: a.encode(value) for name, value in refs.items()},
            **NEGATIVE}


def estimate(record, profile="UNVERIFIED"):
    a.need(type(profile) is str and profile in ("UNVERIFIED", BOUNDED), "unknown reference profile")
    voltage, observed, codes = parse(record)
    if profile == "UNVERIFIED":
        return result("CALIBRATION_UNVERIFIED", voltage, (PRIOR,)*4)
    refs = reference_intervals(codes)
    if refs is None:
        return result("INCONSISTENT_REFERENCE", voltage)
    residuals = {}
    for t, y in zip(TIMES, observed, strict=True):
        alpha = F(t, 240)
        baseline = (1-alpha)*codes["zero_pA"]+alpha*codes["late_zero_pA"]
        corrected = y-baseline
        numerator = c.intersect((F(-200), F(200)), (corrected-E-R, corrected+E+R))
        if numerator is None:
            return result("INCONSISTENT_CURRENT", voltage, refs=refs)
        residuals[t] = a.outward(a.add(a.sub(a.div(numerator, refs["gain"]), constant()),
                                       (-4*J, 4*J)), 2**80)
    rows, inverse = preconditioner(refs["tau"])
    rhs = []
    for t, coefficients in zip(PRIMARY, rows, strict=True):
        radius = sum((a.radius(coef)*mag for coef, mag in
                      zip(coefficients, Z_MAG, strict=True)), F(0))
        rhs.append(a.add(residuals[t], (-radius, radius)))
    z = []
    for prior, inverse_row in zip(Z_PRIOR, inverse, strict=True):
        candidate = a.outward(a.isum(a.mul(a.point(b), y)
                                     for b, y in zip(inverse_row, rhs, strict=True)), 2**60)
        overlap = c.intersect(prior, candidate)
        if overlap is None:
            return result("INCONSISTENT_PRIMARY", voltage, refs=refs)
        z.append(overlap)
    for t in TIMES:
        predicted = a.isum(a.mul(x, v) for x, v in zip(row(t, refs["tau"]), z, strict=True))
        if c.intersect(predicted, residuals[t]) is None:
            return result("INCONSISTENT_FORWARD", voltage, refs=refs)
    d, tau, gamma = refs["delay"], refs["tau"], refs["gamma"]
    factors = (
        exp_interval(a.div(d, a.point(200))),
        exp_interval(a.div(d, a.point(F(5, 2)))),
        a.div(exp_interval(a.div(d, tau)), gamma),
        exp_interval(a.div(d, a.point(6))),
    )
    physical = []
    for i, (v, factor) in enumerate(zip(z, factors, strict=True)):
        x = a.mul(v, factor)
        if i == 0:
            x = a.add(x, a.point(CENTER))
        overlap = c.intersect(PRIOR, a.outward(x, 2**40))
        if overlap is None:
            return result("INCONSISTENT_PHYSICAL_PRIOR", voltage, refs=refs)
        physical.append(overlap)
    status = "CONDITIONAL_NARROW_ENCLOSURE" if all(hi-lo <= WIDTH for lo, hi in physical) else "ABSTAIN_WIDTH"
    return result(status, voltage, physical, refs)
