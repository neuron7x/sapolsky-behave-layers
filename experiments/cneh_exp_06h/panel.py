"""Fixed synthetic reference panel with independent forward certificates."""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache
from itertools import product

from experiments.cneh_exp_06c import algebra as a, fixtures
from experiments.cneh_exp_06f import panel as f
from experiments.cneh_exp_06g import gauge as g
from experiments.cneh_exp_06h import reference as h

TRUTHS = (0, 3, 6, 9, 12, 15, 16, 31)
SIGNS = (1, -1)
QUALIFIED = "PASS_CONDITIONAL_REFERENCE_ASSISTED_ENCLOSURE_ONLY"


def worlds():
    return tuple(product(h.GAIN, h.GAMMA, h.DELAY, h.TAU))+(
        (F(1), F(3, 2), F(1, 2), F(110)),)


@lru_cache(maxsize=512)
def exact_current(t, x, gamma, tau):
    """Exact outward interval, independent of reference inverse coordinates."""
    a.need(type(t) is F and 0 <= t <= 242, "actual time domain")
    w, aa, nn, gg = x
    block = a.reciprocal(a.add(a.point(1), a.div(
        a.exponential(F(93, 25)), a.point(F(357, 100)))))
    base = a.sub(a.point(120), a.mul(a.point(20), a.exponential(F(-5, 2))))
    return a.outward(a.add(base, a.isum((
        a.mul(a.point(24*w-20), a.exponential(-t/200)),
        a.mul(a.point(-6*aa), a.exponential(-t/F(5, 2))),
        a.mul(a.mul(a.point(-6*gamma*nn), block), a.exponential(-t/tau)),
        a.mul(a.point(5*gg), a.exponential(-t/6)),
    ))), 2**120)


def exact_channel(t, j, x, gain, gamma, delay, tau, offset, drift):
    return a.add(a.mul(a.point(gain), exact_current(F(t)+delay+j, x, gamma, tau)),
                 a.point(offset+drift*F(t, 120)))


def contains(result, x):
    return result["normalized_bounds"] is not None and all(
        F(lo) <= value <= F(hi) for value, (lo, hi) in
        zip(x, result["normalized_bounds"], strict=True))


def make_record(v, x, gain, gamma, delay, tau, offset, drift, sign):
    samples, reference_errors, certificates = [], {}, []
    for index, t in enumerate(h.TIMES):
        polarity = sign*(-1)**index
        j = h.J if polarity == 1 else F(0)
        independent = fixtures.current(F(t)+delay+j, x, tau_n=tau, nmda_gain=gamma)
        exact = exact_current(F(t)+delay+j, x, gamma, tau)
        a.need(exact[0] <= independent <= exact[1], "independent KCL outside certificate")
        clean = gain*independent+offset+drift*F(t, 120)
        code = f.quantize(clean+F(3*polarity, 4)*h.EPS, h.STEP)
        certified = exact_channel(t, j, x, gain, gamma, delay, tau, offset, drift)
        distance = max(abs(code-q) for q in certified)
        a.need(distance <= h.E, "current code error outside contract")
        samples.append({"t_ms": t, "current_pA": a.q(code)})
        certificates.append({"t_ms": t, "jitter_ms": a.q(j),
                             "clean_channel_outer_pA": a.encode(certified),
                             "worst_code_error_pA": a.q(distance)})
    reference_truths = (offset, 128*gain+offset, offset+2*drift, gamma, delay, tau)
    refs = {}
    for index, (name, true) in enumerate(zip(h.REFS, reference_truths, strict=True)):
        code = f.quantize(true+sign*(-1)**index*h.R/2, h.STEP)
        error = abs(code-true)
        a.need(error <= h.R, "reference code error outside contract")
        refs[name] = a.q(code)
        reference_errors[name] = a.q(error)
    record = {"schema": h.SCHEMA, "voltage_mV": a.q(v),
              "samples": samples, "references": refs}
    return record, certificates, reference_errors


def assess(record, x):
    inverse = h.estimate(record, h.BOUNDED)
    unknown = h.estimate(record)
    a.need(contains(inverse, x), "compatible reference-assisted truth excluded")
    a.need(inverse["status"] == "CONDITIONAL_NARROW_ENCLOSURE" and
           F(inverse["max_width"]) <= h.WIDTH, "actual inverse width exceeds target")
    a.need(unknown["status"] == "CALIBRATION_UNVERIFIED" and
           unknown["normalized_bounds"] == [["0/1", "1/1"]]*4,
           "unverified fallback not full prior")
    for value in (inverse, unknown):
        a.need(all(type(value.get(k)) is type(v) and value[k] == v
                   for k, v in h.NEGATIVE.items()), "negative evidence or authority leak")
    return inverse, unknown


def panel_case(index, nuisance, sign):
    v, x = fixtures.truth(index)
    gain, gamma, delay, tau = nuisance
    offset, drift = F(16*sign), F(-sign)
    record, certs, errors = make_record(v, x, gain, gamma, delay, tau, offset, drift, sign)
    inverse, unknown = assess(record, x)
    return {"truth_id": index, "truth": [a.q(q) for q in x], "sign": sign,
            "nuisance": [a.q(q) for q in nuisance], "offset_pA": a.q(offset),
            "drift_pA": a.q(drift), "record": record, "current_certificates": certs,
            "reference_code_errors": errors, "estimate": inverse, "unverified": unknown}


def gamma_ablation():
    """Same trace and other references cannot identify unknown NMDA gain."""
    left = (h.CENTER, F(0), F(1), F(0))
    right = (h.CENTER, F(0), F(1, 2), F(0))
    samples = []
    for t in a.TIMES:
        il = exact_current(F(t), left, F(1), F(100))
        ir = exact_current(F(t), right, F(2), F(100))
        code = f.quantize(a.midpoint((min(il[0], ir[0]), max(il[1], ir[1]))), h.STEP)
        distances = (max(abs(code-v) for v in il), max(abs(code-v) for v in ir))
        a.need(max(distances) <= h.E, "gamma ablation common code infeasible")
        samples.append({"t_ms": t, "current_pA": a.q(code),
                        "left_outer_pA": a.encode(il), "right_outer_pA": a.encode(ir),
                        "worst_errors_pA": [a.q(q) for q in distances]})
    a.need(left[2] == 2*right[2] and left[2]-right[2] == F(1, 2),
           "gamma structural ablation separation")
    codes = (F(1), F(2))
    a.need(abs(codes[0]-codes[1]) > 2*h.R, "independent gamma reference fails separation")
    return {"status": "FAIL_WITHOUT_GAMMA_REFERENCE", "separation": "1/2",
            "left": [a.q(q) for q in left], "right": [a.q(q) for q in right],
            "left_gamma": "1/1", "right_gamma": "2/1",
            "same_electronics_time_tau_references": True, "samples": samples,
            "gamma_reference_codes": [a.q(q) for q in codes]}


def g_witness_recovery():
    witness = g.finite_witness("SHARP_DELAY")
    records = []
    for side in ("left", "right"):
        world = witness[side]
        x = tuple(map(F, world["x"]))
        other = tuple(map(F, witness["right" if side == "left" else "left"]["x"]))
        v = F(witness["voltage_mV"])
        record, certs, errors = make_record(
            v, x, F(world["gain"]), F(world["gamma"]), F(world["delay_ms"]),
            F(witness["tau_ms"]), F(world["offset_pA"]), F(world["drift_pA"]), 1)
        estimate, unknown = assess(record, x)
        a.need(not contains(estimate, other), "reference-assisted G alias not separated")
        records.append({"side": side, "truth": [a.q(q) for q in x],
                        "other_truth_excluded": True, "record": record,
                        "estimate": estimate, "unverified": unknown,
                        "current_certificates": certs, "reference_code_errors": errors})
    return {"original_G_witness": witness, "reference_assisted_recovery": records}


def report():
    results, failures, rows = {}, [], []
    for name, operation in (("diameter_certificate", h.diameter_certificate),
                            ("gamma_ablation", gamma_ablation),
                            ("g_witness_recovery", g_witness_recovery)):
        try:
            results[name] = operation()
        except Exception as exc:
            failures.append({"stage": name, "error_type": type(exc).__name__, "error": str(exc)})
    for i, nuisance, sign in product(TRUTHS, worlds(), SIGNS):
        try:
            rows.append(panel_case(i, nuisance, sign))
        except Exception as exc:
            failures.append({"stage": "panel", "truth_id": i, "nuisance": [a.q(q) for q in nuisance],
                             "sign": sign, "error_type": type(exc).__name__, "error": str(exc)})
    identities = {(row["truth_id"], tuple(row["nuisance"]), row["sign"]) for row in rows}
    a.need(len(rows) == len(identities), "duplicate case identity")
    if not failures:
        a.need(len(rows) == 272, "complete fixed reference panel")
    return {"experiment": "CNEH-EXP-06H", "scope": h.SCOPE, "cases": rows,
            "qualification": "FAIL_ENGINEERING_GATE" if failures else QUALIFIED,
            "failures": failures, "panel_max_width": a.q(max(
                (F(row["estimate"]["max_width"]) for row in rows), default=F(0))),
            **results, **h.NEGATIVE}
