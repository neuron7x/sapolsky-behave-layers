"""Fixed, independently generated stress panel and certified channel aliases."""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction as F
from functools import lru_cache
import itertools

from experiments.cneh_exp_06c import algebra as a, estimator as c, fixtures
from experiments.cneh_exp_06f import channel

EPS = F(1, 1024)
FINE = F(1, 2**20)
COARSE = F(1, 4)
TRUTHS = (0, 3, 6, 9, 12, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 31)
SIGNS = ((1, -1, 1, -1, 1), (-1, 1, -1, 1, -1))
ZERO_JITTER = (F(0),)*5
PROFILES = ("IDEAL_QUANTIZED", "WIDE_SYNTHETIC", "UNVERIFIED")
NEGATIVE = {
    "historical_count_observability": "FAIL_PRESERVED",
    "historical_nominal_ood": "FAIL_PRESERVED",
    "historical_noise_width": "FAIL_PRESERVED",
    "historical_structural_aliases": "PRESERVED",
    "historical_2ms_reachability": "FAIL_PRESERVED",
    "calibration": "NOT_TESTED",
    "biophysical_validity": "NOT_TESTED",
    "multiscale_scientific_coherence": "NOT_TESTED",
    "statistical_generalization": "NOT_TESTED",
    "blind_causal_cohort": "BLOCKED",
    "closed_loop_efficacy": "BLOCKED",
    **channel.NEGATIVE_GATES,
}


@dataclass(frozen=True)
class Scenario:
    name: str
    gain: F = F(1)
    offset: F = F(0)
    drift: F = F(0)
    jitter: tuple[F, ...] = ZERO_JITTER
    step: F = FINE
    cap: F | None = None


def scenarios():
    nominal = Scenario("NOMINAL")
    return (
        nominal,
        replace(nominal, name="GAIN_HI", gain=F(9, 8)),
        replace(nominal, name="GAIN_LO", gain=F(7, 8)),
        replace(nominal, name="OFFSET_POS", offset=F(16)),
        replace(nominal, name="OFFSET_NEG", offset=F(-16)),
        replace(nominal, name="DRIFT_POS", drift=F(1)),
        replace(nominal, name="DRIFT_NEG", drift=F(-1)),
        replace(nominal, name="JITTER_ALT", jitter=tuple(map(F, (0, 1, 0, 1, 0)))),
        replace(nominal, name="JITTER_REVERSE", jitter=tuple(map(F, (1, 0, 1, 0, 1)))),
        replace(nominal, name="COARSE", step=COARSE),
        Scenario("COMPOSITE", F(9, 8), F(-16), F(1),
                 (F(0), F(1), F(1, 2), F(1), F(0)), COARSE),
        replace(nominal, name="CLIP", cap=F(110)),
    )


def quantize(value, step):
    a.need(type(value) is F and type(step) is F and step > 0, "quantizer domain")
    return round(value/step)*step


def channel_membership(scenario, profile):
    p = channel.PROFILES[profile]
    return (scenario.cap is None and
            p.gain[0] <= scenario.gain <= p.gain[1] and
            p.offset[0] <= scenario.offset <= p.offset[1] and
            p.drift[0] <= scenario.drift <= p.drift[1] and
            len(scenario.jitter) == 5 and
            all(0 <= j <= p.jitter for j in scenario.jitter) and
            0 < scenario.step <= p.quantization)


@lru_cache(maxsize=256)
def certified_current(t, x):
    """Independent exact interval KCL, valid at displaced sample times."""
    a.need(type(t) is F and 0 <= t <= 121 and len(x) == 4 and
           all(type(v) is F and 0 <= v <= 1 for v in x), "truth/time domain")
    w, ampa, nmda, gaba = x
    block = a.reciprocal(a.add(a.point(1),
                              a.div(a.exponential(F(93, 25)), a.point(F(357, 100)))))
    baseline = a.sub(a.point(120), a.mul(a.point(20), a.exponential(F(-5, 2))))
    terms = (
        a.mul(a.point(24*w-20), a.exponential(-t/200)),
        a.mul(a.point(-6*ampa), a.exponential(-t/F(5, 2))),
        a.mul(a.mul(a.point(-6*nmda), block), a.exponential(-t/100)),
        a.mul(a.point(5*gaba), a.exponential(-t/6)),
    )
    return a.outward(a.add(baseline, a.isum(terms)), 2**120)


def certified_channel(t, x, s, j):
    return a.add(a.mul(a.point(s.gain), certified_current(F(t)+j, x)),
                 a.point(s.offset+s.drift*F(t, 120)))


def measurement(v, values):
    return {
        "schema": c.SCHEMA,
        "voltage_mV": a.q(v),
        "voltage_error_mV": "0/1",
        "current_error_pA": a.q(EPS),
        "samples": [{"t_ms": t, "current_pA": a.q(y)}
                    for t, y in zip(a.TIMES, values, strict=True)],
    }


def contains_interval(outer, inner):
    return outer[0] <= inner[0] <= inner[1] <= outer[1]


def certify_compatibility(x, observed, profile):
    outer = channel.dewarp(observed, EPS, profile)
    for t, bounds in zip(a.TIMES, outer, strict=True):
        a.need(contains_interval(bounds, a.current_interval(t, x)),
               "dewarped nominal current excluded")
    return [a.encode(x) for x in outer]


def no_authority(result):
    a.need(all(result.get(flag) is False for flag in (
        "source_action_authorized", "closed_loop_authorized",
        "scientific_promotion_authorized")), "authority leak")
    a.need(result["scientific_promotion"] == "BLOCKED", "promotion leak")


def evaluate(v, x, record):
    estimates = {"C_NOMINAL": c.estimate(record)}
    estimates.update({name: channel.estimate(record, name) for name in PROFILES})
    results = {}
    for name, estimate in estimates.items():
        no_authority(estimate)
        if name != "C_NOMINAL":
            a.need(estimate["real_calibration_verified"] is False and
                   estimate["joint_feasibility_proven"] is False, "false calibration")
        covered = fixtures.contains(estimate, v, x)
        narrow = estimate["status"] == "CONDITIONAL_NARROW_ENCLOSURE"
        results[name] = {
            "estimate": estimate,
            "truth_enclosed": covered,
            "false_narrow": narrow and not covered,
        }
    unknown = estimates["UNVERIFIED"]
    a.need(unknown["status"] == "CALIBRATION_UNVERIFIED" and
           unknown["normalized_bounds"] == [["0/1", "1/1"]]*4 and
           unknown["voltage_bounds_mV"] == ["-74/1", "-68/1"] and
           results["UNVERIFIED"]["truth_enclosed"], "unverified fallback")
    return results


def panel_case(index, s, signs):
    v, x = fixtures.truth(index)
    values = []
    channel_bounds = []
    clipping_active = []
    for t, jitter, sign in zip(a.TIMES, s.jitter, signs, strict=True):
        independent = fixtures.current(F(t)+jitter, x)
        interval = certified_current(F(t)+jitter, x)
        a.need(contains_interval(interval, (independent, independent)),
               "independent KCL outside exact certificate")
        clean = s.gain*independent+s.offset+s.drift*F(t, 120)
        analog = clean+F(3*sign, 4)*EPS
        active = s.cap is not None and analog > s.cap
        code = quantize(min(analog, s.cap) if s.cap is not None else analog, s.step)
        certified = certified_channel(t, x, s, jitter)
        if s.cap is None:
            a.need(max(abs(code-lo) for lo in certified) <= EPS+s.step/2,
                   "bounded channel record incompatible")
        channel_bounds.append(a.encode(certified))
        clipping_active.append(active)
        values.append(code)
    record = measurement(v, values)
    results = evaluate(v, x, record)
    wide = channel_membership(s, "WIDE_SYNTHETIC")
    ideal = channel_membership(s, "IDEAL_QUANTIZED")
    a.need(wide == (s.cap is None) and ideal == (s.name == "NOMINAL"),
           "locked scenario membership")
    certificates = {}
    for name, compatible in (("WIDE_SYNTHETIC", wide), ("IDEAL_QUANTIZED", ideal)):
        if compatible:
            certificates[name] = certify_compatibility(x, values, name)
            a.need(results[name]["truth_enclosed"], "compatible truth excluded: "+name)
    return {
        "truth_id": index, "voltage_mV": a.q(v), "truth": [a.q(z) for z in x],
        "scenario": s.name, "noise_signs": list(signs),
        "channel": {"gain": a.q(s.gain), "offset_pA": a.q(s.offset),
                    "drift_pA": a.q(s.drift), "jitter_ms": [a.q(j) for j in s.jitter],
                    "quantization_pA": a.q(s.step),
                    "clipping_cap_pA": None if s.cap is None else a.q(s.cap)},
        "bounded_wide": wide, "bounded_ideal": ideal,
        "clipping_active": clipping_active,
        "noiseless_pre_clip_channel_intervals": channel_bounds,
        "measurement": record, "dewarped_certificates": certificates,
        "outcomes": results,
    }


def alias_witness():
    left = (F(1, 2), F(3, 4), F(3, 4), F(3, 4))
    right = (F(29, 54), F(2, 3), F(2, 3), F(2, 3))
    gain = F(9, 8)
    z = (left[0]-F(5, 6), *left[1:])
    z_prime = (right[0]-F(5, 6), *right[1:])
    a.need(tuple(gain*v for v in z_prime) == z, "centered exact alias identity")
    baseline = a.sub(a.point(120), a.mul(a.point(20), a.exponential(F(-5, 2))))
    b_exact = a.mul(a.point(1-gain), baseline)
    fine = F(1, 2**30)
    b = quantize(a.midpoint(b_exact), fine)
    a.need(max(abs(b-v) for v in b_exact) <= fine, "rational alias offset")
    s = Scenario("ALIAS", gain=gain, offset=b, step=fine)
    a.need(channel_membership(s, "WIDE_SYNTHETIC"), "alias outside declared channel")
    samples = []
    distances = []
    intervals = []
    for t in a.TIMES:
        il = certified_current(F(t), left)
        ir = certified_channel(t, right, s, F(0))
        hull = (min(il[0], ir[0]), max(il[1], ir[1]))
        y = quantize(a.midpoint(hull), fine)
        # The shared code is feasible in both models: an analog error
        # y-I, respectively y-I', maps exactly to the reported grid code.
        dl = max(abs(y-v) for v in il)
        dr = max(abs(y-v) for v in ir)
        a.need(max(dl, dr) <= EPS, "shared measurement certificate failed")
        samples.append(y)
        distances.append([a.q(dl), a.q(dr)])
        intervals.append([a.encode(il), a.encode(ir)])
    separation = max(abs(x-y) for x, y in zip(left, right, strict=True))
    a.need(separation == F(1, 12) > a.WIDTH, "alias separation")
    record = measurement(F(-71), samples)
    l = evaluate(F(-71), left, record)
    r = evaluate(F(-71), right, record)
    for truth in (left, right):
        certify_compatibility(truth, samples, "WIDE_SYNTHETIC")
    a.need(l["WIDE_SYNTHETIC"]["truth_enclosed"] and
           r["WIDE_SYNTHETIC"]["truth_enclosed"], "alias truth excluded")
    return {
        "status": "FAIL_WIDTH_IDENTIFIABILITY_COUNTEREXAMPLE",
        "left": [a.q(x) for x in left], "right": [a.q(x) for x in right],
        "gain": a.q(gain), "offset_pA": a.q(b),
        "exact_offset_outer_pA": a.encode(b_exact),
        "measurement": record, "certified_channel_intervals": intervals,
        "worst_distances_pA": distances, "minimum_width": a.q(separation),
        "requested_width": a.q(a.WIDTH), "left_outcomes": l, "right_outcomes": r,
    }


def summarize(cases):
    summaries = []
    for s in scenarios():
        rows = [row for row in cases if row["scenario"] == s.name]
        a.need(len(rows) == 32, "scenario roster")
        methods = {}
        for name in ("C_NOMINAL", *PROFILES):
            outcomes = [row["outcomes"][name] for row in rows]
            statuses = {}
            for item in outcomes:
                status = item["estimate"]["status"]
                statuses[status] = statuses.get(status, 0)+1
            methods[name] = {
                "truth_enclosed": sum(item["truth_enclosed"] for item in outcomes),
                "truth_excluded_or_inconsistent": sum(not item["truth_enclosed"] for item in outcomes),
                "false_narrow": sum(item["false_narrow"] for item in outcomes),
                "status_counts": statuses,
            }
        summaries.append({"scenario": s.name, "cases": len(rows),
                          "clipping_active_cases": sum(any(row["clipping_active"]) for row in rows),
                          "bounded_wide_cases": sum(row["bounded_wide"] for row in rows),
                          "methods": methods})
    return summaries


def report():
    cases = [panel_case(i, s, signs)
             for s, i, signs in itertools.product(scenarios(), TRUTHS, SIGNS)]
    keys = {(row["scenario"], row["truth_id"], tuple(row["noise_signs"])) for row in cases}
    a.need(len(cases) == len(keys) == 384, "complete fixed panel")
    a.need(sum(row["bounded_wide"] for row in cases) == 352 and
           sum(row["bounded_ideal"] for row in cases) == 32, "bounded case roster")
    return {
        "experiment": "CNEH-EXP-06F",
        "scope": "SYNTHETIC_SENSOR_CHANNEL_FALSIFICATION_ONLY",
        "qualification": "PASS_CONDITIONAL_CHANNEL_ENCLOSURE_ONLY",
        "sensor_width_identifiability": "FAIL_COUNTEREXAMPLE",
        "alias_witness": alias_witness(),
        "cases": cases,
        "scenario_summary": summarize(cases),
        **NEGATIVE,
    }
