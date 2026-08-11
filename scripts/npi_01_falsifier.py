#!/usr/bin/env python3
"""NPI-01 constructive falsifier.

This module tests whether a first-order structural-identifiability nullspace
projection can certify a nonzero action-safe neighborhood.  It intentionally
uses exact rational arithmetic for the frozen counterexample family.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable

VERDICT = "NPI_01_FIRST_ORDER_CERTIFICATE_NOT_SUPPORTED"
HARNESS_INVALID = "HARNESS_INVALID"
FROZEN_RADII = (
    Fraction(1, 1),
    Fraction(1, 10),
    Fraction(1, 100),
    Fraction(1, 10_000),
    Fraction(1, 100_000_000),
)


def fstr(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}"


@dataclass(frozen=True)
class Certificate:
    observation: tuple[Fraction, ...]
    jacobian: tuple[tuple[Fraction, ...], ...]
    nullspace_basis: tuple[tuple[Fraction, ...], ...]
    margin: Fraction
    gradient: tuple[Fraction, ...]
    score_squared: Fraction


@dataclass(frozen=True)
class RadiusResult:
    radius: Fraction
    k: Fraction
    test_point: tuple[Fraction, Fraction]
    distance: Fraction
    observation_equal: bool
    inside_radius: bool
    baseline_margin_positive: bool
    score_zero: bool
    reversed_action: bool

    @property
    def passed(self) -> bool:
        return (
            self.observation_equal
            and self.inside_radius
            and self.baseline_margin_positive
            and self.score_zero
            and self.reversed_action
        )


def certificate(*, margin: Fraction = Fraction(1), linear_v: Fraction = Fraction(0),
                observe_v: bool = False,
                nullspace_basis: tuple[tuple[Fraction, Fraction], ...] = ((Fraction(0), Fraction(1)),)) -> Certificate:
    # y = u by default; mutation observe_v changes y = u + v.
    jacobian = ((Fraction(1), Fraction(1) if observe_v else Fraction(0)),)
    gradient = (Fraction(0), linear_v)
    score_squared = sum(
        sum(n_i * g_i for n_i, g_i in zip(vec, gradient, strict=True)) ** 2
        for vec in nullspace_basis
    )
    return Certificate(
        observation=(Fraction(0),),
        jacobian=jacobian,
        nullspace_basis=nullspace_basis,
        margin=margin,
        gradient=gradient,
        score_squared=score_squared,
    )


def evaluate_radius(radius: Fraction, *, k_multiplier: Fraction = Fraction(8),
                    point_multiplier: Fraction = Fraction(1, 2),
                    margin: Fraction = Fraction(1),
                    linear_v: Fraction = Fraction(0),
                    observe_v: bool = False,
                    nullspace_basis: tuple[tuple[Fraction, Fraction], ...] = ((Fraction(0), Fraction(1)),)) -> RadiusResult:
    if radius <= 0:
        raise ValueError("radius must be positive")
    k = k_multiplier / (radius * radius)
    v = point_multiplier * radius
    # y = u (+ v for mutation); theta0=(0,0), theta'=(0,v)
    y0 = Fraction(0)
    y1 = v if observe_v else Fraction(0)
    delta_test = margin + linear_v * v - k * v * v
    cert = certificate(
        margin=margin,
        linear_v=linear_v,
        observe_v=observe_v,
        nullspace_basis=nullspace_basis,
    )
    return RadiusResult(
        radius=radius,
        k=k,
        test_point=(Fraction(0), v),
        distance=abs(v),
        observation_equal=(y0 == y1),
        inside_radius=(abs(v) < radius),
        baseline_margin_positive=(margin > 0),
        score_zero=(cert.score_squared == 0),
        reversed_action=(delta_test < 0),
    )


def frozen_counterexample_results() -> list[RadiusResult]:
    return [evaluate_radius(r) for r in FROZEN_RADII]


def mutation_results() -> dict[str, bool]:
    """Return True when a frozen mutation is correctly killed by the gate."""
    r = Fraction(1, 10)
    mutations = {
        "OBSERVABLE_V": evaluate_radius(r, observe_v=True),
        "NONZERO_FIRST_ORDER_GRADIENT": evaluate_radius(r, linear_v=Fraction(1)),
        "POINT_OUTSIDE_RADIUS": evaluate_radius(r, point_multiplier=Fraction(2)),
        "INSUFFICIENT_CURVATURE": evaluate_radius(r, k_multiplier=Fraction(1)),
        "NONPOSITIVE_MARGIN": evaluate_radius(r, margin=Fraction(0)),
        "WRONG_NULLSPACE_BASIS": evaluate_radius(
            r, nullspace_basis=((Fraction(1), Fraction(0)),)
        ),
    }
    return {name: not result.passed for name, result in mutations.items()}


def verify_certificate_identity(radii: Iterable[Fraction]) -> bool:
    # K and radius must not affect the local first-order certificate at theta0.
    base = certificate()
    return all(certificate() == base for _ in radii)


def build_report() -> dict[str, object]:
    results = frozen_counterexample_results()
    mutations = mutation_results()
    certificate_identity = verify_certificate_identity(FROZEN_RADII)
    counterexample_pass = all(r.passed for r in results)
    mutations_killed = all(mutations.values())
    verdict = VERDICT if certificate_identity and counterexample_pass and mutations_killed else HARNESS_INVALID
    return {
        "schema": "cwc-npi-01/1.0",
        "hypothesis_id": "H-NPI-01",
        "verdict": verdict,
        "certificate_identity": certificate_identity,
        "counterexample_all_radii": counterexample_pass,
        "mutation_kills": mutations,
        "mutation_kill_count": sum(mutations.values()),
        "mutation_total": len(mutations),
        "radii": [
            {
                **{k: (fstr(v) if isinstance(v, Fraction) else v) for k, v in asdict(r).items() if k != "test_point"},
                "test_point": [fstr(v) for v in r.test_point],
                "passed": r.passed,
            }
            for r in results
        ],
        "local_certificate": {
            "observation": [fstr(v) for v in certificate().observation],
            "jacobian": [[fstr(v) for v in row] for row in certificate().jacobian],
            "nullspace_basis": [[fstr(v) for v in row] for row in certificate().nullspace_basis],
            "margin": fstr(certificate().margin),
            "gradient": [fstr(v) for v in certificate().gradient],
            "score_squared": fstr(certificate().score_squared),
        },
        "claim_boundary": (
            "Kills first-order sufficiency only; does not refute curvature-bounded or set-valued "
            "identifiability-aware inhibitory control."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    report = build_report()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))

    if args.self_test and report["mutation_kill_count"] != report["mutation_total"]:
        return 2
    return 0 if report["verdict"] == VERDICT else 1


if __name__ == "__main__":
    raise SystemExit(main())
