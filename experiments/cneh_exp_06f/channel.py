"""Synthetic sensor-channel uncertainty, separate from the frozen C/D/E plant."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as F
from functools import lru_cache

from experiments.cneh_exp_06c import algebra as a, estimator as c

PRIOR = (F(0), F(1))
VOLTAGE_PRIOR = (F(-74), F(-68))
GRID = 2**60
NEGATIVE_GATES = {
    "real_calibration_verified": False,
    "joint_feasibility_proven": False,
    "source_action_authorized": False,
    "closed_loop_authorized": False,
    "scientific_promotion_authorized": False,
    "scientific_promotion": "BLOCKED",
}


@dataclass(frozen=True)
class Channel:
    gain: tuple[F, F]
    offset: tuple[F, F]
    drift: tuple[F, F]
    jitter: F
    quantization: F


PROFILES = {
    "IDEAL_QUANTIZED": Channel(a.point(1), a.point(0), a.point(0),
                               F(0), F(1, 2**20)),
    "WIDE_SYNTHETIC": Channel((F(7, 8), F(9, 8)), (F(-16), F(16)),
                              (F(-1), F(1)), F(1), F(1, 4)),
}


@lru_cache(maxsize=5)
def derivative_upper(t):
    """Certified bound on |I'(s)| for s >= t, on the nominal state prior."""
    a.need(type(t) is int and t in a.TIMES, "reported time domain")
    terms = ((F(20), F(200)), (F(6), F(5, 2)),
             (F(6), F(100)), (F(5), F(6)))
    return sum((amp/tau*a.exponential(-F(t)/tau)[1]
                for amp, tau in terms), F(0))


def dewarp(observed, eps, profile):
    """Outer intervals for I(t), not point-corrected measurements."""
    a.need(type(profile) is str and profile in PROFILES, "unknown bounded profile")
    a.need(len(observed) == len(a.TIMES) and
           all(type(y) is F for y in observed), "current roster")
    a.need(type(eps) is F and 0 <= eps <= a.MAX_ERROR, "analog error domain")
    p = PROFILES[profile]
    radius = eps + p.quantization/2
    result = []
    for t, y in zip(a.TIMES, observed, strict=True):
        code = (y-radius, y+radius)
        analog = a.div(a.sub(a.sub(code, p.offset),
                             a.mul(p.drift, a.point(F(t, 120)))), p.gain)
        time_radius = p.jitter*derivative_upper(t)
        result.append(a.outward(a.add(analog, (-time_radius, time_radius)), GRID))
    return tuple(result)


def result(status, profile, voltage=None, bounds=None, current=None):
    return {
        "status": status,
        "profile": profile,
        "scope": "OUTER_ENCLOSURE_CONDITIONAL_ON_NOMINAL_PLANT_AND_SYNTHETIC_CHANNEL",
        "voltage_bounds_mV": None if voltage is None else a.encode(voltage),
        "normalized_bounds": None if bounds is None else [a.encode(x) for x in bounds],
        "dewarped_current_pA": None if current is None else [a.encode(x) for x in current],
        **NEGATIVE_GATES,
    }


def estimate(record, profile="UNVERIFIED"):
    """No latent state, device credentials or physiological model-set claims."""
    a.need(type(profile) is str and
           (profile == "UNVERIFIED" or profile in PROFILES), "unknown calibration profile")
    voltage, ev, eps, observed = c.parse(record)
    if profile == "UNVERIFIED":
        return result("CALIBRATION_UNVERIFIED", profile, VOLTAGE_PRIOR, (PRIOR,)*4)
    vb = c.intersect((voltage-ev, voltage+ev), VOLTAGE_PRIOR)
    if vb is None:
        return result("INCONSISTENT_VOLTAGE", profile)
    measured = dewarp(observed, eps, profile)
    rows, offsets, inverse, *_ = a.model()
    # If x is compatible, H_mid x is inside y-b_mid plus coefficient
    # interval errors. Use the exact rational inverse, not numerical fitting.
    residuals = []
    for index in a.PRIMARY:
        rounding = a.radius(offsets[index]) + sum(map(a.radius, rows[index]))
        residuals.append(a.add(a.sub(measured[index], a.point(a.midpoint(offsets[index]))),
                               (-rounding, rounding)))
    bounds = []
    for row in inverse:
        interval = a.outward(a.isum(a.mul(a.point(coef), value)
                                    for coef, value in zip(row, residuals, strict=True)), 2**40)
        overlap = c.intersect(PRIOR, interval)
        if overlap is None:
            return result("INCONSISTENT_PRIMARY", profile, current=measured)
        bounds.append(overlap)
    for row, off, measurement in zip(rows, offsets, measured, strict=True):
        predicted = a.add(off, a.isum(a.mul(h, x)
                                      for h, x in zip(row, bounds, strict=True)))
        if c.intersect(predicted, measurement) is None:
            return result("INCONSISTENT_FORWARD", profile, current=measured)
    narrow = all(hi-lo <= a.WIDTH for lo, hi in bounds)
    return result("CONDITIONAL_NARROW_ENCLOSURE" if narrow else
                  "ABSTAIN_CHANNEL_AMBIGUITY", profile,
                  a.outward(vb, 2**40), tuple(bounds), measured)
