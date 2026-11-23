"""Bounded-noise, erased-spike support filter for the EXP04B route family.

Analytic only: a conservative outer approximation of trajectory feasibility.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Iterable

MODES = ((1, 0), (0, 1), (1, 1), (0, 0))
DECAY = math.exp(-0.1 / 6)
QUANTUM = DECAY * .5
EPS = .01
RADIUS = (1 + DECAY) * EPS + 1e-12
N_RECEIVERS = 16
HERE = Path(__file__).resolve().parent


def count_range(bits: tuple[int | None, ...]) -> tuple[int, int]:
    if len(bits) != 4 or any(x is not None and (type(x) is not int or x not in (0, 1)) for x in bits):
        raise ValueError("invalid erased-spike observation")
    lo = bits.count(1)
    return lo, lo + bits.count(None)


def observed_residual(previous: tuple[float, ...], current: tuple[float, ...]) -> tuple[float, ...]:
    if len(previous) != N_RECEIVERS or len(current) != N_RECEIVERS:
        raise ValueError("incomplete receiver observation")
    if any(not math.isfinite(v) for v in previous + current):
        raise ValueError("nonfinite conductance observation")
    r = tuple(y - DECAY*x for x, y in zip(previous, current, strict=True))
    if any(not math.isfinite(v) for v in r):
        raise ValueError("nonfinite residual")
    return r


def possible_counts(mode: int, bits: tuple[int | None, ...]) -> range:
    if type(mode) is not int or mode not in range(4) or len(bits) != 8:
        raise ValueError("invalid mode or source roster")
    a, b = count_range(bits[:4]), count_range(bits[4:])
    m = MODES[mode]
    return range(m[0]*a[0]+m[1]*b[0], m[0]*a[1]+m[1]*b[1]+1)


def support(candidates: tuple[int, ...], bits: tuple[int | None, ...],
            r: tuple[float, ...]) -> tuple[int, ...]:
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError("empty or duplicate candidate input")
    if len(r) != N_RECEIVERS or any(not math.isfinite(x) for x in r):
        raise ValueError("invalid receiver residual")
    lo, hi = min(r), max(r)
    return tuple(mode for mode in candidates
                 if any(max(abs(lo - QUANTUM*k), abs(hi - QUANTUM*k)) <= RADIUS
                        for k in possible_counts(mode, bits)))


def update(candidates: tuple[int, ...], bits: tuple[int | None, ...],
           previous: tuple[float, ...], current: tuple[float, ...]) -> tuple[int, ...]:
    """Intersect within an assumed unchanged mode; reject unsupported observations."""
    result = support(candidates, bits, observed_residual(previous, current))
    if not result:
        raise ValueError("MODEL_SET_VIOLATION")
    return result


def observation_classes() -> Iterable[tuple[tuple[int | None, ...], range]]:
    for ones in range(5):
        for erased in range(5 - ones):
            yield ((1,) * ones + (0,) * (4-ones-erased) + (None,) * erased,
                   range(ones, ones+erased+1))


def qualification() -> dict:
    classes = tuple(observation_classes())
    bound = (1+DECAY)*EPS
    patterns = ((-bound,) * 16, (bound,) * 16, (-bound, bound) * 8)
    count, ambiguous, singleton = 0, 0, 0
    for (a, ar), (b, br) in itertools.product(classes, repeat=2):
        bits = a+b
        for n0, n1, mode, noise in itertools.product(ar, br, range(4), patterns):
            m = MODES[mode]
            expected = QUANTUM*(m[0]*n0+m[1]*n1)
            result = support(tuple(range(4)), bits, tuple(expected+v for v in noise))
            if mode not in result:
                raise AssertionError("false exclusion of true mode")
            count += 1
            singleton += len(result) == 1
            ambiguous += len(result) > 1
    if count != 14700 or count != singleton + ambiguous:
        raise AssertionError("incomplete exhaustive fixture enumeration")
    if not QUANTUM > 2*RADIUS:
        raise AssertionError("count bands are not separated")
    return {"schema": "cneh-bounded-route-support-qualification-v1",
            "authority": "ANALYTIC_FIXTURES_ONLY", "cases": count,
            "false_exclusions": 0, "singleton_cases": singleton,
            "ambiguous_cases": ambiguous, "arrival_quantum_nS": QUANTUM,
            "residual_radius_nS": RADIUS, "minimum_band_gap_nS": QUANTUM-2*RADIUS,
            "receiver_shared_integer_enforced": True,
            "discrete_count_bands_enforced": True,
            "trajectory_global_feasibility_established": False,
            "scientific_promotion_authorized": False,
            "neural_sensor_qualification": "NOT_TESTED",
            "independent_replication": "NOT_TESTED", "physical_energy": "INSTRUMENT_INVALID"}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()
    report = qualification()
    report["implementation_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["preregistration_sha256"] = hashlib.sha256((HERE/"PREREGISTRATION.md").read_bytes()).hexdigest()
    data = (json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()
    if args.verify:
        if args.out.is_symlink() or not args.out.is_file() or args.out.read_bytes() != data:
            raise ValueError("qualification replay mismatch")
    else:
        with args.out.open("xb") as f:
            f.write(data)
    print(data.decode().strip())


if __name__ == "__main__":
    main()
